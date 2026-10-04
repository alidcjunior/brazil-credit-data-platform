"""CLI `brcredit`."""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from brcredit.bronze.writer import new_run_id, write_capture
from brcredit.catalog import SERIES, get_series
from brcredit.config import get_settings
from brcredit.sources.bcb_sgs import SgsClient, SgsError

DEFAULT_CHART_PATH = Path("docs/img/selic_vs_ipca.png")

logger = logging.getLogger("brcredit")

app = typer.Typer(help="Brazil Credit & Economy Data Platform", no_args_is_help=True)
ingest_app = typer.Typer(help="Captura de fontes para o bronze", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Logs em nível DEBUG")] = False,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def make_sgs_client() -> SgsClient:
    return SgsClient()


@ingest_app.command("sgs")
def ingest_sgs(
    serie: Annotated[
        list[int] | None,
        typer.Option(help="Código SGS (repetível). Padrão: todas as séries do catálogo."),
    ] = None,
    start: Annotated[
        datetime | None,
        typer.Option(formats=["%Y-%m-%d"], help="Data inicial. Padrão: início de cada série."),
    ] = None,
    end: Annotated[
        datetime | None,
        typer.Option(formats=["%Y-%m-%d"], help="Data final. Padrão: hoje."),
    ] = None,
) -> None:
    """Captura séries do BCB SGS e grava uma execução imutável no bronze."""
    codes = serie or sorted(SERIES)
    try:
        catalog = [get_series(code) for code in codes]
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--serie") from None

    today = date.today()
    end_date = end.date() if end else today
    if end_date > today:
        raise typer.BadParameter(f"{end_date} está no futuro", param_hint="--end")
    plan = []
    for series in catalog:
        start_date = start.date() if start else series.default_start
        if start_date > end_date:
            raise typer.BadParameter(
                f"{start_date} é posterior à data final {end_date}", param_hint="--start"
            )
        plan.append((series, start_date))

    data_dir = get_settings().data_dir
    run_id = new_run_id()
    failed: list[int] = []
    with make_sgs_client() as client:
        for series, start_date in plan:
            try:
                summary = write_capture(
                    data_dir,
                    series.code,
                    run_id,
                    client.fetch_series(series.code, start_date, end_date),
                )
            except SgsError as exc:
                logger.error("Série %s não capturada: %s", series.code, exc)
                failed.append(series.code)
                continue
            typer.echo(
                f"{series.code}  {start_date} → {end_date}  {summary.windows} janelas  "
                f"{summary.rows:>5} linhas  {summary.path.as_posix()}"
            )

    if failed:
        typer.echo(f"Falha na captura das séries: {', '.join(map(str, failed))}", err=True)
        raise typer.Exit(code=1)


def _connected_engine() -> Engine:
    from sqlalchemy import text

    from brcredit.db import get_engine

    settings = get_settings()
    engine = get_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except OperationalError:
        typer.echo(
            "Postgres não responde em DATABASE_URL. Suba o banco com: docker compose up -d --wait",
            err=True,
        )
        raise typer.Exit(code=1) from None
    return engine


@app.command("init-db")
def init_db_cmd() -> None:
    """Cria schemas e tabelas do silver (idempotente)."""
    from brcredit.db import init_db

    init_db(_connected_engine())
    typer.echo("Silver pronto: silver.sgs_series, silver.sgs_observation")


@app.command("load-silver")
def load_silver_cmd() -> None:
    """Carrega todas as capturas do bronze no silver (upsert idempotente)."""
    from brcredit.silver.loader import load_silver

    result = load_silver(_connected_engine(), get_settings().data_dir)
    typer.echo(
        f"silver.sgs_observation: {result.inserted} inseridas, {result.updated} atualizadas, "
        f"{result.unchanged} sem alteração"
    )


@app.command("build-gold")
def build_gold_cmd() -> None:
    """Roda `dbt build` (modelos + testes de dados) no projeto dbt/."""
    from dbt.cli.main import dbtRunner
    from dotenv import load_dotenv

    load_dotenv()  # o profile do dbt lê POSTGRES_* do ambiente
    project_dir = get_settings().dbt_project_dir
    profiles = project_dir / "profiles.yml"
    if not profiles.exists():
        typer.echo(f"{profiles} não existe. Copie de {profiles}.example", err=True)
        raise typer.Exit(code=1)
    result = dbtRunner().invoke(
        ["build", "--project-dir", str(project_dir), "--profiles-dir", str(project_dir)]
    )
    if not result.success:
        typer.echo("dbt build falhou: veja os modelos/testes com erro acima", err=True)
        raise typer.Exit(code=1)
    typer.echo("Gold pronto: gold.fct_monthly_macro_indicators")


@app.command("chart")
def chart_cmd(
    output: Annotated[Path, typer.Option(help="Arquivo PNG de saída.")] = DEFAULT_CHART_PATH,
) -> None:
    """Gera o gráfico Selic x IPCA 12 meses a partir do gold."""
    from brcredit.chart import read_gold, render_chart

    render_chart(read_gold(_connected_engine()), output)
    typer.echo(f"Gráfico salvo em {output.as_posix()}")


@app.command("run")
def run_cmd(
    serie: Annotated[list[int] | None, typer.Option(help="Código SGS (repetível).")] = None,
    start: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    end: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
) -> None:
    """Fluxo completo: ingest sgs → init-db → load-silver → build-gold → chart."""
    ingest_sgs(serie=serie, start=start, end=end)
    init_db_cmd()
    load_silver_cmd()
    build_gold_cmd()
    chart_cmd(output=DEFAULT_CHART_PATH)
