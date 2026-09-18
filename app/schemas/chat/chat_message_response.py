from datetime import datetime

from pydantic import BaseModel


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime
