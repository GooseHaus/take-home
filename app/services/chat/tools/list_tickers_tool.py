from sqlalchemy.orm import Session

from app.schemas.chat import EmptyArgs
from app.services import ticker_data


class ListTickersTool:
    name = "list_tickers"
    description = "List every ticker that has been ingested, with its company profile, date range and movement counts."
    args_model = EmptyArgs

    def run(self, session: Session, args: EmptyArgs) -> dict:
        return {"tickers": [s.model_dump(mode="json") for s in ticker_data.list_ticker_summaries(session)]}
