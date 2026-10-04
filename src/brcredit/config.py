"""Configuração lida de variáveis de ambiente e do arquivo .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://brcredit:brcredit@localhost:5432/brcredit"
    data_dir: Path = Path("data")
    dbt_project_dir: Path = Path("dbt")


def get_settings() -> Settings:
    return Settings()
