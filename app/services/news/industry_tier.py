import hashlib

from app.constants.news import INDUSTRY_RESULTS, MAX_PEERS, QUERY_DIGEST_CHARS
from app.enums import NewsTier
from app.models import Company, Movement
from app.services.peers import company_peers


class IndustryTier:
    """[Medium] Competitor and sector news. Peers are LLM-suggested once per ticker and cached on the company (D5)."""

    tier = NewsTier.INDUSTRY
    max_results = INDUSTRY_RESULTS

    def build_query(self, movement: Movement, company: Company) -> str | None:
        peers = [peer.name for peer in company_peers(company)][:MAX_PEERS]
        if not company.industry and not peers:
            return None
        subject = f"{company.industry} industry" if company.industry else f"{company.name} competitors"
        return f"{subject} news" + (f", including {', '.join(peers)}" if peers else "")

    def cache_scope(self, movement: Movement, company: Company) -> str:
        # The query names the peers. If they change (or were unavailable the first time), results cached for the
        # old query must not be reused, so a digest of the query is part of the key.
        query = self.build_query(movement, company) or ""
        return f"{company.ticker}:{hashlib.sha1(query.encode()).hexdigest()[:QUERY_DIGEST_CHARS]}"
