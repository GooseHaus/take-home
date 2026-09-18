"""The tiers the pipeline runs. Adding a tier = one strategy class + one entry here."""

from app.enums import DriverHint, NewsTier
from app.services.news.company_tier import CompanyTier
from app.services.news.industry_tier import IndustryTier
from app.services.news.macro_tier import MacroTier
from app.services.news.news_tier_strategy import NewsTierStrategy

NEWS_TIERS: list[NewsTierStrategy] = [CompanyTier(), IndustryTier(), MacroTier()]

# Which tier to try first given what prices alone suggest (D4). Every tier still runs; this only sets link order,
# and an article found by two tiers keeps the first one's label.
TIER_PRIORITY: dict[DriverHint, list[NewsTier]] = {
    DriverHint.MARKET: [NewsTier.MACRO, NewsTier.INDUSTRY, NewsTier.COMPANY],
    DriverHint.SECTOR: [NewsTier.INDUSTRY, NewsTier.COMPANY, NewsTier.MACRO],
    DriverHint.IDIOSYNCRATIC: [NewsTier.COMPANY, NewsTier.INDUSTRY, NewsTier.MACRO],
}


def ordered_tiers(hint: DriverHint, tiers: list[NewsTierStrategy] | None = None) -> list[NewsTierStrategy]:
    priority = TIER_PRIORITY[hint]
    return sorted(tiers if tiers is not None else NEWS_TIERS, key=lambda t: priority.index(t.tier))
