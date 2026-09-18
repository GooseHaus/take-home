from pydantic import BaseModel

from app.schemas.api.peer_response import PeerResponse


class CompanyResponse(BaseModel):
    ticker: str
    name: str
    sector: str | None
    industry: str | None
    sector_etf: str | None
    peers: list[PeerResponse]
