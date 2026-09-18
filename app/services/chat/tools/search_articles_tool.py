from sqlalchemy.orm import Session

from app.constants.chat import TOOL_SNIPPET_CHARS
from app.repositories.article_queries import search_articles
from app.schemas.chat import SearchArticlesArgs
from app.services import ticker_data
from app.utils.text import clean_text


class SearchArticlesTool:
    name = "search_articles"
    description = (
        "Keyword search over stored news articles (titles and excerpts), across all tickers or one. Returns each "
        "article with the movements it was linked to. Use for theme questions like 'which moves involved tariffs?'."
    )
    args_model = SearchArticlesArgs

    def run(self, session: Session, args: SearchArticlesArgs) -> dict:
        ticker = ticker_data.normalize_ticker(args.ticker) if args.ticker else None
        matches = search_articles(session, args.query, ticker, args.start, args.end, args.tier, args.limit)
        return {
            "query": args.query,
            "returned": len(matches),
            "articles": [
                {
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "published": article.published_at.date().isoformat() if article.published_at else None,
                    "excerpt": clean_text(article.snippet, TOOL_SNIPPET_CHARS),
                    "linked_movements": [
                        {"ticker": m.ticker, "date": m.date.isoformat(), "pct_change": round(m.pct_change, 2)}
                        for m in movements
                    ],
                }
                for article, movements in matches
            ],
        }
