# Decisions & tradeoffs

Choices made while planning and building that a reviewer (or future me) would reasonably question. Each notes why and when to revisit. New decisions get the next `D` number; deviations from [PLAN.md](PLAN.md) are recorded here, not silently absorbed. This file is the source material for [SUBMISSION.md](SUBMISSION.md).

---

## D1 — Precompute on ingest; API and chat are read-only views

**Status:** 📋 Planned.

**Decision:** An explicit ingest step does all the slow, paid work (yfinance, Exa, OpenAI) and stores results. `GET /tickers/{ticker}` and `/chat` only read the database.

**Why:** News search + LLM explanation for ~25 movements takes tens of seconds and costs money; doing it inside a GET makes the endpoint slow, non-deterministic and expensive to call twice. Stored results also make filters trivial (SQL) and chat answers reproducible.

**Tradeoff:** Data is as fresh as the last ingest, and a first-time ticker needs two calls (ingest, then read).

**Revisit:** Scheduled re-ingest / incremental "since last date" updates for a real deployment.

---

## D2 — SQLite + SQLAlchemy, `create_all`, no migrations

**Status:** 📋 Planned.

**Decision:** Single-file SQLite via SQLAlchemy 2; tables created on startup.

**Why:** Zero setup for the reviewer (no Docker, no DB server). SQLAlchemy keeps the swap to Postgres to a connection string. The data is relational (movement → articles → explanation) and filter-heavy, so a real DB beats JSON files even at this size.

**Tradeoff:** No schema migrations — a model change means deleting `data/app.db`. Single-writer; fine for one in-process ingest worker.

**Revisit:** Alembic + Postgres the moment there's a second deployment or data worth keeping.

---

## D3 — "Major movement" = |close-to-close| ≥ 2%, with a volatility z-score alongside

**Status:** 📋 Planned.

**Decision:** The gate is the prompt's own definition — absolute daily close-to-close change ≥ a configurable threshold (default 2%). Each movement also stores a z-score against trailing 60-day volatility, exposed as data and as context to the LLM, but not used as the gate.

**Why:** A flat 2% is easy to explain and matches the brief, but it's noisy for high-beta names and too strict for low-vol ones. Storing the z-score gets the insight without making the definition opaque. Close-to-close (not open-to-close) so overnight gaps from after-hours earnings count — that's where most company news lands.

**Tradeoff:** Single-day only; a slow 10% slide over two weeks is invisible.

**Revisit:** Multi-day drawdown/run detection (stretch).

---

## D4 — Use benchmark-relative returns to hint at the driver before searching

**Status:** 📋 Planned.

**Decision:** Fetch SPY and the ticker's sector SPDR ETF alongside the stock. For each movement compute excess return vs each and label a `driver_hint`: `market` (SPY moved similarly), `sector` (ETF moved, SPY didn't), or `idiosyncratic`.

**Why:** "Find macro news that explains this" is the hard tier mostly because it's unclear *when* macro is the answer. Price data answers that cheaply: if the whole market fell 3%, company headlines are likely noise. The hint orders the news tiers and is handed to the LLM as evidence, which should cut confident-but-wrong company attributions on macro days.

**Tradeoff:** It's a heuristic — a stock can fall on its own news on a down-market day. So it's a hint, never a filter; all tiers still run for top movements.

**Revisit:** Regression beta instead of raw excess return.

---

## D5 — Exa as the news source, behind a provider interface

**Status:** 📋 Planned.

**Decision:** Exa search (news category, published-date bounds, highlights) behind a small `NewsProvider` protocol. Macro-tier results are cached by date and shared across tickers. Peers for the industry tier come from one cached LLM call per ticker.

**Why:** Historical coverage is the deciding factor — NewsAPI's free tier only reaches back ~30 days, which makes a 1-year lookback impossible; yfinance news has no date filtering. Exa takes natural-language queries, which suits the industry and macro tiers where keyword search is weakest. Cost is negligible here ($7/1k searches; $20 signup credit; a 1-year ingest ≈ 75 searches). The protocol keeps tests offline and a second provider a small addition.

