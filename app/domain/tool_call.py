from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation requested by the model. `arguments` is the raw JSON string it produced."""

    id: str
    name: str
    arguments: str
