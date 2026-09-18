"""API constants."""

API_VERSION = "1.0.0"

OPENAPI_TAGS = [
    {"name": "tickers", "description": "Ingest a ticker and read its prices, major movements, explanations and news."},
    {"name": "chat", "description": "Ask questions about the stored data. Answers come from read-only tool calls."},
    {"name": "health", "description": "Service status."},
]

TICKER_PATTERN = r"^[A-Z0-9][A-Z0-9.\-]{0,11}$"

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

MAX_LOOKBACK_DAYS = 365 * 5

# Bounds on what one unauthenticated ingest request can spend. Each explained move is 3 searches and 1 LLM call.
MAX_MOVEMENTS_PER_INGEST = 50
# Below this nearly every trading day counts as a "major" move
MIN_THRESHOLD_PCT = 0.5
