from datetime import date

from pydantic import BaseModel

from app.enums import DriverHint
from app.schemas.api.article_response import ArticleResponse
from app.schemas.api.explanation_response import ExplanationResponse


class MovementResponse(BaseModel):
    ticker: str
    date: date
    pct_change: float
    close: float
    prev_close: float
    zscore: float | None
    volume_ratio: float | None
    market_pct_change: float | None
    sector_pct_change: float | None
    excess_vs_market: float | None
    excess_vs_sector: float | None
    driver_hint: DriverHint
    news_window_start: date
    news_window_end: date
    explanation: ExplanationResponse | None
    articles: list[ArticleResponse]
