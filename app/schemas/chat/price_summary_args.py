from datetime import date

from pydantic import BaseModel, Field


class PriceSummaryArgs(BaseModel):
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    start: date | None = Field(None, description="First day of the period. Default: start of stored history")
    end: date | None = Field(None, description="Last day of the period. Default: end of stored history")
