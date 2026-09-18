from app.constants.news import COMPANY_RESULTS
from app.enums import NewsTier
from app.models import Company, Movement


class CompanyTier:
    """[Easy] Company-specific news: earnings, guidance, launches, lawsuits, analyst actions."""

    tier = NewsTier.COMPANY
    max_results = COMPANY_RESULTS

    def build_query(self, movement: Movement, company: Company) -> str | None:
        return f"{company.name} ({company.ticker}) stock news"

    def cache_scope(self, movement: Movement, company: Company) -> str:
        return company.ticker
