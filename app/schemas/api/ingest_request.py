from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.constants.api import MAX_LOOKBACK_DAYS, MAX_MOVEMENTS_PER_INGEST, MIN_THRESHOLD_PCT


class IngestRequest(BaseModel):
    """All fields optional: an empty body ingests the last year at the configured threshold."""

    start: date | None = Field(None, description="First day to analyse. Default: `lookback_days` before `end`")
    end: date | None = Field(None, description="Last day to analyse. Default: today")
    lookback_days: int | None = Field(None, ge=1, le=MAX_LOOKBACK_DAYS, description="Used when `start` is omitted")
    threshold_pct: float | None = Field(
        None, ge=MIN_THRESHOLD_PCT, description="Major-movement cutoff in percent. Default: 2.0"
    )
    max_movements: int | None = Field(
        None,
        ge=1,
        le=MAX_MOVEMENTS_PER_INGEST,
        description="Cost guard: how many of the largest moves get news + explanation",
    )
    refresh: bool = Field(False, description="Re-explain movements that already have an explanation")

    @model_validator(mode="after")
    def check_dates(self) -> "IngestRequest":
        if self.start and self.lookback_days:
            raise ValueError("give either start or lookback_days, not both")
        today = date.today()
        if (self.start and self.start > today) or (self.end and self.end > today):
            raise ValueError("start and end cannot be in the future")
        end = self.end or today
        if self.start and self.start > end:
            raise ValueError("start must be on or before end")
        if self.start and (end - self.start).days > MAX_LOOKBACK_DAYS:
            raise ValueError(f"the period cannot be longer than {MAX_LOOKBACK_DAYS} days")
        return self
