from pydantic import Field

from app.constants.chat import TOOL_DEFAULT_MOVEMENTS, TOOL_MAX_MOVEMENTS
from app.schemas.movement_filters import MovementFilters


class ListMovementsArgs(MovementFilters):
    """The REST filters plus the ticker. The page size is smaller because tool output goes into the prompt."""

    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    limit: int = Field(TOOL_DEFAULT_MOVEMENTS, ge=1, le=TOOL_MAX_MOVEMENTS)

    def movement_filters(self) -> MovementFilters:
        return MovementFilters(**self.model_dump(include=set(MovementFilters.model_fields)))
