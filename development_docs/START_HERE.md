# START HERE — Stock Movement Explainer (2026-09-18: planning done, no code yet)

> Living doc. Update the status line and the sections below at the end of every ticket.

## One-line status

**Planning complete.** Docs written ([ROADMAP.md](ROADMAP.md), [PLAN.md](PLAN.md), [DECISIONS.md](DECISIONS.md)); repo has a venv (Python 3.11.1, empty) and a `.gitignore`. **Next: T0-1 scaffold.**

## The clock

4-hour limit. Budget by phase (ROADMAP has the cut lines):

| Phase | Budget | Status |
|-------|--------|--------|
| 0 Scaffold | 15 min | ⏳ |
| 1 Prices & movements | 40 min | ⏳ |
| 2 News & explanations | 60 min | ⏳ |
| 3 Data API | 35 min | ⏳ |
| 4 Chat | 45 min | ⏳ |
| 5 Ship (protected) | 35 min | ⏳ |

## Done & verified

- Nothing yet.

## Built but UNVERIFIED

- Nothing yet.

## Open loops (need the human)

- **Exa account + key** — sign up at exa.ai ($20 free credit, no card needed for the free tier), put `EXA_API_KEY` in `.env`. Needed from T2-1.
- **OpenAI key** — copy your existing key into this repo's `.env` as `OPENAI_API_KEY`. Needed from T2-3.
- **Demo video** (T5-4) — yours to record; suggested script: ingest → filtered GET → chat + follow-up.
- **Submission answers** — [SUBMISSION.md](SUBMISSION.md) gets drafted from DECISIONS.md in T5-3, but "did you get stuck" and "are you happy" need your voice.

## Immediate next task

**T0-1** — `requirements.txt`, `.env.example`, `app/` skeleton, `/health`. Then T1-1 → T1-2 need no API keys, so key signup can happen in parallel.

## How we work (match this)

- One commit per ticket, on `main` (solo, time-boxed — no PR ceremony).
- Per ticket: implement → `pytest` → one manual smoke check → update this file → commit.
- A deviation from PLAN.md gets a `D` entry in DECISIONS.md at the moment it's made — those entries become the submission answers.
- Timebox blown → take the phase's cut line. Phase 5 time is not borrowable.

## Read order for a fresh agent

1. This file → 2. [PLAN.md](PLAN.md) (tickets, data model, layout) → 3. [DECISIONS.md](DECISIONS.md) → 4. [ROADMAP.md](ROADMAP.md) for phase goals and cut lines.
