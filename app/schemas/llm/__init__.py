"""Shapes the LLM must return (structured output). Enums here are the same ones the DB and API use."""

from app.schemas.llm.article_relevance import ArticleRelevance
from app.schemas.llm.explanation_output import ExplanationOutput

__all__ = ["ArticleRelevance", "ExplanationOutput"]
