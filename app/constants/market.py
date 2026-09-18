"""Market-data constants."""

MARKET_TICKER = "SPY"

# yfinance sector name -> SPDR sector ETF
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# Extra calendar days fetched before the requested start so trailing-volatility stats are warm on day one
WARMUP_DAYS = 100

DEFAULT_LOOKBACK_DAYS = 365

# SQLite caps bound variables per statement
PRICE_UPSERT_CHUNK_SIZE = 500
