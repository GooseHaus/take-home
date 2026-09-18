from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import ExplanationCategory


class ExplanationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str
    category: ExplanationCategory
    confidence: float
    model: str
    created_at: datetime
