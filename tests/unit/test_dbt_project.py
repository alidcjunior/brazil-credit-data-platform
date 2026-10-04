import shutil
from pathlib import Path

from dbt.cli.main import dbtRunner

DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"


def test_dbt_project_parses_without_database(tmp_path, monkeypatch):
    shutil.copy(DBT_DIR / "profiles.yml.example", tmp_path / "profiles.yml")
    for name, value in {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "brcredit",
        "POSTGRES_PASSWORD": "brcredit",
        "POSTGRES_DB": "brcredit",
    }.items():
        monkeypatch.setenv(name, value)

    result = dbtRunner().invoke(
        [
            "parse",
            "--project-dir",
            str(DBT_DIR),
            "--profiles-dir",
            str(tmp_path),
            "--target-path",
            str(tmp_path / "target"),
            "--log-path",
            str(tmp_path / "logs"),
        ]
    )

    assert result.success, result.exception
    nodes = result.result.nodes
    models = {n.name for n in nodes.values() if n.resource_type == "model"}
    assert models == {
        "stg_bcb_sgs__observations",
        "int_selic_monthly",
        "int_ipca_monthly",
        "fct_monthly_macro_indicators",
    }
    tests = {n.name for n in nodes.values() if n.resource_type == "test"}
    assert {
        "assert_no_month_gaps",
        "assert_starts_jun_2012",
        "assert_ipca_12m_official_values",
    } <= tests
    assert any(name.startswith("accepted_range_") for name in tests)
