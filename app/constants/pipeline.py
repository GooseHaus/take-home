"""Ingest-pipeline constants (D7)."""

# Concurrent outbound calls. Only network I/O is parallel; all DB writes stay on the pipeline's own thread (SQLite).
NEWS_MAX_WORKERS = 4
LLM_MAX_WORKERS = 6

MAX_ERRORS_RECORDED = 20

# How long a connection waits for SQLite's single write lock before failing with "database is locked"
SQLITE_BUSY_TIMEOUT_SECONDS = 30

# News keeps arriving after a move. A cached search is final only if it ran at least this many days after its window
# closed; until then a re-ingest runs it again (D19).
NEWS_SETTLE_DAYS = 2

# Moves this recent are always explained, even when they are not among the N largest in the range (D19)
RECENT_MOVE_DAYS = 7
