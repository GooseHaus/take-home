from pydantic import BaseModel, Field


class PeerSuggestion(BaseModel):
    name: str = Field(description="Company name")
    ticker: str | None = Field(description="Yahoo Finance ticker symbol, or null if the company is not listed")
