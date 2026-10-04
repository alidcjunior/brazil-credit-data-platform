import pandas as pd
import pytest

from brcredit.chart import IPCA_LABEL, SELIC_LABEL, SOURCE_NOTE, render_chart


@pytest.fixture
def gold() -> pd.DataFrame:
    months = pd.date_range("2012-06-01", periods=24, freq="MS")
    return pd.DataFrame(
        {
            "ref_month": months,
            "selic_target_eom": [8.5 - 0.05 * i for i in range(24)],
            "ipca_12m": [5.0 + 0.1 * i for i in range(24)],
        }
    )


def test_renders_non_empty_png(gold, tmp_path):
    output = tmp_path / "img" / "chart.png"
    render_chart(gold, output)
    assert output.read_bytes().startswith(b"\x89PNG")
    assert output.stat().st_size > 10_000


def test_chart_has_title_legend_and_source(gold, tmp_path):
    fig = render_chart(gold, tmp_path / "chart.png")
    ax = fig.axes[0]
    assert "06/2012 a 05/2014" in ax.get_title()
    assert [t.get_text() for t in ax.get_legend().get_texts()] == [SELIC_LABEL, IPCA_LABEL]
    assert ax.get_ylabel() == "%"
    assert SOURCE_NOTE in [t.get_text() for t in fig.texts]


def test_empty_gold_raises(tmp_path):
    empty = pd.DataFrame(columns=["ref_month", "selic_target_eom", "ipca_12m"])
    with pytest.raises(ValueError, match="Sem dados"):
        render_chart(empty, tmp_path / "chart.png")
