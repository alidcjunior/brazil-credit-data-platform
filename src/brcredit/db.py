"""Conexão com o Postgres e criação das tabelas do silver."""

from importlib import resources

from sqlalchemy import Engine, create_engine

CONNECT_TIMEOUT_SECONDS = 5


def get_engine(database_url: str) -> Engine:
    # Sem timeout, uma porta fechada no Windows pode travar a conexão por minutos.
    return create_engine(database_url, connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS})


def init_db(engine: Engine) -> None:
    ddl = resources.files("brcredit.silver").joinpath("schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)
