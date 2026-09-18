# Build plan

Tickets in dependency order, with what shipped and the results of the live checks. Phases and cut lines are in [ROADMAP.md](ROADMAP.md), code rules in [CONVENTIONS.md](CONVENTIONS.md), reasoning in [DECISIONS.md](DECISIONS.md).

Status: all tickets done. 181 tests, ruff clean. The demo video and the written answers are the author's.

## Data model

| Table | Columns | Notes |
|-------|---------|-------|
| `companies` | `ticker` PK, name, sector, industry, sector_etf, peers (JSON) | Profile plus cached competitor names |
| `prices` | (`ticker`, `date`) PK, open, high, low, close, volume | Also holds SPY and sector ETF rows |
| `movements` | id, ticker, date, pct_change, zscore, volume_ratio, market and sector returns, driver_hint, window_start, window_end | Unique on (ticker, date) |
| `articles` | id, url (unique), title, source, published_at, snippet | Deduplicated by URL |
| `movement_articles` | movement_id, article_id, tier, relevance | Tier is company, industry or macro |
| `news_search_cache` | cache_key PK, article_ids (JSON), cost_dollars, fetched_at | One row per executed search (D11) |
| `explanations` | movement_id PK, summary, category, confidence, model, created_at | |
| `ingest_jobs` | id, ticker, status, stage, detail (JSON), error, started_at, finished_at | |
| `chat_messages` | id, conversation_id, role, content (JSON), created_at | |

## Environment

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | Explanations and chat | none |
| `OPENAI_MODEL` | Model id | `gpt-5.4-mini` |
| `EXA_API_KEY` | News search | none |
| `DATABASE_URL` | SQLite path | `sqlite:///data/app.db` |
| `MOVE_THRESHOLD_PCT` | Major-move cutoff | `2.0` |
| `MAX_MOVEMENTS_WITH_NEWS` | Cost limit per ingest | `25` |

`.env` is gitignored and `.env.example` is committed.

## Testing

All tests are offline and need no keys.

| Layer | Covers |
|-------|--------|
| Pure functions | Movement detection: threshold edges, z-score warm-up, driver hint, weekend news window |
| Providers and repositories | Exa call shape, result normalising, URL dedupe, price upsert, enum columns |
| Pipeline | Full run with fakes, free re-run, cost limit, partial failures, shared macro cache, refresh, news freshness |
| API | Every filter and every error response, against a seeded in-memory database |
| Chat | Tool loop with a scripted fake LLM: grounding, citations, tool errors, round limit, follow-ups |

Live calls to yfinance, Exa and OpenAI are a manual check per ticket. The results are noted below.

## Tickets

### Epic 0: Scaffold

**T0-1 Project skeleton.** Requirements, `.env.example`, package layout, settings, SQLite engine, `/health`.

### Epic 1: Prices and movements

**T1-1 Models and price ingest.** Nine tables. yfinance provider with adjusted prices and 100 days of extra history (D12), upsert by (ticker, date), sector to SPDR ETF map. An unknown ticker raises `TickerNotFound`. Live: 321 rows each for AAPL, SPY and XLK.

**T1-2 Movement detection.** Pure functions in `services/movements.py`: close-to-close change, trailing z-score, volume ratio, returns relative to the benchmarks, driver hint, news window. Live: AAPL over one year at 2% gives 40 movements (23 idiosyncratic, 11 sector, 6 market).

**T1-3 Conventions retrofit.** Wrote CONVENTIONS.md (D14) and brought the code in line: constants, enums with an `enum_column()` helper, `MarketDataProvider` protocol, repositories, `price_ingest` service, `dependencies.py`, `AppError` with one handler, ruff, pinned dependencies, test fakes and factories. The live AAPL run gave the same 40 movements.

### Epic 2: News and explanations

