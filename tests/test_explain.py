from datetime import date

import pytest

from app.enums import DriverHint, ExplanationCategory, NewsTier
from app.models import Company, Explanation, Movement
from app.repositories.articles import upsert_articles
from app.repositories.movements import link_articles, linked_articles
from app.schemas.llm import ArticleRelevance, ExplanationOutput
from app.services.explain import NO_ARTICLES, build_user_prompt, explain_movement, prompt_articles
from tests.factories import article_hit
from tests.fakes.fake_llm_client import FakeLLMClient

DAY = date(2026, 7, 31)


@pytest.fixture
def company(session) -> Company:
    company = Company(
        ticker="ACME", name="Acme Corp", sector="Technology", industry="Consumer Electronics", sector_etf="XLK"
    )
    session.add(company)
    return company


@pytest.fixture
def movement(session) -> Movement:
    movement = Movement(
        ticker="ACME",
        date=DAY,
        close=92.65,
        prev_close=100.0,
        pct_change=-7.35,
        zscore=-4.1,
        volume_ratio=2.6,
        market_pct_change=0.72,
        sector_pct_change=-0.22,
        excess_vs_market=-8.07,
        excess_vs_sector=-7.13,
        driver_hint=DriverHint.IDIOSYNCRATIC,
        window_start=date(2026, 7, 30),
        window_end=date(2026, 8, 1),
    )
    session.add(movement)
    session.flush()
    return movement


def link(session, movement, *slugs, tier=NewsTier.COMPANY):
    articles = upsert_articles(session, [article_hit(slug) for slug in slugs])
    link_articles(session, movement, articles, tier)
    return articles


def reply_with(category, confidence, relevance: dict[int, float]):
    def reply(user_prompt, response_model):
        return ExplanationOutput(
            summary="  Acme fell after cutting guidance.  ",
            category=category,
            confidence=confidence,
            article_relevance=[ArticleRelevance(article_id=i, relevance=r) for i, r in relevance.items()],
        )

    return reply


def test_prompt_carries_price_context_and_article_ids(session, company, movement):
    (article,) = link(session, movement, "acme-cuts-guidance")
    prompt = build_user_prompt(movement, company, prompt_articles(session, movement))
    assert "Acme Corp (ACME)" in prompt
    assert "2026-07-31 (Friday)" in prompt
    assert "-7.35% (100.00 -> 92.65)" in prompt
    assert "Broad market (SPY): +0.72%" in prompt
    assert "Driver hint from prices alone: idiosyncratic" in prompt
    assert f"[id={article.id}] 2026-07-30 | news.example.com | found by: company search" in prompt


def test_prompt_handles_missing_benchmarks_and_no_articles(session, company, movement):
    movement.market_pct_change = movement.zscore = None
    prompt = build_user_prompt(movement, company, [])
    assert "Broad market (SPY): n/a" in prompt and "volatility: n/a" in prompt
    assert NO_ARTICLES in prompt


def test_explanation_and_relevance_are_stored(session, company, movement):
    cause, noise = link(session, movement, "acme-cuts-guidance", "acme-opens-store")
    llm = FakeLLMClient(reply_with(ExplanationCategory.COMPANY, 0.9, {cause.id: 0.95, noise.id: 0.1}))

    explanation = explain_movement(session, llm, movement, company)
    session.commit()

    assert explanation.category is ExplanationCategory.COMPANY
    assert explanation.summary == "Acme fell after cutting guidance."
    assert explanation.model == "fake-model"
    assert {a.url.rsplit("/", 1)[1]: ln.relevance for ln, a in linked_articles(session, movement)} == {
        "acme-cuts-guidance": 0.95,
        "acme-opens-store": 0.1,
    }
    assert llm.calls[0][2] is ExplanationOutput


def test_invented_article_ids_and_out_of_range_scores_are_contained(session, company, movement):
    (article,) = link(session, movement, "acme-cuts-guidance")
    llm = FakeLLMClient(reply_with(ExplanationCategory.COMPANY, 1.7, {article.id: 3.0, 99999: 0.9}))
    explanation = explain_movement(session, llm, movement, company)
    assert explanation.confidence == 1.0
    assert [ln.relevance for ln, _ in linked_articles(session, movement)] == [1.0]


def test_unexplained_is_stored_like_any_other_verdict(session, company, movement):
    llm = FakeLLMClient(reply_with(ExplanationCategory.UNEXPLAINED, 0.6, {}))
    assert explain_movement(session, llm, movement, company).category is ExplanationCategory.UNEXPLAINED


def test_re_explaining_replaces_rather_than_duplicates(session, company, movement):
    explain_movement(session, FakeLLMClient(reply_with(ExplanationCategory.UNEXPLAINED, 0.4, {})), movement, company)
    explain_movement(session, FakeLLMClient(reply_with(ExplanationCategory.MACRO, 0.8, {})), movement, company)
    session.commit()
    assert [e.category for e in session.query(Explanation)] == [ExplanationCategory.MACRO]


def test_linking_is_idempotent_and_first_tier_wins(session, company, movement):
    link(session, movement, "fed-holds-rates", tier=NewsTier.MACRO)
    link(session, movement, "fed-holds-rates", "acme-cuts-guidance", tier=NewsTier.COMPANY)
    tiers = {a.url.rsplit("/", 1)[1]: ln.tier for ln, a in linked_articles(session, movement)}
    assert tiers == {"fed-holds-rates": NewsTier.MACRO, "acme-cuts-guidance": NewsTier.COMPANY}
