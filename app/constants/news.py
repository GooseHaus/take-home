"""News-search constants (D5)."""

# Exa /search options. One contents mode only: stacking text/summary multiplies billing.
EXA_SEARCH_TYPE = "auto"
EXA_CATEGORY = "news"
EXA_CONTENTS = {"highlights": True}

RESULTS_PER_SEARCH = 8
COST_DECIMALS = 4

# Highlights arrive with page chrome and ragged whitespace; snippets are cleaned and capped before storage
SNIPPET_MAX_CHARS = 600
TITLE_MAX_CHARS = 300

# Query-string keys that vary per share link but not per article
TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = frozenset({"fbclid", "gclid", "ref", "cmpid", "mod", "src"})
