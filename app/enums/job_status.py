from enum import StrEnum


class JobStatus(StrEnum):
    """Lifecycle of an ingest job."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
