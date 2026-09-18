from pydantic import Field

from app.schemas.movement_filters import MovementFilters


class TickerDataQuery(MovementFilters):
    """Query string of `GET /tickers/{ticker}`: the shared movement filters plus one response-shaping flag.

    A subclass rather than an extra endpoint parameter because FastAPI only reads a Pydantic model from the query
    string when it is the endpoint's sole query parameter.
    """

    include_prices: bool = Field(True, description="Include daily price bars for the analysed period")

    def movement_filters(self) -> MovementFilters:
        return MovementFilters(**self.model_dump(include=set(MovementFilters.model_fields)))
