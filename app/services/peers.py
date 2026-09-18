"""Competitor names for the industry news tier: one LLM call per ticker, cached on the company row (D5)."""

import logging

from sqlalchemy.orm import Session

from app.constants.news import MAX_PEERS
from app.errors import ProviderError
from app.models import Company
from app.prompts import load_prompt
from app.providers.llm import LLMClient
from app.schemas.llm import PeersOutput

logger = logging.getLogger(__name__)

NOT_AVAILABLE = "n/a"


def ensure_peers(session: Session, llm: LLMClient, company: Company) -> list[str]:
    if company.peers is not None:
        return company.peers
    try:
        output = llm.structured(
            load_prompt("suggest_peers_system").substitute(max_peers=MAX_PEERS),
            load_prompt("suggest_peers_user").substitute(
                company_name=company.name,
                ticker=company.ticker,
                sector=company.sector or NOT_AVAILABLE,
                industry=company.industry or NOT_AVAILABLE,
            ),
            PeersOutput,
        )
    except ProviderError as exc:
        # Not cached, so the next ingest tries again; the industry tier falls back to the industry string alone
        logger.warning("peer suggestion failed for %s: %s", company.ticker, exc.message)
        return []
    company.peers = [name.strip() for name in output.peers if name.strip()][:MAX_PEERS]
    session.flush()
    logger.info("peers for %s: %s", company.ticker, company.peers)
    return company.peers
