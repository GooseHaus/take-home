from pydantic import BaseModel, Field


class PeersOutput(BaseModel):
    peers: list[str] = Field(description="Company names of the closest publicly traded competitors, most direct first")
