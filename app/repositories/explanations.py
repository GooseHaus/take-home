from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Explanation, Movement, MovementArticle
from app.schemas.llm import ExplanationOutput


def save_explanation(session: Session, movement: Movement, output: ExplanationOutput, model: str) -> Explanation:
    """Store the verdict and copy per-article relevance onto the links. Ids the model made up are ignored."""
    explanation = session.get(Explanation, movement.id) or Explanation(movement_id=movement.id)
    explanation.summary = output.summary.strip()
    explanation.category = output.category
    explanation.confidence = _clamp(output.confidence)
    explanation.model = model
    session.add(explanation)

    links = {
        link.article_id: link
        for link in session.scalars(select(MovementArticle).where(MovementArticle.movement_id == movement.id))
    }
    for item in output.article_relevance:
        if item.article_id in links:
            links[item.article_id].relevance = _clamp(item.relevance)
    session.flush()
    return explanation


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
