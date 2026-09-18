from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArticleHit:
    """One article returned by a news provider, normalised and not yet persisted."""

    url: str
    title: str
    source: str | None
    published_at: datetime | None
    snippet: str | None
