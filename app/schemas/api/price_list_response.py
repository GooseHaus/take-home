from datetime import date

from pydantic import BaseModel

from app.schemas.api.price_response import PriceResponse


class PriceListResponse(BaseModel):
    ticker: str
    start: date | None
    end: date | None
    prices: list[PriceResponse]
