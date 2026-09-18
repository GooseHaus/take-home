"""SQLAlchemy tables, one class per module. Import from here: `from app.models import Price`."""

from app.models.article import Article
from app.models.chat_message import ChatMessage
from app.models.company import Company
from app.models.explanation import Explanation
from app.models.ingest_job import IngestJob
from app.models.movement import Movement
from app.models.movement_article import MovementArticle
from app.models.news_search_cache import NewsSearchCache
from app.models.price import Price

__all__ = [
    "Article",
    "ChatMessage",
    "Company",
    "Explanation",
    "IngestJob",
    "Movement",
    "MovementArticle",
    "NewsSearchCache",
    "Price",
]
