"""News-search constants (D5)."""

# Exa /search options. One contents mode only: stacking text/summary multiplies billing.
EXA_SEARCH_TYPE = "auto"
EXA_CATEGORY = "news"
EXA_CONTENTS = {"highlights": True}

# Results requested per search, by tier. The sum is what one explanation prompt can see.
COMPANY_RESULTS = 8
INDUSTRY_RESULTS = 5
MACRO_RESULTS = 5

MAX_PEERS = 4
QUERY_DIGEST_CHARS = 8
MACRO_CACHE_SCOPE = "global"
MACRO_QUERY = (
    "What moved the stock market today: Wall Street, Federal Reserve, interest rates, inflation, economy, geopolitics"
)
COST_DECIMALS = 4

# Highlights arrive with page chrome and ragged whitespace; snippets are cleaned and capped before storage
SNIPPET_MAX_CHARS = 600
TITLE_MAX_CHARS = 300

# Query-string keys that vary per share link but not per article
TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = frozenset({"fbclid", "gclid", "ref", "cmpid", "mod", "src"})
