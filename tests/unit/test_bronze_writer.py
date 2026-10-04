import json
from datetime import UTC, date, datetime

import pyarrow.parquet as pq
import pytest

from brcredit.bronze.writer import new_run_id, read_captures, series_dir, write_capture
from brcredit.sources.bcb_sgs import Window, WindowResponse

EXTRACTED_AT = datetime(2026, 10, 4, 18, 30, tzinfo=UTC)


def _response(window: Window, records: list[dict]) -> WindowResponse:
    return WindowResponse(
        series_code=432,
        window=window,
        records=records,
        request_url=f"https://example/432?{window.start}",
        http_status=200,
        body_sha256="0" * 64,
        extracted_at=EXTRACTED_AT,
    )


@pytest.fixture
def responses(fixtures_dir):
    records = json.loads((fixtures_dir / "sgs_432_2012-06-01_2012-07-31.json").read_text())
    return [
        _response(Window(date(2012, 6, 1), date(2012, 7, 31)), records),
        _response(Window(date(2012, 8, 1), date(2012, 8, 31)), []),
    ]


def test_run_id_format():
    run_id = new_run_id(datetime(2026, 10, 4, 18, 30, 5, tzinfo=UTC))
    assert run_id.startswith("20261004T183005Z-")
    assert len(run_id.split("-")[1]) == 4


def test_writes_raw_strings_and_metadata(tmp_path, responses):
    summary = write_capture(tmp_path, 432, "RUN1", responses)
    run_dir = series_dir(tmp_path, 432) / "run=RUN1"
    assert summary.path == run_dir
    assert summary.windows == 2
    assert summary.rows == 61

    table = pq.read_table(run_dir / "part-000.parquet")
    assert table.column_names == [
        "data",
        "valor",
        "series_code",
        "window_start",
        "window_end",
        "request_url",
        "extracted_at",
        "run_id",
    ]
    assert str(table.schema.field("data").type) == "string"
    assert str(table.schema.field("valor").type) == "string"
    first = table.slice(0, 1).to_pylist()[0]
    assert first["data"] == "01/06/2012"
    assert first["valor"] == "8.50"
    assert first["run_id"] == "RUN1"


def test_manifest_has_one_row_per_window_including_empty(tmp_path, responses):
    write_capture(tmp_path, 432, "RUN1", responses)
    manifest = pq.read_table(series_dir(tmp_path, 432) / "run=RUN1" / "manifest.parquet")
    rows = manifest.to_pylist()
    assert [r["row_count"] for r in rows] == [61, 0]
    assert all(r["http_status"] == 200 and len(r["body_sha256"]) == 64 for r in rows)
    assert rows[1]["window_start"] == date(2012, 8, 1)


def test_second_run_leaves_first_untouched(tmp_path, responses):
    write_capture(tmp_path, 432, "RUN1", responses)
    first = series_dir(tmp_path, 432) / "run=RUN1" / "part-000.parquet"
    before = first.read_bytes()
    write_capture(tmp_path, 432, "RUN2", responses[:1])
    assert first.read_bytes() == before
    assert (series_dir(tmp_path, 432) / "run=RUN2").is_dir()


def test_existing_run_is_never_overwritten(tmp_path, responses):
    write_capture(tmp_path, 432, "RUN1", responses)
    with pytest.raises(FileExistsError):
        write_capture(tmp_path, 432, "RUN1", responses)


def test_failure_mid_capture_leaves_only_tmp_dir(tmp_path, responses):
    def failing():
        yield responses[0]
        raise RuntimeError("API caiu")

    with pytest.raises(RuntimeError):
        write_capture(tmp_path, 432, "RUN1", failing())
    names = [p.name for p in series_dir(tmp_path, 432).iterdir()]
    assert names == [".tmp-run=RUN1"]
    assert read_captures(tmp_path, 432).empty


def test_read_captures_returns_rows_from_all_runs(tmp_path, responses):
    write_capture(tmp_path, 432, "RUN1", responses)
    write_capture(tmp_path, 432, "RUN2", responses[:1])
    df = read_captures(tmp_path, 432)
    assert len(df) == 122
    assert set(df["run_id"]) == {"RUN1", "RUN2"}


def test_read_captures_without_data_returns_empty(tmp_path):
    df = read_captures(tmp_path, 433)
    assert df.empty
    assert "valor" in df.columns
