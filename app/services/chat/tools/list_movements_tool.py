from sqlalchemy.orm import Session

from app.constants.chat import TOOL_ARTICLES_PER_MOVEMENT
from app.schemas.chat import ListMovementsArgs
from app.services import ticker_data
from app.services.chat.formatting import compact_movement


class ListMovementsTool:
    name = "list_movements"
    description = (
        "Find a ticker's major single-day price movements and why they happened. Filter by date range, direction, "
        "size, explanation category (company/industry/macro/unexplained) or confidence; sort by date or magnitude. "
        "Each movement comes with its explanation and its most relevant articles. Start here for most questions."
    )
    args_model = ListMovementsArgs

    def run(self, session: Session, args: ListMovementsArgs) -> dict:
        ticker = ticker_data.normalize_ticker(args.ticker)
        data = ticker_data.get_ticker_data(session, ticker, args.movement_filters(), include_prices=False)
        return {
            "ticker": ticker,
            "company": data.summary.company.name,
            "total_matching": data.total_movements,
            "returned": len(data.movements),
            "movements": [compact_movement(m, TOOL_ARTICLES_PER_MOVEMENT) for m in data.movements],
        }
