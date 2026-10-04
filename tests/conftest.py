import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def _test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


def _db_available(url: str) -> bool:
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url, connect_args={"connect_timeout": 1})
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    db_items = [item for item in items if "db" in item.keywords]
    if not db_items:
        return
    url = _test_database_url()
    reason = None
    if not url:
        reason = "TEST_DATABASE_URL não definido"
    elif not _db_available(url):
        reason = "banco de teste não responde"
    if reason:
        skip = pytest.mark.skip(reason=reason)
        for item in db_items:
            item.add_marker(skip)


@pytest.fixture
def db_engine():
    """Engine do banco de teste com schemas limpos. Recusa qualquer banco que não seja de teste."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL não definido")
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        raise RuntimeError(
            f"Recusando rodar testes no banco '{database}': o nome deve terminar em _test"
        )

    engine = create_engine(url)
    with engine.begin() as conn:
        for schema in ("silver", "gold", "gold_staging", "gold_intermediate"):
            conn.execute(text(f"drop schema if exists {schema} cascade"))
    yield engine
    engine.dispose()
