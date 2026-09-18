"""Ingest-pipeline constants (D7)."""

# Concurrent outbound calls. Only network I/O is parallel; all DB writes stay on the pipeline's own thread (SQLite).
NEWS_MAX_WORKERS = 4
LLM_MAX_WORKERS = 6

MAX_ERRORS_RECORDED = 20
