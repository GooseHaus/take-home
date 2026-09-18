from datetime import datetime

from pydantic import BaseModel

from app.enums import NewsTier


class ArticleResponse(BaseModel):
    id: int
    url: str
    title: str
    source: str | None
    published_at: datetime | None
    snippet: str | None
    tier: NewsTier
    relevance: float | None
    cited: bool
