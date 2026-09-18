from pydantic import BaseModel

from app.schemas.api.movement_response import MovementResponse
from app.schemas.movement_filters import MovementFilters


class MovementListResponse(BaseModel):
    ticker: str
    filters: MovementFilters
    total_movements: int
    movements: list[MovementResponse]
