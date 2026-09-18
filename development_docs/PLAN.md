# Build plan — tickets

**Goal:** ticker in → explained major movements out → queryable by REST and chat.

See also: [CONVENTIONS.md](CONVENTIONS.md) (how code is written here), [ROADMAP.md](ROADMAP.md) (phases, timeboxes, cut lines), [DECISIONS.md](DECISIONS.md) (choices & tradeoffs), [START_HERE.md](START_HERE.md) (live status).

> **Build status (2026-09-18):** T0-1, T1-1, T1-2, T1-3, T2-1, T2-3 done (45 tests, ruff clean). Next: T2-4 pipeline (company tier), then T2-2.

---

## Repo layout

```
take-home/
  app/
    main.py              ← FastAPI app, lifespan, the single AppError → HTTP handler
    config.py            ← pydantic-settings; deployer-tunable values + keys from .env
    dependencies.py      ← wiring: which adapter backs each Protocol
    db.py  logging_config.py
    api/                 ← thin routers (tickers, chat)
    services/
      price_ingest.py    ← provider → repositories for a ticker + its benchmarks
      movements.py       ← pure detection / z-score / driver hint / news window
      news/              ← tier strategy classes + registry            (T2-1/T2-2)
      explain.py  pipeline.py  chat/                                   (T2-3 → T4)
    repositories/        ← all DB access (prices, companies, movements, …)
    providers/
      market_data/       ← MarketDataProvider Protocol + YFinance adapter
      news/  llm/        ← NewsProvider + Exa, LLMClient + OpenAI      (T2-1, T2-3)
    models/  domain/  enums/  errors/  schemas/   ← one class per file (D10)
    constants/           ← fixed values, one module per domain
    prompts/             ← LLM prompt templates
  tests/                 ← offline; fakes/ implement the Protocols, factories.py builds seed data
  development_docs/
  pyproject.toml (ruff + pytest)  requirements.txt  requirements-dev.txt  .env.example
```

## Data model

| Table | Key columns | Notes |
|-------|-------------|-------|
| `companies` | `ticker` PK, name, sector, industry, sector_etf, peers (JSON) | profile + cached peers |
| `prices` | (`ticker`, `date`) PK, open, high, low, close, volume | also holds SPY / sector ETF rows |
| `movements` | id, ticker, date, pct_change, zscore, excess_vs_market, excess_vs_sector, driver_hint, window_start, window_end | unique (ticker, date) |
| `articles` | id, url (unique), title, source, published_at, snippet | deduped by URL across movements |
| `movement_articles` | movement_id, article_id, tier, relevance | tier = company / industry / macro |
| `news_search_cache` | cache_key PK, article_ids (JSON), cost_dollars, fetched_at | one row per executed search (any tier); macro keys are ticker-independent so they're shared (D11) |
| `explanations` | movement_id PK, summary, category, confidence, model, created_at | cited articles = `movement_articles.relevance` above a cutoff |
| `ingest_jobs` | id, ticker, status, stage, error, started_at, finished_at | in-process job tracking |
| `chat_messages` | id, conversation_id, role, content (JSON), created_at | |

## Environment

| Var | Purpose | Default |
|-----|---------|---------|
| `OPENAI_API_KEY` | explanations + chat | — (required for those features) |
| `OPENAI_MODEL` | model id | set in `.env.example` at build time |
| `EXA_API_KEY` | news search | — (required for ingest) |
| `DATABASE_URL` | SQLite path | `sqlite:///data/app.db` |
| `MOVE_THRESHOLD_PCT` | major-movement cutoff | `2.0` |
| `MAX_MOVEMENTS_WITH_NEWS` | cost guard per ingest | `25` |

`.env` is gitignored; `.env.example` is committed.

## Testing

**Add tests where behaviour is real and easy to break — all offline, no keys.**

| Layer | What |
|-------|------|
| Unit (pure) | `movements.py`: threshold edges, z-score warm-up, driver hint, weekend/holiday news window |
| Unit | tier query builders; explanation prompt assembly; article dedupe |
| API | FastAPI `TestClient` + in-memory SQLite + seeded rows: every filter, 404/409/422 paths |
| Chat | tool loop with a scripted fake LLM client: calls tool → gets rows → final answer carries citations; iteration cap |

Skip: live yfinance/Exa/OpenAI calls in tests (one manual smoke run per phase instead).

---

## Ticket breakdown

Ordered by dependency. One commit per ticket.

### Epic 0 — Scaffold

#### T0-1: Project skeleton ✅
- `requirements.txt`, `.env.example`, package layout, `config.py`, `db.py`, `/health`.
- **Done when:** `uvicorn app.main:app --reload` boots and `pytest` runs.

### Epic 1 — Prices & movements

#### T1-1: Models + price ingest ✅
- All tables in `models.py`. `prices.fetch_history(ticker, start, end)` and `fetch_profile(ticker)`; sector → sector-ETF map (11 SPDR funds). Upsert by (ticker, date).
- Unknown/empty ticker raises a typed error.
- **Done when:** AAPL + SPY + XLK rows land in SQLite.
- **Shipped:** `app/models/*` (9 tables), `services/prices.py` (adjusted closes, 100-day warm-up fetch, upsert), `TickerNotFound`. Live: 321 rows each for AAPL/SPY/XLK.

#### T1-2: Movement detection (pure functions) ✅
- `detect_movements(prices, market, sector, threshold)` → dataclasses. Close-to-close %, trailing-60d z-score (None during warm-up), excess returns, `driver_hint`, `news_window`.
- **Done when:** unit tests pass; AAPL 1y gives a plausible count (tens, not hundreds).
- **Shipped:** `services/movements.py` + 19 unit tests. Live AAPL 1y @2%: **40 movements** (23 idiosyncratic / 11 sector / 6 market). Also stores `volume_ratio` (vs trailing 20d).

