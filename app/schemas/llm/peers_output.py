from pydantic import BaseModel, Field

from app.schemas.llm.peer_suggestion import PeerSuggestion


class PeersOutput(BaseModel):
    peers: list[PeerSuggestion] = Field(description="The closest publicly traded competitors, most direct first")
