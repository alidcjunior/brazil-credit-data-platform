from datetime import date

import pytest

from brcredit.catalog import SERIES, get_series


def test_selic_target_series():
    selic = get_series(432)
    assert selic.periodicity == "daily"
    assert selic.unit == "% a.a."
    assert selic.default_start == date(2012, 6, 1)


def test_ipca_starts_twelve_months_before_analysis():
    ipca = get_series(433)
    assert ipca.periodicity == "monthly"
    assert ipca.default_start == date(2011, 6, 1)


def test_unknown_series_lists_valid_codes():
    with pytest.raises(ValueError, match="432, 433"):
        get_series(1)


def test_catalog_keys_match_codes():
    assert all(code == s.code for code, s in SERIES.items())