#### T1-3: Conventions retrofit ✅
- Write CONVENTIONS.md (D14) and bring Phase 0–1 code in line.
- **Shipped:** `app/constants/{market,movements}.py`; `app/enums/` (DriverHint, NewsTier, ExplanationCategory, JobStatus, Direction) + `enum_column()` helper; `MarketDataProvider` Protocol + `YFinanceMarketDataProvider`; `repositories/{prices,companies}.py`; `services/price_ingest.py`; `dependencies.py`; `AppError` base + single exception handler; logging config; ruff + pytest config in `pyproject.toml`; pinned `requirements.txt` + `requirements-dev.txt`; `tests/fakes/`, `tests/factories.py`, `session` fixture. 27 tests. Live AAPL re-run through the new layers: identical 40 movements.

### Epic 2 — News & explanations

#### T2-1: NewsProvider + Exa ✅
- Protocol `search(query, start, end, limit) -> list[ArticleHit]`; `ExaProvider`; `FakeNewsProvider` for tests. URL dedupe on insert.
- Exa call shape (D5): `exa.search(query, type="auto", category="news", start_published_date=..., end_published_date=..., num_results=limit, contents={"highlights": True})`. snake_case kwargs; no deprecated params; record `costDollars`.
- **Done when:** a manual Exa call for a known date returns on-topic, in-window articles.
- **Shipped:** `providers/news/{news_provider,exa_news_provider}.py`, `domain/{article_hit,news_search_result}.py`, `repositories/articles.py` (URL-deduped upsert), `utils/{urls,text}.py` (tracking-param stripping, snippet cleaning), `constants/news.py`, `ProviderError` (502) / `ProviderNotConfigured` (503), `FakeNewsProvider`. 11 new tests incl. the exact Exa call shape. **Live:** AAPL 2026-07-30→08-01 → 8 in-window hits (Reuters/CNBC/IBD on the earnings guidance miss behind the −7.35% day), $0.007/search, re-upsert creates no duplicates.

#### T2-2: Tiered search
- Query builders for company / industry+peers / macro. Peers via one cached LLM call per ticker. Macro cached by date. Top-N cost guard; tier order from `driver_hint`.
- **Done when:** a movement ends up with articles tagged by tier; a second ticker reuses macro articles with zero new macro searches.

#### T2-3: Explanation ✅
- Structured-output call: movement stats + benchmark context + candidate articles → `{summary, category, confidence, article_relevance[]}`. `unexplained` allowed. Writes `explanations` + `movement_articles.relevance`.
- **Done when:** known earnings day → `company`; known market-wide day → `macro`; both cite URLs.
- **Shipped:** `LLMClient` Protocol + `OpenAILLMClient` (`chat.completions.parse`, retries, token/latency logging); `schemas/llm/{explanation_output,article_relevance}.py` typed by `ExplanationCategory`; prompts in `app/prompts/explain_movement_{system,user}.md` with a `$placeholder` loader; `services/explain.py` (prompt build split from the network call so the pipeline can parallelise); `repositories/{movements,explanations}.py`; `FakeLLMClient`. Invented article ids are ignored and scores clamped to 0..1. 7 new tests. **Live (gpt-5.4-mini):** AAPL 2026-07-31 −7.35% → `company` 0.98 (Reuters/CNBC/IBD guidance-miss pieces ≥0.93); AAPL 2026-01-20 −3.46% with SPY −2.04% → `macro` 0.72 *using company-tier news only*, citing 2 of 8 articles — the benchmark context (D4) is doing its job.

#### T2-4: Pipeline + jobs
- `run_ingest(ticker, ...)`: profile → prices → movements → news → explain, updating `ingest_jobs.stage`. Idempotent (skips finished movements). Bounded concurrency across movements. One failure marks that movement, not the job.
- **Done when:** re-running ingest on AAPL makes no new Exa/OpenAI calls.

### Epic 3 — Data API

#### T3-1: Ingest + status endpoints
- `POST /tickers/{ticker}/ingest` (body: period or start/end, threshold) → 202; `GET /tickers/{ticker}/status`. Duplicate in-flight ingest returns the existing job.

#### T3-2: Ticker data endpoint + filters
- `GET /tickers/{ticker}` with the filter set in ROADMAP Phase 3; queries live in `queries.py`. `GET /tickers` lists ingested tickers. `GET /tickers/{ticker}/movements/{date}`.
- **Done when:** API tests cover each filter and each error path.

### Epic 4 — Chat

#### T4-1: Tools + loop
- JSON-schema tool defs wrapping `queries.py`. Loop: model → tool calls → results → model, max 5 rounds. Collect cited URLs from tool results the model actually used.
- **Done when:** fake-LLM test passes; live question returns a grounded, cited answer.

#### T4-2: Conversations
- Persist messages by `conversation_id` (server-generated if absent); history replay truncated to the last N turns.
- **Done when:** a follow-up question resolves "that day" correctly.

### Epic 5 — Ship

#### T5-1: README + curl walkthrough
#### T5-2: Fresh-clone dry run, full test pass
#### T5-3: SUBMISSION.md answers
#### T5-4: Demo video, push

---

## Build order

```
T0-1 → T1-1 → T1-2 → T2-1 → T2-3 → T2-4 → T3-1 → T3-2 → T4-1 → T4-2 → T5-*
                          └─ T2-2 (industry + macro tiers) slots in after T2-4 works with company tier only
```

Company-tier-only through the pipeline first; widen to industry and macro once the loop is closed. That way a blown timebox still leaves a complete [Easy] system instead of a half-wired [Hard] one.
