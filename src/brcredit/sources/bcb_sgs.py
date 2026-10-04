"""Cliente da API SGS do Banco Central. Só sabe falar com a API: não grava nada."""

import hashlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import httpx
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
# Limite da API para séries diárias. Usamos janelas menores por padrão porque consultas perto do
# limite às vezes estouram o tempo do servidor e voltam HTTP 200 com uma página HTML de erro.
MAX_API_WINDOW_YEARS = 10
DEFAULT_WINDOW_YEARS = 5
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_ATTEMPTS = 4


class SgsError(Exception):
    """Falha ao obter dados da API SGS."""


class SgsResponseError(SgsError):
    """A API respondeu JSON fora do formato esperado."""


class _TransientError(Exception):
    """Resposta que vale a pena repetir (429, 5xx, corpo não-JSON com HTTP 200)."""


@dataclass(frozen=True)
class Window:
    start: date
    end: date


@dataclass(frozen=True)
class WindowResponse:
    series_code: int
    window: Window
    records: list[dict[str, str]]
    request_url: str
    http_status: int
    body_sha256: str
    extracted_at: datetime


def build_url(code: int) -> str:
    return BASE_URL.format(code=code)


def _add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29/02 em ano não bissexto
        return day.replace(year=day.year + years, day=28)


def split_windows(start: date, end: date, max_years: int = DEFAULT_WINDOW_YEARS) -> list[Window]:
    """Divide [start, end] em janelas contíguas de até `max_years` anos, sem buracos nem
    sobreposição."""
    if start > end:
        raise ValueError(f"Data inicial {start} é posterior à final {end}")
    if not 1 <= max_years <= MAX_API_WINDOW_YEARS:
        raise ValueError(f"max_years deve estar entre 1 e {MAX_API_WINDOW_YEARS}")
    windows = []
    current = start
    while current <= end:
        window_end = min(_add_years(current, max_years) - timedelta(days=1), end)
        windows.append(Window(current, window_end))
        current = window_end + timedelta(days=1)
    return windows


def _format_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _validate_records(payload: object, url: str) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        raise SgsResponseError(f"Esperava uma lista JSON em {url}, recebi {type(payload).__name__}")
    for item in payload:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("data"), str)
            and isinstance(item.get("valor"), str)
        ):
            raise SgsResponseError(f"Registro fora do formato {{data, valor}} em {url}: {item!r}")
    return payload


class SgsClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = 1.0,
        window_years: int = DEFAULT_WINDOW_YEARS,
    ) -> None:
        self._http = http or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._window_years = window_years

    def __enter__(self) -> "SgsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def fetch_series(self, code: int, start: date, end: date) -> Iterator[WindowResponse]:
        for window in split_windows(start, end, self._window_years):
            yield self.fetch_window(code, window)

    def fetch_window(self, code: int, window: Window) -> WindowResponse:
        retrying = Retrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=self._backoff_seconds),
            retry=retry_if_exception_type((httpx.TransportError, _TransientError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        try:
            response, payload = retrying(self._request, code, window)
        except (httpx.TransportError, _TransientError) as exc:
            raise SgsError(
                f"Série {code} {_format_date(window.start)}–{_format_date(window.end)}: "
                f"falhou após {self._max_attempts} tentativas ({exc})"
            ) from exc

        url = str(response.url)
        records = _validate_records(payload, url)
        logger.debug("Série %s %s: %d registros", code, window, len(records))
        return WindowResponse(
            series_code=code,
            window=window,
            records=records,
            request_url=url,
            http_status=response.status_code,
            body_sha256=hashlib.sha256(response.content).hexdigest(),
            extracted_at=datetime.now(UTC),
        )

    def _request(self, code: int, window: Window) -> tuple[httpx.Response, object]:
        response = self._http.get(
            build_url(code),
            params={
                "formato": "json",
                "dataInicial": _format_date(window.start),
                "dataFinal": _format_date(window.end),
            },
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise _TransientError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise SgsError(f"HTTP {response.status_code} em {response.url}: {response.text[:300]}")
        try:
            return response, response.json()
        except ValueError:
            # A API às vezes devolve HTTP 200 com página HTML "Requisição inválida!" (timeout).
            raise _TransientError("HTTP 200 com corpo não-JSON") from None
