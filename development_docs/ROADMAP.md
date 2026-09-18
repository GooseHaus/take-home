# Stock Movement Explainer — Roadmap

## Guiding principle

Ship the core loop first. **A ticker goes in; a list of major price movements comes out, each with a cited, honest explanation.** That loop has to work end-to-end (one ticker, company news only) before anything is layered on. The API and chat are views over that stored result — they never do the expensive work themselves.

Total budget: **4 hours**. Every phase has a timebox and a cut line. When a timebox blows, take the cut, don't borrow from Phase 5 — an unexplained repo scores worse than a missing feature.

Tickets live in [PLAN.md](PLAN.md); choices and tradeoffs in [DECISIONS.md](DECISIONS.md); live status in [START_HERE.md](START_HERE.md).

---

## Architecture at a glance

```
            POST /tickers/{t}/ingest
                      │
   ┌──────────────────▼───────────────────┐
   │ pipeline (background task)           │
   │  1. prices     yfinance → prices     │   + SPY and the sector ETF as benchmarks
   │  2. movements  detect + classify     │   abs %, z-score, excess return vs SPY/sector
   │  3. news       Exa, 3 tiers          │   company · industry/peers · macro (cached by date)
   │  4. explain    OpenAI, structured    │   summary, category, confidence, cited article ids
   └──────────────────┬───────────────────┘
                      ▼
                SQLite (SQLAlchemy)
                      ▲
        ┌─────────────┴─────────────┐
 GET /tickers/{t} (+filters)   POST /chat
 read-only over stored data    OpenAI tool-calling; tools = the same read queries
```

**Stack:** Python 3.11 · FastAPI · SQLAlchemy 2 + SQLite · yfinance · Exa (`exa-py`) · OpenAI · pytest.

---

## Phase 0 — Scaffold (15 min)

**Goal:** `uvicorn app.main:app` boots, `/health` answers, config loads from `.env`.

- `requirements.txt`, `.env.example`, `app/` package layout, settings via `pydantic-settings`
- SQLite engine + `create_all` on startup (no Alembic — D2)

**Exit criteria:** `GET /health` → 200; `pytest` runs (zero tests is fine).

---

## Phase 1 — Prices & movement detection (40 min)

**Goal:** For a ticker, stored daily prices and a list of "major movements" with enough context to guide the news search.

- Fetch daily OHLCV via yfinance (default 1y; `start`/`end` override), plus **SPY** and the ticker's **sector ETF** over the same window
- Company profile (name, sector, industry) from `yfinance.Ticker.info`, cached
- Detection (D3): close-to-close return; major when `|return| ≥ threshold` (default 2%). Also store a **z-score vs trailing 60-day volatility** so a 2% day in KO and a 2% day in TSLA aren't treated as equally notable
- **Driver hint (D4):** excess return vs SPY and vs sector ETF → `market` / `sector` / `idiosyncratic`. The price data itself says which news tier most likely explains the move
- News window per movement = previous trading day → movement day (covers after-hours earnings and weekends)

**Exit criteria:** unit tests pass on synthetic series (threshold edges, z-score warm-up, driver hint, Monday window); a real `AAPL` run stores sane movements.

**Cut line:** drop the sector ETF (keep SPY only).

---

## Phase 2 — News & explanations (60 min)

**Goal:** Each movement has relevant articles across three tiers and an LLM-written explanation that cites them.

- `NewsProvider` protocol; **Exa** implementation (date-bounded, news category, highlights rather than full text). Fake provider for tests
- Three tiers (D5):
  - **[Easy] company** — `"{name} ({ticker})"` news in the window
  - **[Medium] industry / competitors** — industry string from the profile + peers (LLM-suggested once per ticker, cached)
  - **[Hard] macro** — ticker-independent query per date, **cached by date and shared across tickers**
- Cost guard: only the top-N movements by magnitude get news (default 25); tier order follows the driver hint
- **Explain (D6):** one structured-output OpenAI call per movement → `summary`, `category` (company / industry / macro / unexplained), `confidence`, `cited_article_ids`, per-article relevance. "Unexplained" is a valid answer — no invented causes
- Everything is idempotent: re-ingest skips movements that already have news + explanation

**Exit criteria:** ingesting `AAPL` for a year yields explanations where a known earnings day is tagged `company` and a known broad sell-off day is tagged `macro`, each citing real URLs.

**Cut line:** drop peers (industry string only) → then drop per-article relevance.

---

## Phase 3 — Data API (35 min)

**Goal:** The "fetch all stock and news data for a ticker" endpoint, with useful filters.

- `POST /tickers/{ticker}/ingest` → 202 + job status (background task, D7); `GET /tickers/{ticker}/status`
- `GET /tickers/{ticker}` — company, prices, movements → explanation → articles. Filters: `start`, `end`, `min_abs_change`, `direction`, `category`, `min_confidence`, `tier`, `include_prices`, `include_news`, `limit`/`offset`
- `GET /tickers/{ticker}/movements/{date}` — one movement in full
- Clear errors: unknown ticker 404, not-yet-ingested 409 with a pointer to ingest, bad filter 422

**Exit criteria:** API tests pass against a seeded in-memory DB with fake providers (no network, no keys); OpenAPI docs at `/docs` read well.

**Cut line:** drop the single-movement endpoint and `tier`/`min_confidence` filters.

---

## Phase 4 — Chat (45 min)

**Goal:** A usable chat endpoint grounded in the stored data.

- `POST /chat` `{message, ticker?, conversation_id?}` → `{answer, citations[], conversation_id}`
- OpenAI **tool-calling** (D8) over read-only tools: `list_movements`, `get_movement`, `search_articles`, `price_summary`, `list_tickers` — same query layer the REST endpoints use
- Conversation history persisted per `conversation_id`; bounded tool-loop iterations
- System prompt: answer only from tool results, cite article URLs, say so when data is missing (and name the ingest endpoint)

**Exit criteria:** "Why did AAPL drop in early August?" returns a grounded answer with citations; a follow-up ("was that just Apple or the whole market?") works using the conversation id.

**Cut line:** drop persistence (client sends history) → then drop `search_articles`.

---

## Phase 5 — Ship (35 min, protected)

**Goal:** A reviewer can clone, run, and understand it in five minutes.

- README: what it is, quickstart, `.env` keys, curl examples for every endpoint, architecture sketch, limitations
- Full test run green; one fresh-clone dry run of the quickstart
- [SUBMISSION.md](SUBMISSION.md): the four written answers, drawn from DECISIONS.md
- Short demo video (ingest → filtered GET → chat with follow-up)
- Push to GitHub

**Exit criteria:** fresh venv + README steps → working demo.

---

## Stretch (only if Phases 0–5 are done)

- Committed sample dataset so reviewers without keys can explore the API and chat's read tools
- Streaming chat responses (SSE)
- Chat tool that triggers ingest for an un-ingested ticker
- Multi-day movements (drawdowns / runs), not just single days
- SQLite FTS5 over article text for `search_articles`
- Dockerfile

## Out of scope

Auth, rate limiting, a durable job queue, Postgres, a frontend, intraday data, real-time updates. Each is named in the README's "what I'd do next" rather than half-built.