**T2-1 News provider.** `NewsProvider` protocol and `ExaNewsProvider`, using the call shape in D5. Articles are stored deduplicated by normalised URL, and snippets are cleaned and capped. Provider errors map to 502 and a missing key to 503. Live: a search for AAPL from 2026-07-30 to 08-01 returned 8 articles inside the window (Reuters, CNBC and IBD on the earnings guidance miss) for $0.007.

**T2-3 Explanation.** `LLMClient` protocol and OpenAI adapter. `ExplanationOutput` schema typed by `ExplanationCategory`. Prompts are files in `app/prompts/`. Article ids the model invents are ignored and scores are clamped to 0..1. Live on gpt-5.4-mini: AAPL 2026-07-31 (-7.35%) came back `company` at 0.98. AAPL 2026-01-20 (-3.46%, SPY -2.04%) came back `macro` at 0.72 using company news alone, citing 2 of 8 articles.

**T2-4 Pipeline and jobs.** `run_ingest` runs prices, movements, news and explanations, commits each stage, and records failures on the job row. News tiers are strategy classes in a registry. Searches are planned, deduplicated by cache key, fetched in parallel and linked. Network calls run in thread pools and all database writes stay on one thread. Failed searches and explanations are recorded, not cached, and retried on the next ingest. Live: AAPL over one year found 40 movements, selected 25 and explained 23 new ones in 28.8 s for $0.16. A re-run took 0.8 s with no paid calls.

**T2-2 Industry and macro tiers.** `IndustryTier` and `MacroTier` added to the registry, two files and one line. Result limits per tier are 8, 5 and 5. Competitor names come from one cached LLM call per ticker. `run_ingest` gained a `refresh` flag (D15). Live: an AAPL refresh ran 52 new searches and reused 23, for $0.36 in 62 s. Competitors were Samsung, Alphabet, Microsoft and Sony. Categories were 17 company, 5 industry and 3 macro, and every move with a market hint came back `macro`. MSFT's first ingest reused 6 macro searches from AAPL, and 3 of its moves came back `unexplained`.

T2-4 was built before T2-2 so the pipeline worked end to end with company news before the other tiers were added.

### Epic 3: Data API

**T3-1 Ingest and status endpoints, T3-2 Ticker data and filters.** One commit, because they share the router and its tests. Five routes in `api/tickers.py`. `MovementFilters` is the single filter definition (D17). Ten request and response schemas. `repositories/movement_queries.py` and `services/ticker_data.py` form the read layer that chat reuses. An ingest already running for the ticker is returned with 200 and not started again. A missing API key returns 503 before a job is created. A ticker that isn't ingested returns 404, not the 409 in ROADMAP (D17). Live: every route, filter and error checked with curl against the AAPL and MSFT data, including a free re-ingest.

### Epic 4: Chat

**T4-1 Tools and loop, T4-2 Conversations.** One commit, because the loop and its storage share a service and tests. `POST /chat` and `GET /chat/{conversation_id}`. Five tool classes behind a `ChatTool` protocol and a registry: `list_tickers`, `list_movements` (its arguments are `MovementFilters` plus a ticker), `get_movement`, `search_articles`, `price_summary`. Tool specs are generated from the Pydantic argument models. The loop allows 6 tool rounds and then forces an answer without tools. Tool failures are returned to the model as an error result. Citations are limited to URLs the tools returned. The whole conversation is stored, but only questions and final answers are replayed (D18).

Live on gpt-5.4-mini:

- "Why did AAPL drop at the end of July?" The model resolved the dates, made one `list_movements` call and answered correctly in 6 s, citing CNBC, IBD and Reuters.
- The follow-up "Was that just Apple, or the whole market?" called `get_movement` for 2026-07-31 and answered that it was mostly Apple, with the market up 0.72%.
- A question about MSFT's macro and industry moves was answered from one call with 4 citations and a note about an `unexplained` move.
- A question about TSLA, which isn't ingested, got the ingest instruction and no guess.

### Epic 5: Ship

**T5-1 README and CI.** Quickstart, a walkthrough with real outputs, a filter table, architecture, configuration and limitations. `.github/workflows/ci.yml` runs ruff and pytest with no secrets.

