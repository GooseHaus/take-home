from pydantic import Field

from app.schemas.movement_filters import MovementFilters


class TickerDataQuery(MovementFilters):
    """Query string of `GET /tickers/{ticker}`: the shared movement filters plus response-shaping flags.

    A subclass rather than extra endpoint parameters because FastAPI only reads a Pydantic model from the query
    string when it is the endpoint's sole query parameter.
    """

    include_prices: bool = Field(True, description="Include daily price bars (within start/end)")
    include_news: bool = Field(True, description="Include each movement's articles")

    def movement_filters(self) -> MovementFilters:
        return MovementFilters(**self.model_dump(include=set(MovementFilters.model_fields)))
