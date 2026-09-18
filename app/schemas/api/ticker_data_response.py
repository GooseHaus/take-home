from pydantic import BaseModel

from app.schemas.api.ingest_job_response import IngestJobResponse
from app.schemas.api.movement_response import MovementResponse
from app.schemas.api.price_response import PriceResponse
from app.schemas.api.ticker_summary_response import TickerSummaryResponse
from app.schemas.movement_filters import MovementFilters


class TickerDataResponse(BaseModel):
    summary: TickerSummaryResponse
    latest_ingest: IngestJobResponse | None
    filters: MovementFilters
    total_movements: int
    movements: list[MovementResponse]
    prices: list[PriceResponse] | None
