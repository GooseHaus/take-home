from pydantic import BaseModel


class ToolCallTrace(BaseModel):
    """Which stored data an answer was built from, so a reader can check the grounding."""

    name: str
    arguments: dict
