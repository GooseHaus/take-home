# START HERE — Stock Movement Explainer (2026-09-18: Phases 0–1 done; next T2-1 Exa provider)

> Living doc. Update the status line and the sections below at the end of every ticket.

## One-line status

**Phases 0–1 done.** Prices (AAPL + SPY + sector ETF) ingest from yfinance into SQLite; movement detection with z-score, volume ratio, excess returns, driver hint and news window is unit-tested (20 tests) and smoke-tested live (AAPL 1y → 40 movements). Models are one-class-per-file (D10). **Next: T2-1 Exa news provider.**

## The clock

4-hour limit. Budget by phase (ROADMAP has the cut lines):

| Phase | Budget | Status |
|-------|--------|--------|
| 0 Scaffold | 15 min | ✅ |
| 1 Prices & movements | 40 min | ✅ |
| 2 News & explanations | 60 min | ⏳ |
| 3 Data API | 35 min | ⏳ |
| 4 Chat | 45 min | ⏳ |
| 5 Ship (protected) | 35 min | ⏳ |

## Done & verified

- **T0-1 scaffold** — `pytest` 1 passed; `/health` → 200 with `exa_configured` / `openai_configured` true; `data/app.db` created and gitignored.
- **T1-1 models + price ingest** — live: AAPL/SPY/XLK 321 rows each; unknown ticker → `TickerNotFound`.
- **T1-2 movement detection** — 19 unit tests; live AAPL 1y @2% → 40 movements (23 idiosyncratic / 11 sector / 6 market); biggest 2026-07-31 −7.35%, z −4.1, volume ×2.6.

## Built but UNVERIFIED

- Nothing yet.

## Open loops (need the human)

- ~~Exa + OpenAI keys~~ ✅ both present in `.env`. `OPENAI_MODEL=gpt-5.4-mini`.
- **Demo video** (T5-4) — yours to record; suggested script: ingest → filtered GET → chat + follow-up.
- **Submission answers** — [SUBMISSION.md](SUBMISSION.md) gets drafted from DECISIONS.md in T5-3, but "did you get stuck" and "are you happy" need your voice.

## Immediate next task

**T2-1** — `NewsProvider` protocol + `ExaProvider` + fake (one class per file under `app/services/news/`), then T2-3 explanation and T2-4 pipeline with the company tier only; T2-2 (industry + macro) once the loop is closed.

## How we work (match this)

- **One class per file** (D10) — models, dataclasses, exceptions, providers.
- One commit per ticket, on `main` (solo, time-boxed — no PR ceremony).
- Per ticket: implement → `pytest` → one manual smoke check → update this file → commit.
- A deviation from PLAN.md gets a `D` entry in DECISIONS.md at the moment it's made — those entries become the submission answers.
- Timebox blown → take the phase's cut line. Phase 5 time is not borrowable.

## Read order for a fresh agent

1. This file → 2. [PLAN.md](PLAN.md) (tickets, data model, layout) → 3. [DECISIONS.md](DECISIONS.md) → 4. [ROADMAP.md](ROADMAP.md) for phase goals and cut lines.
