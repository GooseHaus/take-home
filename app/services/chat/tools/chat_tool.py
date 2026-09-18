from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session


class ChatTool(Protocol):
    """A read-only capability offered to the chat model. Register implementations in `registry.py`.

    The JSON schema the model sees is generated from `args_model`, so arguments are declared exactly once.
    """

    name: str
    description: str
    args_model: type[BaseModel]

    def run(self, session: Session, args: BaseModel) -> dict:
        """JSON-serialisable result. Raise AppError for expected failures; the loop reports them to the model."""
        ...
