"""Bronze: grava as respostas da API em Parquet, sem conversão, uma execução por diretório."""

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from brcredit.sources.bcb_sgs import WindowResponse

SOURCE = "bcb_sgs"

DATA_SCHEMA = pa.schema(
    [
        ("data", pa.string()),
        ("valor", pa.string()),
        ("series_code", pa.int16()),
        ("window_start", pa.date32()),
        ("window_end", pa.date32()),
        ("request_url", pa.string()),
        ("extracted_at", pa.timestamp("us", tz="UTC")),
        ("run_id", pa.string()),
    ]
)

MANIFEST_SCHEMA = pa.schema(
    [
        ("series_code", pa.int16()),
        ("window_start", pa.date32()),
        ("window_end", pa.date32()),
        ("request_url", pa.string()),
        ("http_status", pa.int16()),
        ("row_count", pa.int32()),
        ("body_sha256", pa.string()),
        ("extracted_at", pa.timestamp("us", tz="UTC")),
        ("run_id", pa.string()),
    ]
)


@dataclass(frozen=True)
class CaptureSummary:
    path: Path
    windows: int
    rows: int


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(2)}"


def series_dir(data_dir: Path, code: int) -> Path:
    return Path(data_dir) / "bronze" / SOURCE / f"serie={code}"


def write_capture(
    data_dir: Path, code: int, run_id: str, responses: Iterable[WindowResponse]
) -> CaptureSummary:
    """Grava todas as janelas de uma série numa execução nova.

    Escreve em `.tmp-run=<id>` e só renomeia para `run=<id>` no fim: se a captura falhar no meio,
    nada fica visível para a leitura. Execuções existentes nunca são sobrescritas.
    """
    base = series_dir(data_dir, code)
    final_dir = base / f"run={run_id}"
    if final_dir.exists():
        raise FileExistsError(f"Execução {final_dir} já existe; o bronze é imutável")
    tmp_dir = base / f".tmp-run={run_id}"
    tmp_dir.mkdir(parents=True, exist_ok=False)

    data_rows: list[dict] = []
    manifest_rows: list[dict] = []
    for response in responses:
        meta = {
            "series_code": code,
            "window_start": response.window.start,
            "window_end": response.window.end,
            "request_url": response.request_url,
            "extracted_at": response.extracted_at,
            "run_id": run_id,
        }
        data_rows.extend({"data": r["data"], "valor": r["valor"], **meta} for r in response.records)
        manifest_rows.append(
            {
                **meta,
                "http_status": response.http_status,
                "row_count": len(response.records),
                "body_sha256": response.body_sha256,
            }
        )

    pq.write_table(
        pa.Table.from_pylist(data_rows, schema=DATA_SCHEMA), tmp_dir / "part-000.parquet"
    )
    pq.write_table(
        pa.Table.from_pylist(manifest_rows, schema=MANIFEST_SCHEMA), tmp_dir / "manifest.parquet"
    )
    tmp_dir.rename(final_dir)
    return CaptureSummary(path=final_dir, windows=len(manifest_rows), rows=len(data_rows))


def read_captures(data_dir: Path, code: int) -> pd.DataFrame:
    """Lê as linhas de todas as execuções concluídas da série (ignora `.tmp-*`)."""
    files = sorted(series_dir(data_dir, code).glob("run=*/part-*.parquet"))
    if not files:
        return DATA_SCHEMA.empty_table().to_pandas()
    return pa.concat_tables(pq.read_table(f, schema=DATA_SCHEMA) for f in files).to_pandas()
