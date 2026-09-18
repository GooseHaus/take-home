# Submission answers

> **DRAFT — edit before submitting.** Written from [DECISIONS.md](DECISIONS.md) and the build log so the facts are right, but questions 2–4 ask for your view, so put them in your own words. Delete this note before submitting.

## 1. Process from start to finish — assumptions, decisions, tradeoffs

**Plan first, with cut lines.** Before writing code I wrote a roadmap of six timeboxed phases, each with an exit criterion and a "what to drop if this overruns" line, plus a ticket plan and a decision log ([development_docs/](.)). I worked with Claude Code as a pair throughout: I set the architecture, conventions and workflow and reviewed each ticket; it did most of the typing. Every ticket ended with offline tests, a lint pass and one live smoke run, recorded in PLAN.md.

**Assumptions:** daily granularity is enough; the news "period" for a move is the previous trading day through the day after (covers after-hours earnings, weekends and next-day write-ups); a reviewer should be able to run it with two API keys and no infrastructure; explanations are plausible attributions, not causal claims.

**Key decisions and their tradeoffs**

- **Precompute on ingest; API and chat are read-only (D1).** News search + LLM calls for 25 moves take ~a minute and cost money, so they happen once, in a background job, and are stored. Filters become SQL and chat answers are reproducible. *Cost:* data is only as fresh as the last ingest, and a new ticker takes two calls.
- **"Major move" = |close-to-close| ≥ 2%, as the brief suggests, with a volatility z-score stored alongside (D3).** Simple to explain, and the z-score keeps the insight that 2% means different things for KO and TSLA. Adjusted prices so splits don't register as crashes (D12). *Cost:* single-day only.
- **Use prices to decide where to look (D4).** Each move is compared with SPY and the sector ETF to produce a `market / sector / idiosyncratic` hint, which orders the searches and is given to the LLM as evidence. This was my answer to the [Hard] tier: the difficulty isn't finding macro news, it's knowing *when* macro is the answer. Live, every market-hinted AAPL move was categorised `macro`. *Cost:* hand-picked thresholds; so it's a hint, never a filter.
- **Exa for news (D5).** Historical reach decided it — NewsAPI's free tier covers ~30 days. Three tiers as strategy classes; macro searches are ticker-independent, so their cache is shared across tickers. *Cost:* published-date filters are hard, so undated pages are lost.
- **LLM explains and ranks; "unexplained" is allowed (D6).** Structured output typed by the same enums as the DB and API; citations restricted to supplied article ids. Forcing a cause for every move is the worst failure mode for this product.
- **Chat = tool-calling over the REST read layer, not embeddings (D8, D18).** Questions here are structured (ticker, dates, direction), so SQL filters beat similarity search. One `MovementFilters` model serves the query string, the chat tool schema and the repository (D17), so they can't drift. Citations are limited to URLs the tools returned.
- **SQLite, in-process background jobs (D2, D7).** Zero setup for the reviewer. Idempotent ingest is what makes this acceptable: a crashed job is recovered by re-posting, at no cost.
- **Conventions agreed after Phase 1 (D14):** one class per file, constants and enums, Protocol-backed providers, repositories, typed errors. One 15-minute retrofit ticket while there were three modules to change rather than fifteen.
- **Build order:** close the loop with company news only, *then* add industry and macro — so a blown timebox would still have left a complete [Easy] system. Adding the two harder tiers was two files and a registry line.

## 2. Are you happy with your solution?

Mostly yes. It does what the brief asks end to end, the hard tier is handled by an idea I'd defend (price-relative hints) rather than by more searching, and it fails honestly — unexplained moves, un-ingested tickers and provider outages all surface as what they are. It's cheap (~$0.50 and a minute for a first ticker; a re-run is free) and the 120 tests run offline.

What I'm less happy with: accuracy is *eyeballed*, not measured — I checked known days (an earnings miss, market-wide sell-offs) but have no evaluation set, so I can't say how often the category is right. Ingest is slower than it should be because I capped Exa concurrency at 4 without knowing the rate limit. And it's more files than a project this size strictly needs — a deliberate choice for extensibility that a reviewer could fairly call heavy.

## 3. What would you do differently?

- **Build a small eval set first** — 20–30 known events (earnings dates, FOMC days, sector shocks) with expected categories — and tune prompts and thresholds against it instead of by inspection.
- **Agree conventions before the first line of code**, not after Phase 1; the retrofit was cheap but avoidable.
- **Gate the macro search on the market actually moving** rather than running all three tiers for every move (D16) — roughly a third fewer searches for the same answers.
- With more time: multi-day drawdowns, a durable job queue + Postgres, incremental re-ingest, cache expiry for windows that include today, FTS for article search, streaming chat.

## 4. Did you get stuck anywhere?

Nothing blocked for long, but three things cost time:

- **FastAPI silently stopped reading my filter model from the query string** — every request returned 422 "field required". Cause: a Pydantic model is only treated as query parameters when it's the endpoint's *sole* query parameter, and I'd added two loose flags beside it. Found it by hitting the endpoint directly and reading the error's `loc`; fixed with a small subclass that carries the flags (D17).
- **A field named `date` shadowing the `date` type** broke annotations, first in a SQLAlchemy model and later in a Pydantic schema. Fixed with `import datetime as dt`; the second time I recognised it immediately.
- **In-memory SQLite gives each connection its own empty database**, so tests saw missing tables until the engine used a single shared connection (`StaticPool`).

One design correction rather than a bug: after adding the industry and macro tiers, already-explained moves were skipped by the idempotency logic, so they never saw the new evidence. That led to the `refresh` flag — re-explain, but still never repeat a cached search (D15).
