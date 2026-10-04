from datetime import UTC, date, datetime, timedelta

import pytest
from typer.testing import CliRunner

from brcredit import cli
from brcredit.sources.bcb_sgs import SgsError, WindowResponse, split_windows

# Largura fixa para a caixa de erro do Typer não quebrar as mensagens no meio.
runner = CliRunner(env={"COLUMNS": "200"})


class FakeClient:
    def __init__(self):
        self.calls = []
        self.fail_codes = set()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def fetch_series(self, code, start, end):
        self.calls.append((code, start, end))
        if code in self.fail_codes:
            raise SgsError(f"Série {code}: falhou após 4 tentativas")
        for window in split_windows(start, end):
            yield WindowResponse(
                series_code=code,
                window=window,
                records=[{"data": window.start.strftime("%d/%m/%Y"), "valor": "1.00"}],
                request_url="https://example",
                http_status=200,
                body_sha256="0" * 64,
                extracted_at=datetime.now(UTC),
            )


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    client = FakeClient()
    monkeypatch.setattr(cli, "make_sgs_client", lambda: client)
    return client


def _runs(tmp_path, code):
    return list((tmp_path / "bronze" / "bcb_sgs" / f"serie={code}").glob("run=*"))


def test_start_after_end_fails_before_any_request(fake):
    result = runner.invoke(
        cli.app, ["ingest", "sgs", "--start", "2020-01-02", "--end", "2020-01-01"]
    )
    assert result.exit_code != 0
    assert fake.calls == []


def test_future_end_fails_before_any_request(fake):
    future = (date.today() + timedelta(days=1)).isoformat()
    result = runner.invoke(cli.app, ["ingest", "sgs", "--end", future])
    assert result.exit_code != 0
    assert "futuro" in result.output
    assert fake.calls == []


def test_unknown_series_lists_valid_codes(fake):
    result = runner.invoke(cli.app, ["ingest", "sgs", "--serie", "1"])
    assert result.exit_code != 0
    assert "432, 433" in result.output
    assert fake.calls == []


def test_default_run_captures_all_series_from_catalog_start(fake, tmp_path):
    result = runner.invoke(cli.app, ["ingest", "sgs", "--end", "2026-10-01"])
    assert result.exit_code == 0, result.output
    assert fake.calls == [
        (432, date(2012, 6, 1), date(2026, 10, 1)),
        (433, date(2011, 6, 1), date(2026, 10, 1)),
    ]
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0].startswith("432")
    assert "janelas" in lines[0]
    runs_432, runs_433 = _runs(tmp_path, 432), _runs(tmp_path, 433)
    assert len(runs_432) == len(runs_433) == 1
    assert runs_432[0].name == runs_433[0].name


def test_single_series_with_explicit_period(fake):
    result = runner.invoke(
        cli.app,
        ["ingest", "sgs", "--serie", "433", "--start", "2020-01-01", "--end", "2020-12-31"],
    )
    assert result.exit_code == 0, result.output
    assert fake.calls == [(433, date(2020, 1, 1), date(2020, 12, 31))]


def test_failed_series_does_not_block_others_and_exits_nonzero(fake, tmp_path):
    fake.fail_codes = {433}
    result = runner.invoke(cli.app, ["ingest", "sgs", "--end", "2026-10-01"])
    assert result.exit_code == 1
    assert "433" in result.output
    assert _runs(tmp_path, 432)
    assert not _runs(tmp_path, 433)