**T5-2 Fresh-clone dry run.** New clone, new venv, install from the pinned files, then pytest and ruff. It found a bug: three chat tests passed only where a real `.env` existed, because they never injected a fake LLM, so a missing key returned 503 where 422 was expected. `tests/conftest.py` now blanks both keys. After the fix the clone passed 121 tests. With no `.env` the app starts, `/health` reports both keys missing, and ingest and chat return 503 naming the key.

**T5-3 Written answers.** Drafted in [SUBMISSION.md](SUBMISSION.md). Questions 2 to 4 need the author's own words.

**T5-4 Demo video.** The author's. A suggested script is in [START_HERE.md](START_HERE.md).

### Epic 6: Follow-up

**T6-1 News freshness (D19).** `services/news/freshness.py` has two pure functions, `is_settled` and `is_recent`. `fetch_news` re-runs cached searches that are not settled, merges new articles with the ones already found, and reports which movements gained articles. The pipeline selects the N largest moves plus moves from the last 7 days, and explains a move only when it is new, refreshed or just gained articles. The clock is passed into `run_ingest` so tests control it. Job detail now reports `candidates`, `to_explain` and `searches_refreshed`. 10 new tests. Live: TSLA over 30 days with the limit at 2 explained the two largest moves plus yesterday's +2.27% move. A second run re-ran only that move's 3 searches ($0.02) and paid for no explanation. AAPL and MSFT re-ran from cache at no cost.

**T6-2 Competitor price moves (D20).** `PeersOutput` returns names with tickers. `services/peers.py` stores them, reads the older names-only format, fetches competitor prices and computes their move on a given day. The pipeline suggests competitors and loads their prices before detection. `driver_hint` takes the competitor median as a third benchmark. The explanation prompt has a competitor section, and `peer_moves` is in `MovementResponse` and the chat tool output. 14 new tests. Live: AAPL refresh loaded prices for Samsung, Dell, Lenovo and HPE, re-explained 25 moves in 20 s with no new searches, moved two hints to `sector`, and corrected one `industry` verdict to `company`.

### Epic 7: Spec and review

**T7-1 OpenAPI files.** `python -m scripts.export_openapi` writes `openapi/openapi.yaml`, `tickers.yaml` and `chat.yaml`. The per-group files keep only the schemas they use. All three validate as OpenAPI 3.1. A test fails when the committed files are out of date. Routes now declare their 404, 422, 502 and 503 responses with an `ErrorResponse` schema.

**T7-2 Review fixes (D21).** An independent review plus my own checks. The main fix: the pipeline no longer holds SQLite's write lock during network calls. 18 regression tests in `tests/test_robustness.py`, including one on a real database file that fails against the old code. Live: two ingests and a chat request ran at the same time on the real server with no errors.

### Epic 8: After the manual test

**T8, T9 README on Windows (D22).** Windows quickstart, curl commands that work in cmd and bash, no `curl -s`, a health check first, an explicit conversation id placeholder.

**T10 Lean responses (D23).** `articles=cited|all|none` and `include_snippets` on the shared filters, with cited and no excerpts as the default. New `GET /tickers/{ticker}/movements` and `GET /tickers/{ticker}/prices`. Prices and the summary default to the analysed period, which fixes a leak of warm-up history. Measured on a year of AAPL: the default response went from 633 KB to 134 KB, `/movements` is 95 KB, `/prices` is 38 KB, and the five largest moves without prices are 21 KB. 7 new tests.

**T11 Repeatability (D24).** A third manual run showed one market-hinted AAPL move categorised `company`, contradicting a claim in the README. Structured LLM calls now use temperature 0 and a seed, with a fallback for models that reject them. Five repeats on identical evidence: default sampling gave 4 macro and 1 company for that move, the new settings gave 5 macro. The claim was corrected and the limitation documented. The README's piped curl example was fixed for Windows.
