from pydantic import BaseModel, Field

from app.enums import ExplanationCategory
from app.schemas.llm.article_relevance import ArticleRelevance


class ExplanationOutput(BaseModel):
    summary: str = Field(description="2-4 sentences explaining the move, grounded only in the supplied evidence")
    category: ExplanationCategory
    confidence: float = Field(description="0 to 1: how well the evidence supports this explanation")
    article_relevance: list[ArticleRelevance] = Field(description="One entry per candidate article")