**API usage (per Exa's `build-with-exa` skill, checked 2026-09-18):** `/search` with `type="auto"`, `category="news"`, `start_published_date`/`end_published_date` (ISO 8601), and `contents={"highlights": True}` — bare highlights, one extraction mode only (stacking `text`/`summary` multiplies billing; synthesis happens in our own LLM pass, D6). Python SDK kwargs are snake_case. Avoid the deprecated `use_autoprompt`, `num_sentences`, `highlights_per_url`, `livecrawl`. Log `costDollars` from each response into the job row. Exa's Monitors API (scheduled searches + webhooks) is the fit for *ongoing* monitoring, not this historical backfill.

**Tradeoff:** Published-date bounds are **hard filters that drop undated or misdated pages**, so some relevant coverage is lost; the window is widened by a day on the trailing side to compensate for next-day write-ups. Semantic search can still return tangential pages; mitigated by the LLM relevance pass (D6). LLM-suggested peers could be wrong for obscure tickers — falls back to the industry string.

**Revisit:** Add a second provider and merge results; a curated peers source.

---

## D6 — LLM explains and ranks; "unexplained" is a first-class answer

**Status:** 📋 Planned.

**Decision:** One structured-output call per movement receives the move's stats, benchmark context (D4) and candidate articles, and returns summary, category, confidence and per-article relevance. The model may answer `unexplained`. Citations are article ids from the candidates only.

**Why:** Retrieval gives *candidates*; attribution is a judgement call. Forcing a cause for every move manufactures false explanations — the worst failure mode for this product. Structured output makes category/confidence filterable in the API. Restricting citations to supplied ids prevents invented URLs.

**Tradeoff:** Attribution is plausible, not causal, and the README says so. One call per movement rather than batching — simpler and parallelisable, slightly more tokens.

**Revisit:** Eval set of known events (earnings dates, FOMC days) to measure category accuracy.

---

## D7 — Ingest runs as an in-process background task with a job row

**Status:** 📋 Planned.

**Decision:** `POST /ingest` returns 202 and runs the pipeline via FastAPI `BackgroundTasks`; progress lives in `ingest_jobs` and is polled through a status endpoint. The pipeline is idempotent per movement.

**Why:** Ingest takes longer than a comfortable HTTP request. A real queue (Celery/RQ + Redis) is the production answer but adds infrastructure the reviewer must run. Idempotency is what makes the cheap option acceptable: a crash mid-ingest is recovered by re-posting, without repeating paid calls.

**Tradeoff:** Jobs die with the process and don't scale past one worker.

**Revisit:** Durable queue when there's more than one process.

---

## D8 — Chat uses tool-calling over the query layer, not embeddings/RAG

**Status:** 📋 Planned.

**Decision:** The chat model gets read-only tools that wrap the same `queries.py` functions as the REST endpoints. No vector store.

**Why:** Questions about this data are overwhelmingly structured — a ticker, a date range, a direction ("biggest drops in Q2", "what happened on Aug 5"). SQL filters answer those exactly; vector similarity answers them approximately. The corpus per ticker is small, and explanations are already distilled summaries. Sharing the query layer means chat can't drift from what the API returns.

**Tradeoff:** Free-text search across article content is only a `LIKE` match. Weak for "which moves were about antitrust?" across many tickers.

**Revisit:** SQLite FTS5 first; embeddings only if that proves insufficient.

---

## D9 — OpenAI as the LLM provider

**Status:** 📋 Planned.

**Decision:** OpenAI SDK for explanations and chat; model id from `OPENAI_MODEL`.

**Why:** Pragmatic — an OpenAI key already existed; setting up a second provider's billing inside a 4-hour window buys nothing the reviewer can see. Both uses (structured output, tool-calling) are standard features, and the LLM is touched in only two modules.

**Revisit:** A thin client interface if provider choice ever matters.

---

## D10 — One class per file

**Status:** ✅ Implemented (T1-1).

**Decision:** Every class lives in its own module: `app/models/<table>.py`, `app/domain/<dataclass>.py`, `app/errors/<exception>.py`. Packages re-export from `__init__.py` so call sites stay `from app.models import Price`. Pure functions may share a module.

**Why:** A file name tells you exactly what's in it, diffs stay scoped to one concept, and there's no ever-growing `models.py`. Cross-model relationships use string targets + `TYPE_CHECKING` imports, so there are no circular imports.

**Tradeoff:** More files and a little import boilerplate for a project this size.

---

## D11 — Generic news-search cache instead of a macro-only date table

**Status:** ✅ Implemented in the schema (T1-1); used from T2-2.

**Decision:** PLAN.md's `macro_news_cache(date)` became `news_search_cache(cache_key → article_ids, cost)` — one row per executed search of any tier.

**Why:** Same mechanism gives both things we wanted: macro searches shared across tickers (their key has no ticker in it) *and* free idempotent re-ingest for company/industry searches. It also records Exa's per-search cost.

---

## D12 — Adjusted prices, with a warm-up fetch

**Status:** ✅ Implemented (T1-1).

**Decision:** Prices are fetched with `auto_adjust=True`, starting 100 calendar days before the requested window. Existing rows are overwritten on re-ingest.

**Why:** Unadjusted closes turn a 4:1 split into a fake −75% "movement". The warm-up means the trailing-volatility z-score is populated from the first requested day rather than ~3 months in. Overwrite (not insert-or-ignore) because adjusted history shifts after every dividend.

**Tradeoff:** Stored closes are adjusted values, not the prices printed on the day; percentage moves — what we care about — are correct.

---

## D13 — Driver-hint thresholds

**Status:** ✅ Implemented (T1-2).

**Decision:** A benchmark "explains" a move when it moved the same direction by at least `max(1.0%, 40% of the stock's move)`. Market is checked before sector.

**Why:** 1:1 matching would miss high-beta names that amplify the tape (SPY −2.5%, stock −6% is still a market day); the 1% floor stops a drifting index from "explaining" anything. On AAPL's last year this splits 40 moves into 23 idiosyncratic / 11 sector / 6 market, which passes the smell test.

**Tradeoff:** Hand-picked constants, not fitted. They only order searches and inform the prompt, so a wrong hint degrades gracefully.

**Revisit:** Per-ticker beta from a regression.

---

## D14 — Conventions agreed up front; retrofit ticket T1-3

**Status:** ✅ Implemented (T1-3). Rules live in [CONVENTIONS.md](CONVENTIONS.md).

**Decision:** After Phase 1, pause for one ticket to fix the conventions for the rest of the build — constants modules, `StrEnum` vocabularies, Protocol-backed providers wired in one place, repositories for all DB access, typed errors with a single HTTP handler, prompts as files, ruff, pinned dependencies — and bring the existing code in line.

**Why:** Cheapest moment to do it: three modules to retrofit instead of fifteen. The rules target real duplication risks in the remaining phases (one enum feeding DB + API + LLM schema; one filter model feeding REST + chat) and the seams the brief names (news source, news tier, LLM). `services/prices.py` was split along those lines into a yfinance adapter, two repository modules and a `price_ingest` service.

**Tradeoff:** ~15 minutes of a 4-hour budget on structure rather than features, and more files than a project this size strictly needs. Guard rail: "seams, not speculation" — no abstraction without a variation point the brief implies.

---

## D15 — `refresh` re-explains; caches still hold

**Status:** ✅ Implemented (T2-2).

**Decision:** Ingest skips movements that already have an explanation. `refresh=true` re-selects them, but cached searches are still never repeated — so a refresh costs the LLM calls plus only the searches that are genuinely new.

**Why:** Needed the moment a tier was added: AAPL's explanations had been written from company news alone. Refresh picked up 52 new industry/macro searches while reusing all 23 company searches. Same mechanism covers a prompt or model change.

**Tradeoff:** No way to force a *search* re-run short of deleting cache rows. Fine for historical windows, whose news doesn't change; wrong for a window that includes today.

**Revisit:** Expire cache rows whose window ended less than N days before they were fetched.

---

## D16 — Every tier runs for every selected movement

**Status:** ✅ Implemented (T2-2).

**Decision:** The driver hint (D4) orders tiers and labels shared articles, but does not skip tiers: each of the top-N movements gets company, industry and macro searches (8/5/5 results).

**Why:** The hint is a heuristic; skipping the company search on a "market" day would hide the case where a stock fell on its own news during a sell-off. Letting the LLM see all three tiers, plus the benchmark numbers, produced sensible splits live (AAPL: 17 company / 5 industry / 3 macro). Cost stays small because macro is shared and everything is cached: ~$0.50 for a first ticker, less for later ones.

**Tradeoff:** ~3x the searches of a hint-gated design, and ingest time is dominated by them (~60 s for 75 searches at 4 workers). Measured, accepted.

**Revisit:** Raise `NEWS_MAX_WORKERS` once Exa's rate limit for the account is known; or gate the macro tier on `abs(market move) >= 1%`.
