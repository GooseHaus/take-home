"""Movement-detection constants (D3, D4, D13)."""

VOL_WINDOW = 60  # trading days of trailing returns behind the z-score
VOL_MIN_PERIODS = 20
VOLUME_WINDOW = 20
VOLUME_MIN_PERIODS = 5

# A benchmark "explains" a move when it went the same way, moved meaningfully in its own right,
# and covers a fair share of the stock's move (high-beta names amplify the market, so not 1:1).
BENCHMARK_MIN_ABS_PCT = 1.0
BENCHMARK_MIN_SHARE = 0.4

# One competitor moving proves little. The peer median only counts as a benchmark with at least this many (D20)
MIN_PEERS_FOR_HINT = 2

# Published-date bounds are hard filters in the news API, so catch next-day write-ups too (D5)
WINDOW_TRAILING_DAYS = 1

PCT_DECIMALS = 4
