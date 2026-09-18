"""Shapes the LLM must return (structured output). Enums here are the same ones the DB and API use."""

from app.schemas.llm.article_relevance import ArticleRelevance
from app.schemas.llm.explanation_output import ExplanationOutput
from app.schemas.llm.peer_suggestion import PeerSuggestion
from app.schemas.llm.peers_output import PeersOutput

__all__ = ["ArticleRelevance", "ExplanationOutput", "PeerSuggestion", "PeersOutput"]
