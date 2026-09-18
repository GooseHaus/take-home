import datetime as dt

from pydantic import BaseModel, Field


class GetMovementArgs(BaseModel):
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    date: dt.date = Field(description="The movement's date, YYYY-MM-DD")
