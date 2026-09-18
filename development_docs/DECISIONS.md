# Decisions and tradeoffs

Design choices a reviewer might question, with the reason for each and when to revisit it. Changes from [PLAN.md](PLAN.md) are recorded here too. All of these are implemented.

## D1. Ingest does the paid work; the API and chat only read

An explicit ingest step makes every yfinance, Exa and OpenAI call and stores the results. `GET /tickers/{ticker}` and `/chat` read the database.

Why: news search and explanations for about 25 moves take around a minute and cost money. Inside a GET that would be slow, non-repeatable and billed on every call. Stored results also make filters plain SQL.

Tradeoff: data is as fresh as the last ingest, and a new ticker needs two calls.

Revisit: scheduled or incremental re-ingest.

## D2. SQLite with SQLAlchemy, tables created on startup, no migrations

Why: nothing for the reviewer to install. The data is relational and filtered heavily, so a database fits better than files. SQLAlchemy keeps a move to Postgres small.

Tradeoff: a schema change means deleting `data/app.db`. One writer at a time.

Revisit: Alembic and Postgres once there is data worth keeping.

## D3. A major move is an absolute close-to-close change of 2% or more

The threshold is configurable. Each move also stores a z-score against trailing 60-day volatility. The z-score is shown in the API and given to the LLM but is not part of the cutoff.

Why: 2% is the brief's own example and is easy to explain. It is noisy for volatile stocks and strict for quiet ones, and the z-score covers that without making the definition harder to understand. Close-to-close is used so overnight gaps from after-hours earnings count.

Tradeoff: single-day moves only.

Revisit: multi-day drawdowns and runs.

## D4. Compare each move with the market and the sector before searching

SPY and the ticker's sector SPDR ETF are fetched with the stock. Each move gets a `driver_hint`: `market` if SPY moved similarly, `sector` if the ETF did and SPY didn't, otherwise `idiosyncratic`.

Why: the hard part of the macro tier is knowing when macro is the answer. Prices answer that cheaply. If the whole market fell 3%, company headlines that day are probably not the cause. The hint sets the search order and is given to the LLM as evidence.

Tradeoff: a stock can fall on its own news on a bad market day. The hint never filters anything out; every tier still runs.

Revisit: use a regression beta.

## D5. Exa for news, behind a provider interface

Why: it can search a full year back. NewsAPI's free tier covers about 30 days, and yfinance news has no date filter. Exa also accepts natural-language queries, which helps the industry and macro tiers. Cost is small: $7 per 1,000 searches with $20 of free credit.

Usage, following Exa's `build-with-exa` guidance: `/search` with `type="auto"`, `category="news"`, ISO published-date bounds and `contents={"highlights": True}`. Only one content mode is requested because each one is billed. The deprecated parameters (`use_autoprompt`, `num_sentences`, `highlights_per_url`, `livecrawl`) are not used. The cost reported by each response is stored. Exa's Monitors API is the right tool for ongoing monitoring, not for this historical backfill.

Tradeoff: the published-date filter drops undated and misdated pages. The window is extended by one day to catch next-day coverage. Competitor names come from one cached LLM call per ticker and could be wrong for obscure companies; the industry name is the fallback.

Revisit: a second provider, and a curated source for competitors.

## D6. The LLM explains and ranks, and may answer "unexplained"

One structured-output call per move receives the price stats, the benchmark context and the candidate articles. It returns a summary, a category, a confidence and a relevance score per article. Citations must be ids from the candidate list.

Why: search returns candidates, and deciding which one explains the move is a judgement. Forcing a cause for every move would produce false explanations. Structured output makes category and confidence filterable. Restricting citations to supplied ids prevents invented URLs.

Tradeoff: the result is a likely cause, not a proven one. One call per move costs a few more tokens than batching but is simpler and runs in parallel.

Revisit: an evaluation set of known events to measure category accuracy.

## D7. Ingest runs as an in-process background task with a job row

`POST /ingest` returns 202. Progress is stored in `ingest_jobs` and read through the status endpoint.

Why: ingest is too long for one request. Celery or RQ would be the production choice but adds infrastructure for the reviewer. Repeatable ingest makes the simple option acceptable: after a crash, posting again resumes without repeating paid calls.

Tradeoff: there is one worker, and a job interrupted by a restart is marked failed at the next start (D21).

Revisit: a durable queue.

## D8. Chat uses tool calling over the query layer, not embeddings

The chat model gets read-only tools that call the same functions as the REST endpoints.

Why: questions about this data are mostly structured: a ticker, a date range, a direction. SQL answers those exactly and similarity search answers them approximately. The data per ticker is small, and sharing the query layer keeps chat consistent with the API.

Tradeoff: free-text search over articles is a substring match.

Revisit: SQLite FTS5, then embeddings if that isn't enough.

## D9. OpenAI as the LLM provider

Why: I already had a key, and a second provider's setup would not have shown the reviewer anything new. The model id comes from `OPENAI_MODEL`, and the LLM is used in two places behind one interface.

## D10. One class per file

