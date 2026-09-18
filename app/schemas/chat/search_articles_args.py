from datetime import date

from pydantic import BaseModel, Field

from app.constants.chat import TOOL_SEARCH_DEFAULT, TOOL_SEARCH_MAX
from app.enums import NewsTier


class SearchArticlesArgs(BaseModel):
    query: str = Field(
        min_length=2, description="Keyword or short phrase to find in article titles and excerpts, e.g. 'tariff'"
    )
    ticker: str | None = Field(None, description="Only articles linked to this ticker's movements")
    start: date | None = Field(None, description="Earliest publication date")
    end: date | None = Field(None, description="Latest publication date")
    tier: NewsTier | None = Field(None, description="Only articles found by this search tier")
    limit: int = Field(TOOL_SEARCH_DEFAULT, ge=1, le=TOOL_SEARCH_MAX)
