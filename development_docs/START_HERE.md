# START HERE — Stock Movement Explainer (2026-09-18: Phases 0–1, conventions, Phases 0–4 done — chat live; next Phase 5 ship)

> Living doc. Update the status line and the sections below at the end of every ticket.

## One-line status

**Phases 0–1 done.** Prices (AAPL + SPY + sector ETF) ingest from yfinance into SQLite; movement detection with z-score, volume ratio, excess returns, driver hint and news window is unit-tested (20 tests) and smoke-tested live (AAPL 1y → 40 movements). Models are one-class-per-file (D10). **T1-3 retrofit done:** code follows [CONVENTIONS.md](CONVENTIONS.md) — constants, enums, Protocol-backed providers, repositories, typed errors, ruff clean, pinned deps (27 tests). **T2-1 done:** Exa news search behind `NewsProvider`, URL-deduped article storage (38 tests). **T2-3 done:** LLM explanations with structured output, prompts as files (45 tests); live: earnings day → `company` 0.98, market sell-off day → `macro` 0.72. **T2-4 done — the core loop is closed:** one call ingests a ticker end-to-end (live AAPL 1y: 28.8 s, $0.16, re-run free). **T2-2 done — Phase 2 complete:** company + industry + macro tiers, LLM-suggested peers, macro searches shared across tickers, `refresh` re-explain (71 tests). **Phase 3 done:** `POST /tickers/{t}/ingest`, `GET /tickers/{t}/status`, `GET /tickers/{t}` with the shared `MovementFilters`, `GET /tickers/{t}/movements/{date}`, `GET /tickers` (107 tests; verified live over HTTP). **Phase 4 done:** `POST /chat` (tool-calling over the shared read layer, grounded citations, tool trace) and `GET /chat/{id}`; follow-ups work via `conversation_id` (120 tests; verified live on gpt-5.4-mini). Branch `initial-development/T4-chat` is ready to push. **Every feature in the brief now exists. Next: Phase 5 — README, fresh-clone dry run, SUBMISSION.md answers, video.**

## The clock

4-hour limit. Budget by phase (ROADMAP has the cut lines):

| Phase | Budget | Status |
|-------|--------|--------|
| 0 Scaffold | 15 min | ✅ |
| 1 Prices & movements | 40 min | ✅ |
| 2 News & explanations | 60 min | ✅ |
| 3 Data API | 35 min | ✅ |
| 4 Chat | 45 min | ✅ |
| 5 Ship (protected) | 35 min | ⏳ |

## Done & verified

- **T0-1 scaffold** — `pytest` 1 passed; `/health` → 200 with `exa_configured` / `openai_configured` true; `data/app.db` created and gitignored.
- **T1-1 models + price ingest** — live: AAPL/SPY/XLK 321 rows each; unknown ticker → `TickerNotFound`.
- **T1-2 movement detection** — 19 unit tests; live AAPL 1y @2% → 40 movements (23 idiosyncratic / 11 sector / 6 market); biggest 2026-07-31 −7.35%, z −4.1, volume ×2.6.
- **T1-3 conventions retrofit** — 27 tests, `ruff check` + `ruff format --check` clean; live AAPL run through provider → repositories → detection gives the same 40 movements. *Schema changed (enum columns): delete `data/app.db` if you have an old one (D2).*
- **T2-1 Exa news provider** — 11 tests (call shape, normalisation, error mapping, dedupe); live search for AAPL's 2026-07-31 drop returned 8 on-topic in-window articles at $0.007.
- **T2-3 explanation** — 7 tests; live on gpt-5.4-mini both "done when" cases pass (see PLAN.md T2-3).
- **T2-4 pipeline + jobs** — 7 tests (idempotent re-run, cost guard, partial-failure retry, failed-job path); live AAPL 1y end-to-end, numbers in PLAN.md T2-4.
- **T2-2 tiers** — 19 tests; live AAPL refresh + MSFT ingest (numbers in PLAN.md T2-2). Local `data/app.db` now holds AAPL and MSFT, 25 explained movements each.
- **T3-1/T3-2 data API** — 36 tests; every route exercised live with curl against real AAPL/MSFT data, including error paths and a zero-cost re-ingest.
- **T4-1/T4-2 chat** — 13 tests; four live conversations incl. a follow-up and an un-ingested ticker (transcripts summarised in PLAN.md T4).

## Built but UNVERIFIED

- Nothing yet.

## Open loops (need the human)

- ~~Exa + OpenAI keys~~ ✅ both present in `.env`. `OPENAI_MODEL=gpt-5.4-mini`.
- **Demo video** (T5-4) — yours to record; suggested script: ingest → filtered GET → chat + follow-up.
- **Submission answers** — [SUBMISSION.md](SUBMISSION.md) gets drafted from DECISIONS.md in T5-3, but "did you get stuck" and "are you happy" need your voice.

## Immediate next task

**T5-1** — README: what it is, quickstart (venv, `pip install -r requirements.txt`, `.env`, `uvicorn app.main:app`), curl walkthrough (ingest → status → filtered GET → chat + follow-up), architecture sketch, limitations / what's next. Then **T5-2** fresh-clone dry run, **T5-3** SUBMISSION.md drafts from DECISIONS.md, optional CI workflow (ruff + pytest). Video (T5-4) is the user's.

## How we work (match this)

- **Follow [CONVENTIONS.md](CONVENTIONS.md)** — one class per file, constants/enums (no magic values), Protocol-backed providers wired in `dependencies.py`, repositories for DB access, typed errors.
- **One branch per epic: `initial-development/T<epic>-<description>`** (e.g. `initial-development/T2-news-and-explanations`), cut from up-to-date `main`. One commit per ticket. The user pushes when the epic is done.
- **The agent never pushes and never commits to `main`.** The user pushes branches and merges.
- Per ticket: implement → `ruff format` + `ruff check` → `pytest` → one manual smoke check → update this file → commit.
- A deviation from PLAN.md gets a `D` entry in DECISIONS.md at the moment it's made — those entries become the submission answers.
- Timebox blown → take the phase's cut line. Phase 5 time is not borrowable.

## Read order for a fresh agent

1. This file → 2. [CONVENTIONS.md](CONVENTIONS.md) → 3. [PLAN.md](PLAN.md) (tickets, data model, layout) → 4. [DECISIONS.md](DECISIONS.md) → 5. [ROADMAP.md](ROADMAP.md) for phase goals and cut lines.
