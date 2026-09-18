from enum import StrEnum


class IngestStage(StrEnum):
    """Where an ingest job currently is; exposed by the status endpoint."""

    PRICES = "prices"
    MOVEMENTS = "movements"
    NEWS = "news"
    EXPLANATIONS = "explanations"
    COMPLETE = "complete"
