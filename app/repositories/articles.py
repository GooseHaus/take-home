from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import ArticleHit
from app.models import Article


def upsert_articles(session: Session, hits: list[ArticleHit]) -> list[Article]:
    """Persist hits, deduping on URL against both the database and the batch itself. Order follows `hits`.

    Existing rows are kept as-is: the same article found by a later search shouldn't churn stored text.
    """
    urls = list(dict.fromkeys(hit.url for hit in hits))
    if not urls:
        return []
    existing = {a.url: a for a in session.scalars(select(Article).where(Article.url.in_(urls)))}

    for hit in hits:
        if hit.url not in existing:
            existing[hit.url] = Article(
                url=hit.url, title=hit.title, source=hit.source, published_at=hit.published_at, snippet=hit.snippet
            )
            session.add(existing[hit.url])
    session.flush()  # assign ids
    return [existing[url] for url in urls]


def get_articles(session: Session, article_ids: list[int]) -> list[Article]:
    """Articles in the order of `article_ids` (provider ranking), skipping ids that no longer exist."""
    if not article_ids:
        return []
    by_id = {a.id: a for a in session.scalars(select(Article).where(Article.id.in_(article_ids)))}
    return [by_id[i] for i in article_ids if i in by_id]
