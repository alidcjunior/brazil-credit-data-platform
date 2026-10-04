from datetime import date, timedelta

import pytest

from brcredit.sources.bcb_sgs import MAX_API_WINDOW_YEARS, Window, split_windows


def _assert_contiguous(windows: list[Window], start: date, end: date) -> None:
    assert windows[0].start == start
    assert windows[-1].end == end
    for previous, current in zip(windows, windows[1:], strict=False):
        assert current.start == previous.end + timedelta(days=1)
    assert all(w.start <= w.end for w in windows)


def test_full_history_is_split_without_gaps_or_overlap():
    start, end = date(2012, 6, 1), date(2026, 10, 4)
    windows = split_windows(start, end)
    _assert_contiguous(windows, start, end)
    assert len(windows) == 3


def test_each_window_spans_at_most_max_years():
    windows = split_windows(date(2011, 6, 1), date(2026, 10, 4), max_years=5)
    for w in windows:
        assert w.end < date(w.start.year + 5, w.start.month, w.start.day)


def test_short_period_yields_single_window():
    assert split_windows(date(2026, 1, 1), date(2026, 1, 31)) == [
        Window(date(2026, 1, 1), date(2026, 1, 31))
    ]


def test_single_day_period():
    assert split_windows(date(2026, 1, 1), date(2026, 1, 1)) == [
        Window(date(2026, 1, 1), date(2026, 1, 1))
    ]


def test_leap_day_start_is_handled():
    windows = split_windows(date(2012, 2, 29), date(2020, 1, 1), max_years=5)
    _assert_contiguous(windows, date(2012, 2, 29), date(2020, 1, 1))


def test_start_after_end_raises():
    with pytest.raises(ValueError, match="posterior"):
        split_windows(date(2026, 2, 1), date(2026, 1, 1))


def test_window_above_api_limit_is_rejected():
    with pytest.raises(ValueError, match="10"):
        split_windows(date(2012, 1, 1), date(2026, 1, 1), max_years=MAX_API_WINDOW_YEARS + 1)
