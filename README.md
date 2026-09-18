# Stock Movement Explainer

Give it a ticker. It pulls a year of daily prices, finds the days with a major move, searches for news around each one (company, industry and macro), and uses an LLM to write a short explanation with sources, a category and a confidence score. The results are available through a REST API and a chat endpoint.

Stack: Python 3.11, FastAPI, SQLite (SQLAlchemy 2), yfinance, [Exa](https://exa.ai) for news, OpenAI for explanations and chat.

## Quickstart

You need Python 3.11+, an [Exa API key](https://dashboard.exa.ai/api-keys) (the free tier is enough) and an OpenAI API key.

```bash
git clone https://github.com/GooseHaus/take-home.git && cd take-home
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # fill in EXA_API_KEY and OPENAI_API_KEY
uvicorn app.main:app
```

API docs are at <http://localhost:8000/docs>. `GET /health` shows whether both keys loaded.

Tests run offline and need no keys:

```bash
pip install -r requirements-dev.txt
pytest
ruff check . && ruff format --check .
```

## Walkthrough

### 1. Ingest a ticker

```bash
curl -s -X POST localhost:8000/tickers/AAPL/ingest
```

This returns `202` and a job. The work runs in the background. A first ticker takes about a minute and costs roughly $0.50 of Exa credit plus a few cents of OpenAI. Poll the job:

```bash
curl -s localhost:8000/tickers/AAPL/status
```

```json
{ "status": "done", "stage": "complete",
  "detail": { "movements": 40, "candidates": 25, "to_explain": 25, "explained": 25,
              "news": { "searches_run": 75, "searches_cached": 0, "searches_refreshed": 0, "cost_dollars": 0.525 },
              "errors": [] } }
```

The request body is optional:

```bash
curl -s -X POST localhost:8000/tickers/MSFT/ingest -H 'content-type: application/json' \
  -d '{"start": "2026-01-01", "end": "2026-06-30", "threshold_pct": 3, "max_movements": 10}'
```

| Field | Default | Meaning |
|---|---|---|
| `start`, `end` | last 365 days | Period to analyse. `lookback_days` can be used instead of `start` |
| `threshold_pct` | `2.0` | Minimum absolute close-to-close change, in percent, to count as a major move |
| `max_movements` | `25` | Cost limit. The N largest moves get news searches and an explanation, plus any move from the last 7 days |
| `refresh` | `false` | Re-explain moves that already have an explanation |

Ingest can be repeated safely. It skips searches and explanations it has already done, so a re-run of past dates takes about a second and costs nothing. Macro news searches don't depend on the ticker, so a second ticker reuses the ones the first ticker ran.

Recent moves are handled differently, because news keeps arriving after a move. A search counts as final only if it ran at least two days after its news window closed. Until then, each re-ingest runs that move's searches again, and the move is re-explained only if new articles turned up. Moves from the last 7 days are always explained, even if they are not among the N largest.

### 2. Get all stock and news data for a ticker

```bash
curl -s "localhost:8000/tickers/AAPL"
```

The response has the company profile, daily prices, every major movement, and the explanation and articles for each movement:

```json
{
  "date": "2026-07-31", "pct_change": -7.35, "zscore": -4.1, "volume_ratio": 2.6,
  "market_pct_change": 0.72, "sector_pct_change": -0.22, "driver_hint": "idiosyncratic",
  "explanation": { "category": "company", "confidence": 0.97,
                   "summary": "Apple fell 7.35% ... after its earnings report and a weak forward forecast ..." },
  "articles": [ { "title": "Apple disappoints with forecast dogged by supply chain struggles | Reuters",
                  "url": "https://www.reuters.com/...", "tier": "company", "relevance": 0.96, "cited": true } ]
}
```

All filters are optional and can be combined:

| Filter | Example | Effect |
|---|---|---|
| `start`, `end` | `start=2026-01-01&end=2026-03-31` | Date range. Also limits the prices returned |
| `direction` | `direction=down` | Only losses or only gains |
| `min_abs_change` | `min_abs_change=4` | Moves of at least 4% in either direction |
| `category` | `category=macro` | `company`, `industry`, `macro` or `unexplained` |
| `driver_hint` | `driver_hint=market` | What the price data suggested: `market`, `sector` or `idiosyncratic` |
| `min_confidence` | `min_confidence=0.8` | Minimum explanation confidence |
| `explained_only` | `explained_only=true` | Leave out moves that were not explained |
| `tier`, `min_relevance` | `min_relevance=0.5` | Limits the articles shown inside each movement. Does not remove movements |
| `sort` | `sort=magnitude` | `date_desc` (default), `date_asc` or `magnitude` |
| `limit`, `offset` | `limit=10` | Pagination over movements. `total_movements` is the full count |
| `include_prices`, `include_news` | `include_prices=false` | Leave parts out of the response |

```bash
# Market-driven drops, showing only the articles the explanation relied on
curl -s "localhost:8000/tickers/AAPL?direction=down&category=macro&min_relevance=0.5&include_prices=false"

# One movement with every article that was considered
curl -s localhost:8000/tickers/AAPL/movements/2026-07-31

# Tickers ingested so far
curl -s localhost:8000/tickers
```

### 3. Chat with the data

```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message": "Why did AAPL drop at the end of July?"}'
```

```json
{ "conversation_id": "3f2a...",
  "answer": "AAPL dropped 7.35% on 2026-07-31 because of a company-specific post-earnings selloff ...",
  "citations": [ { "title": "Apple (AAPL) Q3 2026 earnings report: Live updates", "url": "https://www.cnbc.com/...", "source": "cnbc.com" } ],
  "tool_calls": [ { "name": "list_movements", "arguments": { "ticker": "AAPL", "start": "2026-07-25", "end": "2026-07-31", "direction": "down" } } ] }
```

Send the `conversation_id` back to ask a follow-up:

```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"conversation_id": "3f2a...", "message": "Was that just Apple, or was the whole market down that day?"}'
```

Other questions to try:

- Which of Microsoft's big moves this year were macro or industry driven?
- What were AAPL's three biggest drops and what caused them?
- How did MSFT do in Q2?
- Anything about a ticker you haven't ingested. It tells you how to ingest it and does not guess.

The chat model has read-only access through five tools that use the same queries as the REST endpoints. `citations` lists the articles the answer links to, limited to URLs the tools returned. `tool_calls` shows the lookups behind the answer. `GET /chat/{conversation_id}` returns the transcript.

## How it works

Ingest (`POST /tickers/{ticker}/ingest`) runs four stages as a background job and stores the results in SQLite:

1. Prices. yfinance daily bars for the ticker, SPY and the ticker's sector ETF.
2. Movements. Days where the absolute close-to-close change is at least 2%. Each one also gets a z-score against trailing volatility, a volume ratio, and its return relative to the market and the sector. Those produce a driver hint: `market`, `sector` or `idiosyncratic`.
3. News. Three Exa searches per movement: company, industry (with competitors suggested by the LLM) and macro. Results are cached by search key.
4. Explanation. One OpenAI structured-output call per movement returns a summary, a category, a confidence and a relevance score for each article.

`GET /tickers/{ticker}` and `POST /chat` only read from the database. They share one query layer and one `MovementFilters` model.

Design notes:

- Paid calls happen once, during ingest. The read endpoints are fast, filters are plain SQL, and nothing is billed twice.
- The driver hint is how the macro tier is handled. Finding macro news is easy. Knowing when macro is the right answer is the hard part, and the price data answers that cheaply: if SPY fell 3% the same day, company headlines are probably not the cause. The hint sets the search order and is passed to the LLM as evidence. In testing, every AAPL move flagged as market-driven was categorised `macro`.
- The LLM may answer `unexplained`, and it can only cite articles it was given. Three of MSFT's 25 explained moves came back `unexplained`.
- `MovementFilters` is defined once and used as the REST query string, the chat tool arguments and the repository input. The enums are shared by the database columns, the API and the LLM output schema.
- The news source, the LLM and the market data provider each sit behind a Protocol and are wired in `app/dependencies.py`. News tiers and chat tools are small classes in a registry. Adding the industry and macro tiers took two new files and one registry line.

### Layout

```
app/
  api/            routers
  services/       pipeline, movement detection, news tiers, explanations, chat
  repositories/   database access
  providers/      yfinance, Exa, OpenAI
  models/ domain/ schemas/ enums/ errors/    one class per file
  constants/      fixed values
  prompts/        LLM prompts as .md files
  dependencies.py provider wiring
  config.py       settings from the environment
tests/            131 offline tests, with fakes for each provider
development_docs/ roadmap, tickets, conventions and decision log
```

The planning documents are in `development_docs/`: [ROADMAP](development_docs/ROADMAP.md), [PLAN](development_docs/PLAN.md), [CONVENTIONS](development_docs/CONVENTIONS.md) and [DECISIONS](development_docs/DECISIONS.md). The written answers are in [SUBMISSION](development_docs/SUBMISSION.md).

### Configuration

| Variable | Default | Notes |
|---|---|---|
| `EXA_API_KEY` | | Required for ingest |
| `OPENAI_API_KEY` | | Required for ingest and chat |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Needs structured output and tool calling |
| `DATABASE_URL` | `sqlite:///data/app.db` | |
| `MOVE_THRESHOLD_PCT` | `2.0` | Default cutoff for a major move |
| `MAX_MOVEMENTS_WITH_NEWS` | `25` | Default cost limit per ingest |
| `LOG_LEVEL` | `INFO` | Paid calls log their latency and cost |

Without keys the app still starts and serves data that was already ingested. Ingest and chat return `503` with the name of the missing key.

## Limitations

- An explanation is the most likely cause according to the news found. It is not proof, and it is not investment advice.
- Only single-day moves are detected. A slow 10% slide over two weeks is missed.
- Exa's published-date filter drops pages with a missing or wrong date. The search window is extended by one day to pick up next-day coverage.
- News for a recent move is only updated when ingest is run again. Nothing re-ingests on a schedule.
- Outside the last 7 days, only the N largest moves in the requested range are explained.
- Background jobs run inside the API process. A restart during an ingest loses the job. Posting the ingest again resumes it without repeating finished work.
- SQLite with no migrations. A schema change means deleting `data/app.db`.
- No authentication or rate limiting. `search_articles` is a substring match, not full-text search.
