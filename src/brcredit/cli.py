"""CLI `brcredit`."""

import logging
from datetime import date, datetime
from typing import Annotated

import typer

from brcredit.bronze.writer import new_run_id, write_capture
from brcredit.catalog import SERIES, get_series
from brcredit.config import get_settings
from brcredit.sources.bcb_sgs import SgsClient, SgsError

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
