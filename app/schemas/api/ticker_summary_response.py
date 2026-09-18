from datetime import date

from pydantic import BaseModel

from app.schemas.api.company_response import CompanyResponse


class TickerSummaryResponse(BaseModel):
    company: CompanyResponse
    first_price_date: date | None
    last_price_date: date | None
    movement_count: int
    explained_count: int
