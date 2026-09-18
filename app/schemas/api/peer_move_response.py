from pydantic import BaseModel, ConfigDict


class PeerMoveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    ticker: str
    pct_change: float
