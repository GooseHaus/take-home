"""The tools the chat model can call. Adding one = one tool class + one entry here."""

from app.services.chat.tools.chat_tool import ChatTool
from app.services.chat.tools.get_movement_tool import GetMovementTool
from app.services.chat.tools.list_movements_tool import ListMovementsTool
from app.services.chat.tools.list_tickers_tool import ListTickersTool
from app.services.chat.tools.price_summary_tool import PriceSummaryTool
from app.services.chat.tools.search_articles_tool import SearchArticlesTool

CHAT_TOOLS: list[ChatTool] = [
    ListTickersTool(),
    ListMovementsTool(),
    GetMovementTool(),
    SearchArticlesTool(),
    PriceSummaryTool(),
]
