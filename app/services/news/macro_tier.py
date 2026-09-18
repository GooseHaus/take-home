from app.constants.news import MACRO_CACHE_SCOPE, MACRO_QUERY, MACRO_RESULTS
from app.enums import NewsTier
from app.models import Company, Movement


class MacroTier:
    """[Hard] Market-wide news: rates, economic data, policy, geopolitics.

    The query doesn't mention the company, so the cache scope is global: every ticker (and every movement sharing a
    window) reuses one search.
    """

    tier = NewsTier.MACRO
    max_results = MACRO_RESULTS

    def build_query(self, movement: Movement, company: Company) -> str | None:
        return MACRO_QUERY

    def cache_scope(self, movement: Movement, company: Company) -> str:
        return MACRO_CACHE_SCOPE
