from dataclasses import dataclass, field

from app.domain.article_hit import ArticleHit


@dataclass(frozen=True)
class NewsSearchResult:
    hits: list[ArticleHit] = field(default_factory=list)
    cost_dollars: float | None = None
