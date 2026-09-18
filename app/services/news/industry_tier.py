from app.constants.news import INDUSTRY_RESULTS, MAX_PEERS
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
        # Peers are chosen per ticker, so two tickers in one industry don't necessarily share a query
        return company.ticker
