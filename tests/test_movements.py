from datetime import date

import pytest

from app.enums import DriverHint
from app.services.movements import benchmark_explains, detect_movements, driver_hint, news_window
from tests.factories import price_frame as frame


def test_threshold_is_inclusive_and_symmetric():
    prices = frame([100, 102, 99.96, 101.0])  # +2.0%, -2.0%, +1.04%
    moves = detect_movements(prices, None, None, threshold_pct=2.0)
    assert [m.pct_change for m in moves] == [2.0, -2.0]


def test_below_threshold_is_ignored():
    prices = frame([100, 101.99, 100.0])
    assert detect_movements(prices, None, None, threshold_pct=2.0) == []


def test_first_day_has_no_return_and_is_never_a_movement():
    prices = frame([100, 110])
    moves = detect_movements(prices, None, None, threshold_pct=2.0)
    assert len(moves) == 1 and moves[0].prev_close == 100 and moves[0].close == 110


def test_zscore_is_none_during_warmup_then_populated():
    closes = [100.0]
    for i in range(40):
        closes.append(closes[-1] * (1.005 if i % 2 else 0.995))
    closes[5] = closes[4] * 1.05  # early spike: inside warm-up
    closes.append(closes[-1] * 1.05)  # late spike: warm
    moves = detect_movements(frame(closes), None, None, threshold_pct=4.0)
    early, late = moves[0], moves[-1]
    assert early.zscore is None
    assert late.zscore is not None and late.zscore > 3


def test_zscore_excludes_the_day_itself():
    closes = [100.0]
    for i in range(30):
        closes.append(closes[-1] * (1.002 if i % 2 else 0.998))
    closes.append(closes[-1] * 1.10)
    move = detect_movements(frame(closes), None, None, threshold_pct=5.0)[0]
    # ~0.2% daily vol -> a 10% day is tens of sigmas; it would be ~5 if the spike polluted its own window
    assert move.zscore > 20


def test_volume_ratio():
    prices = frame([100] * 10 + [105], volumes=[1_000] * 10 + [3_000])
    move = detect_movements(prices, None, None, threshold_pct=2.0)[0]
    assert move.volume_ratio == pytest.approx(3.0)


def test_start_end_limit_reporting_but_not_history():
    prices = frame([100, 105, 100, 105])
    days = list(prices.index)
    moves = detect_movements(prices, None, None, threshold_pct=2.0, start=days[2], end=days[2])
    assert [m.date for m in moves] == [days[2]]
    assert moves[0].prev_close == 105  # return still computed from the out-of-range prior day


@pytest.mark.parametrize(
    "pct, market, sector, expected",
    [
        (-3.0, -2.5, -2.8, DriverHint.MARKET),  # everything fell
        (-6.0, -2.5, None, DriverHint.MARKET),  # high-beta amplification: market covers >=40% of the move
        (-10.0, -1.2, -1.0, DriverHint.IDIOSYNCRATIC),  # small market dip can't explain a 10% drop
        (-3.0, -0.2, -2.4, DriverHint.SECTOR),  # sector sold off, market flat
        (4.0, -1.5, -2.0, DriverHint.IDIOSYNCRATIC),  # rose against a falling tape
        (3.0, 0.4, 0.6, DriverHint.IDIOSYNCRATIC),  # benchmarks barely moved
        (3.0, None, None, DriverHint.IDIOSYNCRATIC),  # no benchmark data
    ],
)
def test_driver_hint(pct, market, sector, expected):
    assert driver_hint(pct, market, sector) == expected


def test_benchmark_must_move_in_same_direction():
    assert not benchmark_explains(3.0, -3.0)


def test_excess_returns_and_benchmark_alignment():
    prices = frame([100, 97])
    market = frame([400, 392])  # -2.0%
    sector = frame([200, 199])  # -0.5%
    move = detect_movements(prices, market, sector, threshold_pct=2.0)[0]
    assert move.market_pct_change == pytest.approx(-2.0)
    assert move.excess_vs_market == pytest.approx(-1.0)
    assert move.excess_vs_sector == pytest.approx(-2.5)
    assert move.driver_hint is DriverHint.MARKET


def test_missing_benchmark_day_gives_none_not_error():
    prices = frame([100, 97, 100])
    market = frame([400, 392])  # one day short
    moves = detect_movements(prices, market, None, threshold_pct=2.0)
    assert moves[1].market_pct_change is None and moves[1].excess_vs_market is None


def test_news_window_spans_the_weekend_for_a_monday_move():
    friday, monday = date(2026, 1, 9), date(2026, 1, 12)
    assert news_window(monday, friday) == (friday, date(2026, 1, 13))


def test_detected_window_uses_previous_trading_day():
    prices = frame([100, 100, 100, 100, 100, 105], start=date(2026, 1, 5))  # Mon..Fri, then Mon
    move = detect_movements(prices, None, None, threshold_pct=2.0)[0]
    assert move.date.weekday() == 0 and move.window_start.weekday() == 4


def test_zero_volume_history_gives_no_ratio_instead_of_infinity():
    prices = frame([100] * 6 + [105], volumes=[0] * 6 + [500])
    (move,) = detect_movements(prices, None, None, threshold_pct=2.0)
    assert move.volume_ratio is None


def test_a_move_from_a_zero_close_is_not_a_movement():
    assert detect_movements(frame([0.0, 5.0, 5.0]), None, None, threshold_pct=2.0) == []
