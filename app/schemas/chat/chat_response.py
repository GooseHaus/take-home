from pydantic import BaseModel

from app.schemas.chat.citation import Citation
from app.schemas.chat.tool_call_trace import ToolCallTrace


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation]
    tool_calls: list[ToolCallTrace]
