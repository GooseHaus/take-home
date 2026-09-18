from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants.api import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.enums import ArticleScope, Direction, DriverHint, ExplanationCategory, MovementSort, NewsTier


class MovementFilters(BaseModel):
    """The one definition of how movements can be filtered.

    Used as the REST query parameters, as the chat tools' arguments (their JSON schema is generated from this model)
    and as the repository's input, so the three stay in sync.

    Movement fields choose which movements come back. Article fields only shape the article list inside each one.
    """

    # A misspelt filter is an error, not a silently unfiltered result
    model_config = ConfigDict(extra="forbid")

    start: date | None = Field(None, description="Earliest movement date (inclusive)")
    end: date | None = Field(None, description="Latest movement date (inclusive)")
    direction: Direction | None = Field(None, description="Only gains (up) or only losses (down)")
    min_abs_change: float | None = Field(None, ge=0, description="Minimum absolute daily move, in percent")
    category: ExplanationCategory | None = Field(None, description="Explanation verdict")
    driver_hint: DriverHint | None = Field(None, description="What the price data alone suggested")
    min_confidence: float | None = Field(None, ge=0, le=1, description="Minimum explanation confidence")
    explained_only: bool = Field(False, description="Drop movements that have no explanation yet")
    articles: ArticleScope = Field(
        ArticleScope.CITED,
        description="Articles to include per movement: cited (the ones the explanation relied on), all, or none",
    )
    tier: NewsTier | None = Field(None, description="Only show articles found by this search tier")
    min_relevance: float | None = Field(None, ge=0, le=1, description="Only show articles at or above this relevance")
    include_snippets: bool = Field(False, description="Include each article's text excerpt")
    sort: MovementSort = Field(MovementSort.DATE_DESC, description="Result order")
    limit: int = Field(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(0, ge=0)

    @model_validator(mode="after")
    def check_date_order(self) -> "MovementFilters":
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end")
        return self
