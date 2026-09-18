from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.constants.api import MAX_LOOKBACK_DAYS, MAX_PAGE_SIZE


class IngestRequest(BaseModel):
    """All fields optional: an empty body ingests the last year at the configured threshold."""

    start: date | None = Field(None, description="First day to analyse. Default: `lookback_days` before `end`")
    end: date | None = Field(None, description="Last day to analyse. Default: today")
    lookback_days: int | None = Field(None, ge=1, le=MAX_LOOKBACK_DAYS, description="Used when `start` is omitted")
    threshold_pct: float | None = Field(None, gt=0, description="Major-movement cutoff in percent. Default: 2.0")
    max_movements: int | None = Field(
        None, ge=1, le=MAX_PAGE_SIZE, description="Cost guard: how many of the largest moves get news + explanation"
    )
    refresh: bool = Field(False, description="Re-explain movements that already have an explanation")

    @model_validator(mode="after")
    def check_dates(self) -> "IngestRequest":
        if self.start and self.lookback_days:
            raise ValueError("give either start or lookback_days, not both")
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end")
        return self
