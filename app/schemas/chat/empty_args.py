from pydantic import BaseModel


class EmptyArgs(BaseModel):
    """For tools that take no arguments."""
