from datetime import date

import pytest

from app.constants.news import COMPANY_RESULTS, MACRO_CACHE_SCOPE, MACRO_QUERY
from app.enums import DriverHint, NewsTier
from app.models import Company, Movement
from app.services.news.company_tier import CompanyTier
from app.services.news.industry_tier import IndustryTier
from app.services.news.macro_tier import MacroTier
from app.services.news.registry import NEWS_TIERS, ordered_tiers
from app.services.news.search import plan_searches


def company(**overrides) -> Company:
    defaults = {"ticker": "ACME", "name": "Acme Corp", "industry": "Widgets", "peers": ["Globex", "Initech"]}
    return Company(**{**defaults, **overrides})


def movement(id: int, hint: DriverHint, start=date(2026, 1, 5), end=date(2026, 1, 7)) -> Movement:
    return Movement(id=id, ticker="ACME", driver_hint=hint, window_start=start, window_end=end)


def test_registry_covers_all_three_tiers():
    assert {t.tier for t in NEWS_TIERS} == set(NewsTier)


@pytest.mark.parametrize(
    "hint, first",
    [
        (DriverHint.MARKET, NewsTier.MACRO),
        (DriverHint.SECTOR, NewsTier.INDUSTRY),
        (DriverHint.IDIOSYNCRATIC, NewsTier.COMPANY),
    ],
)
def test_driver_hint_decides_which_tier_goes_first(hint, first):
    assert ordered_tiers(hint)[0].tier is first


def test_company_query_names_the_company_and_ticker():
    assert CompanyTier().build_query(movement(1, DriverHint.MARKET), company()) == "Acme Corp (ACME) stock news"


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, "Widgets industry news, including Globex, Initech"),
        ({"peers": None}, "Widgets industry news"),
        ({"industry": None}, "Acme Corp competitors news, including Globex, Initech"),
        ({"industry": None, "peers": []}, None),  # nothing to search for -> tier is skipped
        ({"peers": ["A", "B", "C", "D", "E", "F"]}, "Widgets industry news, including A, B, C, D"),
    ],
)
def test_industry_query(overrides, expected):
    assert IndustryTier().build_query(movement(1, DriverHint.SECTOR), company(**overrides)) == expected


def test_macro_tier_is_ticker_independent():
    tier = MacroTier()
    acme, beta = company(), company(ticker="BETA", name="Beta Inc")
    assert tier.build_query(movement(1, DriverHint.MARKET), acme) == MACRO_QUERY
    assert tier.cache_scope(None, acme) == tier.cache_scope(None, beta) == MACRO_CACHE_SCOPE


def test_movements_sharing_a_window_share_searches():
    same_window = [movement(1, DriverHint.MARKET), movement(2, DriverHint.IDIOSYNCRATIC)]
    planned = plan_searches(same_window, company())
    assert len(planned) == 3 and all(search.movement_ids == [1, 2] for search in planned)

    other_window = movement(3, DriverHint.MARKET, start=date(2026, 2, 2), end=date(2026, 2, 4))
    assert len(plan_searches([*same_window, other_window], company())) == 6


def test_planned_search_carries_tier_limit_and_cache_key():
    (search,) = plan_searches([movement(1, DriverHint.IDIOSYNCRATIC)], company(), tiers=[CompanyTier()])
    assert search.cache_key == "company:ACME:2026-01-05:2026-01-07"
    assert (search.tier, search.limit) == (NewsTier.COMPANY, COMPANY_RESULTS)


def test_tier_without_a_query_is_skipped():
    planned = plan_searches([movement(1, DriverHint.SECTOR)], company(industry=None, peers=[]))
    assert {s.tier for s in planned} == {NewsTier.COMPANY, NewsTier.MACRO}
