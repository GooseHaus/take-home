from pydantic import BaseModel, Field

from app.constants.chat import MAX_MESSAGE_CHARS


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    ticker: str | None = Field(None, description="Optional focus ticker, so questions can say 'the stock' or 'it'")
    conversation_id: str | None = Field(None, description="Continue an earlier conversation. Omit to start a new one")
