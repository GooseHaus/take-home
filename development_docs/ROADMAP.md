# Roadmap

Written before any code. Tickets are in [PLAN.md](PLAN.md) and the reasoning is in [DECISIONS.md](DECISIONS.md).

## Approach

Build the core loop first: a ticker goes in, and a list of major price movements comes out, each with a cited explanation. Get that working for one ticker with company news only, then add to it. The API and chat read the stored result and never do the expensive work themselves.

The budget is 4 hours. Each phase has a timebox and a cut line. If a phase overruns, take the cut and leave Phase 5's time alone, because a repo nobody can run scores worse than a missing feature.

Stack: Python 3.11, FastAPI, SQLAlchemy 2 with SQLite, yfinance, Exa (`exa-py`), OpenAI, pytest.

## Phase 0: Scaffold (15 min)

Goal: `uvicorn app.main:app` starts, `/health` answers and settings load from `.env`.

- `requirements.txt`, `.env.example`, the `app/` package and settings with `pydantic-settings`
- SQLite engine, with tables created on startup (D2)

Exit: `GET /health` returns 200 and `pytest` runs.

## Phase 1: Prices and movement detection (40 min)

Goal: stored daily prices for a ticker and a list of major movements with enough context to guide the news search.

- Daily bars from yfinance, one year by default, plus SPY and the ticker's sector ETF for the same period
- Company name, sector and industry from `yfinance.Ticker.info`
- Detection (D3): a close-to-close change of at least the threshold, 2% by default. Also a z-score against trailing 60-day volatility
- Driver hint (D4): return relative to SPY and the sector ETF gives `market`, `sector` or `idiosyncratic`
- News window per movement: the previous trading day through the movement day, which covers after-hours earnings and weekends

Exit: unit tests pass on synthetic price series, and a real AAPL run gives a sensible list.

Cut: drop the sector ETF and keep SPY.

## Phase 2: News and explanations (60 min)

Goal: each movement has articles from three tiers and an LLM explanation that cites them.

- A `NewsProvider` protocol with an Exa implementation and a fake for tests
- Three tiers (D5): company news, industry and competitor news, and macro news. Macro searches don't depend on the ticker, so they are cached and shared
- Cost limit: only the N largest movements get news, 25 by default
- Explanation (D6): one structured-output call per movement returning a summary, a category, a confidence and per-article relevance. `unexplained` is allowed
- Re-ingest skips work that is already done

Exit: a known AAPL earnings day is categorised `company`, a known market-wide selloff is categorised `macro`, and both cite real URLs.

Cut: drop competitors and search on the industry name only. Then drop per-article relevance.

## Phase 3: Data API (35 min)

Goal: the endpoint that returns all stock and news data for a ticker, with filters.

- `POST /tickers/{ticker}/ingest` returns 202 and a job (D7). `GET /tickers/{ticker}/status` reports progress
- `GET /tickers/{ticker}` returns the company, prices and movements with explanations and articles. Filters cover dates, direction, size, category, confidence and tier, with pagination
- `GET /tickers/{ticker}/movements/{date}` returns one movement in full
- Clear errors for an unknown ticker, a ticker that isn't ingested and a bad filter

Exit: API tests pass against a seeded in-memory database with fake providers, and `/docs` reads well.

Cut: drop the single-movement endpoint and the tier and confidence filters.

## Phase 4: Chat (45 min)

Goal: a usable chat endpoint that answers from the stored data.

- `POST /chat` takes `{message, ticker?, conversation_id?}` and returns `{answer, citations[], conversation_id}`
- OpenAI tool calling (D8) over read-only tools that use the same query layer as the REST endpoints
- Conversation history stored by `conversation_id`, with a limit on tool rounds
- The system prompt tells the model to answer only from tool results, to cite article URLs, and to say when data is missing

Exit: "Why did AAPL drop in early August?" gets an answer with citations, and a follow-up works through the conversation id.

Cut: drop stored history and have the client send it. Then drop article search.

## Phase 5: Ship (35 min, protected)

Goal: a reviewer can clone it, run it and understand it in five minutes.

- README with quickstart, curl examples for every endpoint, an architecture summary and limitations
- A full test pass and a dry run of the quickstart from a fresh clone
- [SUBMISSION.md](SUBMISSION.md) with the four written answers
- A short demo video
- Push to GitHub

Exit: a fresh venv plus the README steps gives a working demo.

## Stretch, only after Phase 5

- A committed sample dataset for reviewers without keys
- Streaming chat responses
- A chat tool that starts an ingest
- Multi-day movements
- SQLite FTS5 for article search
- Dockerfile

## Out of scope

Auth, rate limiting, a durable job queue, Postgres, a frontend, intraday data and real-time updates.
