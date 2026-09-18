from dataclasses import dataclass, field
from datetime import date

from app.enums import NewsTier


@dataclass
class PlannedSearch:
    """One news search the pipeline intends to run. Movements sharing a cache_key share the search and its results."""

    cache_key: str
    tier: NewsTier
    query: str
    start: date
    end: date
    limit: int
    movement_ids: list[int] = field(default_factory=list)
