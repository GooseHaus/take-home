from datetime import date

import pytest

from app.services.news.freshness import is_recent, is_settled

WINDOW_END = date(2026, 1, 13)


@pytest.mark.parametrize(
    "fetched_on, expected",
    [
        (date(2026, 1, 13), False),  # searched on the day the window closed
        (date(2026, 1, 14), False),
        (date(2026, 1, 15), True),  # two days later: next-day coverage has been published
        (date(2026, 9, 18), True),  # historical backfill
    ],
)
def test_is_settled(fetched_on, expected):
    assert is_settled(WINDOW_END, fetched_on) is expected


@pytest.mark.parametrize(
    "move_date, expected",
    [(date(2026, 1, 17), True), (date(2026, 1, 10), True), (date(2026, 1, 9), False)],
)
def test_is_recent(move_date, expected):
    assert is_recent(move_date, today=date(2026, 1, 17)) is expected
