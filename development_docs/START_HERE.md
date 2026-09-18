# Start here

Status as of 2026-09-18: all code is done. 174 tests pass and ruff is clean.

## What's left

1. Edit [SUBMISSION.md](SUBMISSION.md), especially questions 2 to 4, and delete its draft note.
2. Record the demo video.
3. Submit the repository link.

Suggested 3-minute demo:

1. Show `/docs`.
2. `POST /tickers/NVDA/ingest`, then poll `/tickers/NVDA/status` to show the stages and the cost.
3. `GET /tickers/AAPL?direction=down&category=macro&min_relevance=0.5&include_prices=false`
4. Ask the chat "Why did AAPL drop at the end of July?", then "Was that just Apple, or was the whole market down that day?"
5. Ask about a ticker that hasn't been ingested.
6. Spend 30 seconds on the driver hint idea and DECISIONS.md.

## Phases

| Phase | Budget | Status |
|-------|--------|--------|
| 0 Scaffold | 15 min | done |
| 1 Prices and movements | 40 min | done |
| 2 News and explanations | 60 min | done |
| 3 Data API | 35 min | done |
| 4 Chat | 45 min | done |
| 5 Ship | 35 min | done except the video and the written answers |

What shipped in each ticket, with the numbers from the live runs, is in [PLAN.md](PLAN.md).

## Known gaps

- TSLA in the local database still has competitors in the older names-only format. Its next ingest upgrades them and loads competitor prices (D20).
- News for a recent move only updates when ingest is run again. Nothing runs on a schedule (D19).
- Accuracy was checked by looking at known days. It was not measured.

## Running it

```bash
uvicorn app.main:app      # docs at http://localhost:8000/docs
pytest
ruff check . && ruff format --check .
python -m scripts.export_openapi   # after changing an endpoint or schema
```

The local `data/app.db` holds AAPL and MSFT with 25 explained movements each. Delete it after any model change, because there are no migrations (D2).

## How we work

- Follow [CONVENTIONS.md](CONVENTIONS.md).
- One branch per epic, named `initial-development/T<epic>-<description>`, cut from up-to-date `main`. One commit per ticket. The user pushes and merges; the agent never pushes or commits to `main`.
- Per ticket: implement, run `ruff format` and `ruff check`, run `pytest`, do one live check, update the docs, commit.
- A change from PLAN.md gets an entry in DECISIONS.md when it is made.

## Read order

This file, then [CONVENTIONS.md](CONVENTIONS.md), [PLAN.md](PLAN.md), [DECISIONS.md](DECISIONS.md) and [ROADMAP.md](ROADMAP.md).