Models, dataclasses, schemas, exceptions, providers and tools each get their own module. Packages re-export from `__init__.py` so imports stay short. Functions can share a module.

Why: the file name says what is inside, and diffs stay small.

Tradeoff: more files and some import boilerplate.

## D11. One search cache for all tiers

PLAN.md had a macro-only cache keyed by date. It became `news_search_cache`, with one row per executed search of any tier.

Why: one mechanism gives both shared macro searches (their key has no ticker) and free re-ingest for the other tiers. It also stores the cost of each search.

## D12. Adjusted prices, fetched with extra history

Prices use `auto_adjust=True` and start 100 days before the requested window. Re-ingest overwrites existing rows.

Why: unadjusted prices turn a 4:1 split into a -75% move. The extra history means the z-score is available from the first requested day. Rows are overwritten because adjusted history changes after each dividend.

Tradeoff: stored closes are adjusted values, not the prices quoted on the day. Percentage moves are correct.

## D13. Driver hint thresholds

A benchmark explains a move when it moved the same way by at least 1%, or by 40% of the stock's move if that is larger. The market is checked before the sector.

Why: requiring a 1:1 match would miss high-beta stocks that amplify the market. The 1% floor stops a flat index from explaining anything. On a year of AAPL this gives 23 idiosyncratic, 11 sector and 6 market moves.

Tradeoff: the constants are hand-picked. They only affect search order and the prompt.

Revisit: a per-ticker beta.

## D14. Conventions agreed after Phase 1

One ticket (T1-3) wrote [CONVENTIONS.md](CONVENTIONS.md) and brought the existing code in line: constants modules, enums, provider Protocols wired in one place, repositories, typed errors with one HTTP handler, ruff, pinned dependencies.

Why: it was the cheapest time to do it, with three modules to change. The rules target real duplication, such as one enum used by the database, the API and the LLM schema.

Tradeoff: about 15 minutes of a 4-hour budget, and more files than the project strictly needs.

## D15. `refresh` re-explains without repeating searches

Ingest skips moves that already have an explanation. `refresh=true` selects them again, but cached searches are still reused.

Why: after the industry and macro tiers were added, AAPL's explanations had been written from company news only. A refresh ran 52 new searches and reused the 23 cached ones.

Tradeoff: there is no way to force a search to run again. That is fine for past dates and wrong for a window that includes today.

Resolved for recent windows by D19.

## D16. Every tier runs for every selected move

The driver hint orders the tiers but does not skip any. Each selected move gets company, industry and macro searches returning 8, 5 and 5 results.

Why: skipping the company search on a market day would hide a stock that fell on its own news during a selloff. With all three tiers and the benchmark numbers, the categories came out sensibly (AAPL: 17 company, 5 industry, 3 macro).

Tradeoff: about three times the searches, which is most of the ingest time (around 60 seconds for 75 searches with 4 workers).

Revisit: run the macro search only when the market moved at least 1%, and raise the worker count once the Exa rate limit is known.

## D17. One `MovementFilters` model

A single Pydantic model defines every filter. It is the REST query string, the chat tool arguments and the repository input. Movement fields select movements. `tier` and `min_relevance` only limit the articles shown inside each movement.

Why: otherwise the filters would exist in three hand-maintained copies. Keeping the article filters from removing movements means `min_relevance=0.5` reads as "show only the cited articles". Hiding weakly supported moves is what `min_confidence` is for.

Note: FastAPI reads a Pydantic model from the query string only when it is the endpoint's only query parameter. Two extra flags next to it made every request fail with 422. `TickerDataQuery` subclasses the filters to carry those flags.

Tradeoff: one response holds prices, movements and articles, so it can be large. `include_prices`, `include_news`, date bounds and pagination reduce it.

Change from the plan: a ticker that hasn't been ingested returns 404, not the 409 in ROADMAP. Nothing conflicts; the resource doesn't exist.

## D18. Store the whole conversation, replay only questions and answers

Every message of a chat turn is stored, including tool calls and results. A follow-up replays the last 12 user questions and final answers only.

Why: tool results are most of the tokens, and the answers already contain the dates and tickers a follow-up refers to. It also means trimming history can never separate a tool result from its call, which the API rejects. In testing, "was that just Apple?" led the model to fetch 2026-07-31 again on its own.

Tradeoff: a follow-up that needs earlier detail costs one more tool call. Messages are stored in chat-completions format, which ties storage to that format.

Citations are the articles whose URLs appear in the answer and were returned by a tool in that turn. `tool_calls` is returned as well so a reader can see which lookups were used.

## D19. Recent news is re-fetched until it settles, and recent moves are always explained

A cached search is final only if it ran at least 2 days after its news window closed. Until then a re-ingest runs it again and adds any new articles to the ones already found. Candidates for news are the N largest moves plus any move from the last 7 days. A move is explained when it has no explanation, when `refresh` is set, or when a search just brought in new articles.

Why: searches were cached permanently (D11, D15), so a move ingested the morning after it happened kept only that morning's coverage. The top-N cost limit also meant a small move from yesterday was detected but never explained. Both matter for anyone running ingest day to day.

