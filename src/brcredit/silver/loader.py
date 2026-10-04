"""Silver: transforma as capturas do bronze em observações tipadas e faz upsert no Postgres."""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from brcredit.bronze.writer import read_captures
from brcredit.catalog import SERIES

logger = logging.getLogger(__name__)

SILVER_COLUMNS = ["series_code", "ref_date", "value", "source_run_id", "source_extracted_at"]
KEY = ["series_code", "ref_date"]


class SilverParseError(ValueError):
    """Valor ou data do bronze que não pode ser convertido."""


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int
    unchanged: int


def _parse_value(raw: str, run_id: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise SilverParseError(f"Valor não numérico {raw!r} na captura {run_id}") from None
    if not value.is_finite():
        raise SilverParseError(f"Valor não finito {raw!r} na captura {run_id}")
    return value


def _parse_date(raw: str, run_id: str):
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError:
        raise SilverParseError(f"Data inválida {raw!r} na captura {run_id}") from None


def parse_captures(bronze: pd.DataFrame) -> pd.DataFrame:
    """Converte `data` e `valor` brutos em tipos; falha apontando a captura de origem."""
    rows = [
        {
            "series_code": int(row.series_code),
            "ref_date": _parse_date(row.data, row.run_id),
            "value": _parse_value(row.valor, row.run_id),
            "source_run_id": row.run_id,
            "source_extracted_at": row.extracted_at,
        }
        for row in bronze.itertuples(index=False)
    ]
    return pd.DataFrame(rows, columns=SILVER_COLUMNS)


def dedupe_latest(parsed: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por série + data: vence a captura mais recente (empate: maior run_id)."""
    ordered = parsed.sort_values(
        ["source_extracted_at", "source_run_id"], ascending=False, kind="stable"
    )
    return ordered.drop_duplicates(KEY, keep="first").sort_values(KEY).reset_index(drop=True)


_UPSERT_SERIES = text(
    """
    INSERT INTO silver.sgs_series (series_code, name, unit, periodicity)
    VALUES (:series_code, :name, :unit, :periodicity)
    ON CONFLICT (series_code) DO UPDATE
    SET name = excluded.name, unit = excluded.unit, periodicity = excluded.periodicity
    """
)

_CREATE_STAGE = text(
    """
    CREATE TEMPORARY TABLE stage_sgs_observation (LIKE silver.sgs_observation
        INCLUDING DEFAULTS) ON COMMIT DROP
    """
)

_INSERT_STAGE = text(
    """
    INSERT INTO stage_sgs_observation
        (series_code, ref_date, value, source_run_id, source_extracted_at)
    VALUES (:series_code, :ref_date, :value, :source_run_id, :source_extracted_at)
    """
)

# Atualiza só quando o valor muda: recapturar o mesmo dado não altera nada (idempotência).
_UPSERT_OBSERVATIONS = text(
    """
    WITH upserted AS (
        INSERT INTO silver.sgs_observation
            (series_code, ref_date, value, source_run_id, source_extracted_at)
        SELECT series_code, ref_date, value, source_run_id, source_extracted_at
        FROM stage_sgs_observation
        ON CONFLICT (series_code, ref_date) DO UPDATE
        SET value = excluded.value,
            source_run_id = excluded.source_run_id,
            source_extracted_at = excluded.source_extracted_at,
            loaded_at = now()
        WHERE silver.sgs_observation.value IS DISTINCT FROM excluded.value
        RETURNING (xmax = 0) AS inserted
    )
    SELECT count(*) FILTER (WHERE inserted) AS inserted,
           count(*) FILTER (WHERE NOT inserted) AS updated
    FROM upserted
    """
)


def load_silver(engine: Engine, data_dir: Path) -> LoadResult:
    frames = [parse_captures(read_captures(data_dir, code)) for code in sorted(SERIES)]
    observations = dedupe_latest(pd.concat(frames, ignore_index=True))
    # Tipos nativos do Python: o psycopg não adapta numpy.int64 nem pandas.Timestamp por padrão.
    records = [
        {
            **row,
            "series_code": int(row["series_code"]),
            "source_extracted_at": pd.Timestamp(row["source_extracted_at"]).to_pydatetime(),
        }
        for row in observations.to_dict("records")
    ]
    logger.info("%d observações distintas no bronze", len(records))

    with engine.begin() as conn:
        conn.execute(
            _UPSERT_SERIES,
            [
                {
                    "series_code": s.code,
                    "name": s.name,
                    "unit": s.unit,
                    "periodicity": s.periodicity,
                }
                for s in SERIES.values()
            ],
        )
        conn.execute(_CREATE_STAGE)
        if records:
            conn.execute(_INSERT_STAGE, records)
        inserted, updated = conn.execute(_UPSERT_OBSERVATIONS).one()

    return LoadResult(
        inserted=inserted, updated=updated, unchanged=len(records) - inserted - updated
    )
