from dataclasses import dataclass, field

from app.domain.tool_call import ToolCall


@dataclass(frozen=True)
class ChatTurn:
    """One assistant reply: either final text, or a request to run tools (or, rarely, both)."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict:
        """The reply in chat-completions message form, for appending to the running conversation."""
        message: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        return message
