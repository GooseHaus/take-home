# START HERE — Stock Movement Explainer (2026-09-18: T0-1 scaffold done; next T1-1)

> Living doc. Update the status line and the sections below at the end of every ticket.

## One-line status

**Phase 0 done.** FastAPI app boots, `/health` answers, settings load from `.env` (both keys detected), SQLite created under `data/`, pytest runs offline against in-memory SQLite. **Next: T1-1 models + price ingest.**

## The clock

4-hour limit. Budget by phase (ROADMAP has the cut lines):

| Phase | Budget | Status |
|-------|--------|--------|
| 0 Scaffold | 15 min | ✅ |
| 1 Prices & movements | 40 min | ⏳ |
| 2 News & explanations | 60 min | ⏳ |
| 3 Data API | 35 min | ⏳ |
| 4 Chat | 45 min | ⏳ |
| 5 Ship (protected) | 35 min | ⏳ |

## Done & verified

- **T0-1 scaffold** — `pytest` 1 passed; `/health` → 200 with `exa_configured` / `openai_configured` true; `data/app.db` created and gitignored.

## Built but UNVERIFIED

- Nothing yet.

## Open loops (need the human)

- ~~Exa + OpenAI keys~~ ✅ both present in `.env`. **`OPENAI_MODEL` still needs a value** before T2-3.
- **Demo video** (T5-4) — yours to record; suggested script: ingest → filtered GET → chat + follow-up.
- **Submission answers** — [SUBMISSION.md](SUBMISSION.md) gets drafted from DECISIONS.md in T5-3, but "did you get stuck" and "are you happy" need your voice.

## Immediate next task

**T1-1** — SQLAlchemy models (all tables in PLAN.md) + yfinance price/profile ingest incl. SPY and the sector ETF. Then T1-2 pure movement detection with unit tests.

## How we work (match this)

- One commit per ticket, on `main` (solo, time-boxed — no PR ceremony).
- Per ticket: implement → `pytest` → one manual smoke check → update this file → commit.
- A deviation from PLAN.md gets a `D` entry in DECISIONS.md at the moment it's made — those entries become the submission answers.
- Timebox blown → take the phase's cut line. Phase 5 time is not borrowable.

## Read order for a fresh agent

1. This file → 2. [PLAN.md](PLAN.md) (tickets, data model, layout) → 3. [DECISIONS.md](DECISIONS.md) → 4. [ROADMAP.md](ROADMAP.md) for phase goals and cut lines.
