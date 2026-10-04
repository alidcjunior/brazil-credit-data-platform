import json
from datetime import date

import httpx
import pytest
import respx

from brcredit.sources.bcb_sgs import (
    SgsClient,
    SgsError,
    SgsResponseError,
    Window,
    build_url,
)

WINDOW_432 = Window(date(2012, 6, 1), date(2012, 7, 31))
URL_432 = build_url(432)


@pytest.fixture(scope="module")
def client():
    with SgsClient(backoff_seconds=0) as c:
        yield c


def _fixture(fixtures_dir, name: str) -> bytes:
    return (fixtures_dir / name).read_bytes()


@respx.mock
def test_request_uses_brazilian_date_format(client, fixtures_dir):
    route = respx.get(URL_432).mock(
        return_value=httpx.Response(
            200, content=_fixture(fixtures_dir, "sgs_432_2012-06-01_2012-07-31.json")
        )
    )
    client.fetch_window(432, WINDOW_432)
    params = route.calls.last.request.url.params
    assert params["dataInicial"] == "01/06/2012"
    assert params["dataFinal"] == "31/07/2012"
    assert params["formato"] == "json"


@respx.mock
def test_records_are_returned_unchanged(client, fixtures_dir):
    body = _fixture(fixtures_dir, "sgs_432_2012-06-01_2012-07-31.json")
    respx.get(URL_432).mock(return_value=httpx.Response(200, content=body))
    result = client.fetch_window(432, WINDOW_432)
    assert result.records == json.loads(body)
    assert result.records[0] == {"data": "01/06/2012", "valor": "8.50"}
    assert result.http_status == 200
    assert len(result.body_sha256) == 64
    assert result.window == WINDOW_432
    assert "bcdata.sgs.432" in result.request_url


@respx.mock
def test_empty_list_is_valid(client):
    respx.get(URL_432).mock(return_value=httpx.Response(200, json=[]))
    assert client.fetch_window(432, WINDOW_432).records == []


@respx.mock
def test_retries_transient_errors_then_succeeds(client, fixtures_dir):
    body = _fixture(fixtures_dir, "sgs_432_2012-06-01_2012-07-31.json")
    route = respx.get(URL_432).mock(
        side_effect=[
            httpx.ReadTimeout("timeout"),
            httpx.Response(503),
            httpx.Response(200, content=body),
        ]
    )
    result = client.fetch_window(432, WINDOW_432)
    assert route.call_count == 3
    assert len(result.records) == 61


@respx.mock
def test_html_page_with_200_is_retried(client, fixtures_dir):
    html = _fixture(fixtures_dir, "sgs_432_200_html_invalid_request.html")
    route = respx.get(URL_432).mock(
        side_effect=[
            httpx.Response(200, content=html, headers={"content-type": "text/html"}),
            httpx.Response(200, json=[{"data": "01/06/2012", "valor": "8.50"}]),
        ]
    )
    assert len(client.fetch_window(432, WINDOW_432).records) == 1
    assert route.call_count == 2


@respx.mock
def test_persistent_html_page_raises_after_max_attempts(client, fixtures_dir):
    html = _fixture(fixtures_dir, "sgs_432_200_html_invalid_request.html")
    route = respx.get(URL_432).mock(
        return_value=httpx.Response(200, content=html, headers={"content-type": "text/html"})
    )
    with pytest.raises(SgsError, match="4 tentativas"):
        client.fetch_window(432, WINDOW_432)
    assert route.call_count == 4


@respx.mock
def test_does_not_retry_client_errors(client, fixtures_dir):
    route = respx.get(URL_432).mock(
        return_value=httpx.Response(
            406, content=_fixture(fixtures_dir, "sgs_432_406_window_too_large.json")
        )
    )
    with pytest.raises(SgsError, match="406.*10 anos"):
        client.fetch_window(432, WINDOW_432)
    assert route.call_count == 1


@respx.mock
def test_raises_after_max_attempts(client):
    route = respx.get(URL_432).mock(return_value=httpx.Response(503))
    with pytest.raises(SgsError, match="4 tentativas"):
        client.fetch_window(432, WINDOW_432)
    assert route.call_count == 4


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [{"erro": "x"}, [{"data": "01/06/2012"}], ["01/06/2012"], [{"data": 1, "valor": "8.5"}]],
)
def test_unexpected_json_shape_is_not_retried(client, payload):
    route = respx.get(URL_432).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(SgsResponseError, match="bcdata.sgs.432"):
        client.fetch_window(432, WINDOW_432)
    assert route.call_count == 1


@respx.mock
def test_fetch_series_walks_all_windows(client):
    route = respx.get(URL_432).mock(return_value=httpx.Response(200, json=[]))
    results = list(client.fetch_series(432, date(2012, 6, 1), date(2026, 10, 4)))
    assert route.call_count == 3
    assert results[0].window.start == date(2012, 6, 1)
    assert results[-1].window.end == date(2026, 10, 4)
