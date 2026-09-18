from pydantic import BaseModel, ConfigDict


class PeerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    ticker: str | None
