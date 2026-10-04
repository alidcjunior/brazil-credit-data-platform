from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from brcredit.silver.loader import SilverParseError, dedupe_latest, parse_captures

EARLY = datetime(2026, 10, 1, tzinfo=UTC)
LATE = datetime(2026, 10, 4, tzinfo=UTC)


def _bronze(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["data", "valor", "series_code", "extracted_at", "run_id"]
    ).astype({"extracted_at": "datetime64[us, UTC]"})


def test_parses_brazilian_date_and_decimal_value():
    parsed = parse_captures(_bronze([("12/07/2012", "8.00", 432, LATE, "RUN1")]))
    row = parsed.iloc[0]
    assert row["ref_date"] == date(2012, 7, 12)
    assert row["value"] == Decimal("8.00")
    assert row["series_code"] == 432
    assert row["source_run_id"] == "RUN1"
    assert row["source_extracted_at"] == LATE


def test_negative_values_are_valid():
    parsed = parse_captures(_bronze([("01/08/2026", "-0.32", 433, LATE, "RUN1")]))
    assert parsed.iloc[0]["value"] == Decimal("-0.32")


@pytest.mark.parametrize("valor", ["", "abc", "1,5", "NaN", "Infinity"])
def test_non_numeric_value_names_the_run(valor):
    with pytest.raises(SilverParseError, match="RUN9"):
        parse_captures(_bronze([("01/06/2012", valor, 432, LATE, "RUN9")]))


def test_invalid_date_names_the_run():
    with pytest.raises(SilverParseError, match="RUN9"):
        parse_captures(_bronze([("2012-06-01", "8.50", 432, LATE, "RUN9")]))


def test_empty_input_gives_empty_output():
    parsed = parse_captures(_bronze([]))
    assert parsed.empty
    assert "ref_date" in parsed.columns


def test_latest_capture_wins_for_same_key():
    parsed = parse_captures(
        _bronze(
            [
                ("01/06/2012", "8.50", 432, EARLY, "OLD"),
                ("01/06/2012", "8.75", 432, LATE, "NEW"),
                ("02/06/2012", "8.50", 432, EARLY, "OLD"),
            ]
        )
    )
    deduped = dedupe_latest(parsed).set_index("ref_date")
    assert len(deduped) == 2
    assert deduped.loc[date(2012, 6, 1), "value"] == Decimal("8.75")
    assert deduped.loc[date(2012, 6, 1), "source_run_id"] == "NEW"
    assert deduped.loc[date(2012, 6, 2), "source_run_id"] == "OLD"


def test_same_date_in_different_series_is_kept():
    parsed = parse_captures(
        _bronze(
            [
                ("01/06/2012", "8.50", 432, LATE, "RUN1"),
                ("01/06/2012", "0.08", 433, LATE, "RUN1"),
            ]
        )
    )
    assert len(dedupe_latest(parsed)) == 2
