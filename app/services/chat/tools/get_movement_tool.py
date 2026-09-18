from sqlalchemy.orm import Session

from app.schemas.chat import GetMovementArgs
from app.services import ticker_data
from app.services.chat.formatting import compact_movement


class GetMovementTool:
    name = "get_movement"
    description = (
        "Everything stored about one movement on one date: price and benchmark stats, the explanation, and every "
        "article considered (all tiers) with excerpts and relevance scores. Use for a deep dive on a specific day."
    )
    args_model = GetMovementArgs

    def run(self, session: Session, args: GetMovementArgs) -> dict:
        ticker = ticker_data.normalize_ticker(args.ticker)
        movement = ticker_data.get_movement_detail(session, ticker, args.date)
        return compact_movement(movement, max_articles=None, with_snippets=True)
