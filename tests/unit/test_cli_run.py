import pytest
import typer
from typer.testing import CliRunner

from brcredit import cli

runner = CliRunner(env={"COLUMNS": "200"})

STEPS = ["ingest_sgs", "init_db_cmd", "load_silver_cmd", "build_gold_cmd", "chart_cmd"]


@pytest.fixture
def calls(monkeypatch):
    calls: list[str] = []
    for name in STEPS:
        monkeypatch.setattr(cli, name, lambda *a, _name=name, **kw: calls.append(_name))
    return calls


def test_run_executes_steps_in_order(calls):
    result = runner.invoke(cli.app, ["run"])
    assert result.exit_code == 0, result.output
    assert calls == STEPS


def test_run_stops_at_first_failure(calls, monkeypatch):
    def failing_load(*args, **kwargs):
        calls.append("load_silver_cmd")
        raise typer.Exit(code=1)

    monkeypatch.setattr(cli, "load_silver_cmd", failing_load)
    result = runner.invoke(cli.app, ["run"])
    assert result.exit_code == 1
    assert calls == ["ingest_sgs", "init_db_cmd", "load_silver_cmd"]


def test_db_commands_fail_clearly_without_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:x@127.0.0.1:1/x")
    result = runner.invoke(cli.app, ["init-db"])
    assert result.exit_code == 1
    assert "docker compose up" in result.output
