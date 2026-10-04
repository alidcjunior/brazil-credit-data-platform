"""Gráfico Selic x IPCA a partir do gold."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from sqlalchemy import Engine, text  # noqa: E402

SELIC_LABEL = "Meta Selic (% a.a.)"
IPCA_LABEL = "IPCA 12 meses (%)"
SOURCE_NOTE = "Fonte: BCB/SGS (séries 432 e 433). Meta Selic no último dia do mês."

_GOLD_QUERY = text(
    """
    SELECT ref_month, selic_target_eom, ipca_12m
    FROM gold.fct_monthly_macro_indicators
    ORDER BY ref_month
    """
)


def read_gold(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(_GOLD_QUERY, conn)
    df["ref_month"] = pd.to_datetime(df["ref_month"])
    return df.astype({"selic_target_eom": float, "ipca_12m": float})


def render_chart(df: pd.DataFrame, output: Path) -> Figure:
    """Desenha Selic e IPCA 12m no mesmo eixo de tempo e salva em PNG."""
    if df.empty:
        raise ValueError("Sem dados no gold para desenhar o gráfico")
    first, last = df["ref_month"].min(), df["ref_month"].max()

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    ax.step(
        df["ref_month"], df["selic_target_eom"], where="post", label=SELIC_LABEL, color="#1f5aa6"
    )
    ax.plot(df["ref_month"], df["ipca_12m"], label=IPCA_LABEL, color="#d1495b")
    ax.set_title(f"Juros e inflação no Brasil: {first:%m/%Y} a {last:%m/%Y}")
    ax.set_xlabel("Mês")
    ax.set_ylabel("%")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", frameon=False)
    fig.text(0.01, 0.01, SOURCE_NOTE, fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    plt.close(fig)
    return fig