All candidates go through the news step, including ones handled before. That is cheap, because a settled cached search is a database lookup. It also means a tier added later is picked up without `refresh`.

Tradeoff: a move's searches run again on each ingest during the 2 to 3 days after it, about $0.02 per move per run. If a re-run fails, the articles already found are kept. The constants (2 and 7 days) are hand-picked. Freshness still depends on someone running ingest.

Live check: TSLA over 30 days with the limit at 2 explained the two largest moves and also yesterday's +2.27% move, the smallest of the ten. A second run re-ran only that move's 3 searches, found nothing new and paid for no explanation. AAPL and MSFT, with no recent moves, re-ran from cache at no cost.

Revisit: a scheduled re-ingest, and settle times per tier.

## D20. Competitor prices as evidence for the industry tier

The LLM now suggests competitors with their Yahoo Finance tickers. Ingest fetches their price history. Each movement's explanation prompt lists how the competitors moved the same day, and the API and chat tools return the same `peer_moves`. If at least two competitors traded that day, their median move also counts as a benchmark for the driver hint: competitors moving together give a `sector` hint even when the broad sector ETF did not move.

Why: the industry tier was the weakest. On AAPL, explanations cited 103 company articles, 13 macro articles and only 4 industry articles, and nothing checked whether competitors actually moved. This applies the idea from D4 one level down: prices say when the industry is the answer, and the news says why.

No schema change. Competitors stay in the `companies.peers` JSON column as `{name, ticker}` objects, and their daily moves are computed from the `prices` table when needed. Rows written earlier hold plain names. They still load, and the next ingest asks the LLM once more to get tickers.

Tradeoff: up to four more yfinance fetches per ingest. LLM-suggested tickers can be wrong, so a ticker with no data is skipped and logged. Competitors listed in Asia close before the US session, so their same-date move lags by a day. The hint uses the median and needs at least two competitors, which limits the damage from one bad series.

Live check: an AAPL refresh upgraded its competitors to Samsung, Dell, Lenovo and HPE, loaded all four price histories, and re-explained 25 moves in 20 s with no new searches. Two moves changed hint from idiosyncratic to sector because competitors rose with Apple. One move (2026-04-22) changed from `industry` to `company`: with competitors mixed that day, the model cited the announced CEO transition.

Revisit: compare Asian listings with the next day's move, and use a curated competitor list.

## D21. Fixes from the pre-submission review

An independent review of the whole repo found one serious problem and several smaller ones. All of these are fixed and have regression tests in `tests/test_robustness.py`.

The serious one: the pipeline held SQLite's write lock across network calls. `ingest_prices` wrote the ticker's prices and then fetched SPY, the sector ETF and the competitors, and asked the LLM for competitors, all before the next commit. Any other write in that window failed after 5 seconds with "database is locked". That meant a 500 from `/chat` after its LLM calls were paid for, or a 500 from a second ticker's ingest, which is exactly what the README walkthrough does. The failure handler then hit the same lock and raised, leaving a job stuck as pending. No test saw it because every test shared one in-memory connection.

Fix: fetch everything first, then write and commit. No write transaction is ever open during a network call. The engine also uses WAL mode and a 30 second busy timeout. The failure path records the error with a fresh session and cannot raise. One test runs the pipeline on a real database file and writes from a second connection during every fetch. It fails against the old code and passes now.

Other fixes:

- A job left pending or running by a stopped server blocked that ticker forever. Startup now marks such jobs failed.
- Two POSTs for one ticker could both start a job. Job creation is now under a lock.
- Ingest requests are bounded: no future dates, at most 5 years, at most 50 explained moves, threshold at least 0.5%. Before, one unauthenticated request could ask for 200 moves, which is 600 searches.
- Datetimes lost their UTC offset in SQLite, so the same timestamp came back with and without a "Z". A `UTCDateTime` column type fixes that.
- When a move had more articles than fit in the prompt, the newest were dropped. Those are the "shares fell after" reports, the strongest evidence. Now each tier keeps its newest articles.
- Raising the threshold left the old smaller moves in place. Undetected moves without an explanation are now removed. Explained ones are kept because they were paid for.
- A zero average volume or a zero previous close produced infinity. Those values are now treated as missing.
- yfinance exceptions and unparsable Exa results become `ProviderError`, so one bad competitor or search no longer fails the job.
- A crashing chat tool is reported to the model as an error, not returned as a 500.
- A URL counts as cited only when the whole URL appears in the answer.
- Article search escapes `%` and `_`.
- A misspelt query parameter returns 422. It used to be ignored.
- Both system prompts say that article text is untrusted and must not be followed as instructions.
- Unexpected errors are logged in full but stored on the public job row only as the exception type.
- The industry search cache key includes a digest of the query, so results cached before competitors were known are not reused.

Left as is, on purpose:

- Validation errors use FastAPI's 422 body and application errors use `{"error": {...}}`. Unifying them is a small handler, but it changes every documented error example.
- `GET /tickers/{ticker}` returns 404 during the first seconds of a first ingest, before the company row exists. The status endpoint shows the running job.
- There is still no authentication or rate limiting (out of scope, see ROADMAP).
