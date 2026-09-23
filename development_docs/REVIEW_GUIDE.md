# Review guide for the debrief

Personal prep for walking the dev team through the repo. Not meant to be committed.

Total code is about 8,000 lines including the OpenAPI files and docs. The Python under `app/` is about 4,000 lines across 150 small files, and the ten files listed under "Today" are the ones that matter. Everything else is a schema, an enum, a constant or a one-function repository that those ten files call.

## How it fits together

Three layers, top to bottom. Nothing skips a layer.

| Layer | Directory | Job |
|---|---|---|
| API | `app/api/` | Routes. Parse the request, call one service function, return a schema. No logic. |
| Services | `app/services/` | All the logic: detection, news planning, explanation, the ingest pipeline, the read layer, the chat loop. |
| Repositories | `app/repositories/` | Every SQL query. Services never write SQLAlchemy queries themselves. |
| Providers | `app/providers/` | The three outside systems (yfinance, Exa, OpenAI), each behind a Protocol so tests swap in fakes. |

Around those: `app/models/` is one SQLAlchemy table per file, `app/schemas/` is one Pydantic model per file (split into `api`, `chat` and `llm`), `app/constants/` holds every tunable number with a comment saying why, `app/enums/` holds the string enums, `app/errors/` is one exception class per file all inheriting `AppError`, `app/prompts/` is the LLM prompts as Markdown templates, and `app/domain/` is small dataclasses passed between services.

`app/dependencies.py` is the only place that decides which concrete provider backs each Protocol. Tests override those functions.

Three flows to be able to draw on a whiteboard:

1. **Ingest.** `POST /tickers/{ticker}/ingest` creates a job row and starts a background task. The task fetches prices for the ticker, SPY, the sector ETF and the competitors, detects moves, plans news searches per tier, runs the ones not already cached, links articles to moves, then asks the LLM for an explanation of each move that needs one. Each stage commits and updates the job row.
2. **Read.** `GET /tickers/{ticker}` and its sub-resources parse `MovementFilters` from the query string, run one SQL query through `movement_queries.py`, and shape the rows into response schemas in `ticker_data.py`. No outside calls.
3. **Chat.** `POST /chat` builds a system prompt listing the ingested tickers, replays the earlier questions and answers, and loops: model, tool calls, tool results, model, up to six rounds. The tools call the same `ticker_data.py` functions the REST API uses. Citations are limited to URLs the tools returned.

## Today: one hour in four blocks

Read in this order. The line references are for the current `main`.

### Block 1: the pipeline (15 min)

- [pipeline.py](../app/services/pipeline.py). Start at `run_ingest` (line 97). It is the whole ingest in 50 lines: five stages, each ending in a `set_stage` call. Then `select_candidates` (line 38), the cost guard, and `needs_explanation` (line 50), which decides what gets re-explained on a re-run. Note the two `except` blocks at the bottom: an `AppError` message is public, anything else goes to the log only.
- [price_ingest.py](../app/services/price_ingest.py). One function. Read the docstring: fetch everything first, then write. This is the SQLite write-lock fix from the review (D21) and a likely question.
- [ingest_requests.py](../app/services/ingest_requests.py). How a request becomes a job, and the lock that stops two POSTs for one ticker both starting an ingest.

Be ready for: "What happens if the process dies mid-ingest?" Answer: `fail_interrupted_jobs` in `main.py` closes the job at the next start, and re-posting the ingest resumes at no cost because cached searches and existing explanations are skipped.

### Block 2: detection and the driver hint (15 min)

- [movements.py](../app/services/movements.py). Pure functions, no database. `detect_movements` (line 79) is the loop. `trailing_zscore` (line 27) uses `shift(1)` so the day being scored does not dampen its own score. `driver_hint` (line 41) and `benchmark_explains` (line 33) are the price-only heuristic for market, sector or idiosyncratic. The thresholds are in [constants/movements.py](../app/constants/movements.py): a benchmark explains a move when it went the same way, moved at least 1% itself, and covers at least 40% of the stock's move.
- [peers.py](../app/services/peers.py). The LLM suggests up to four competitors with tickers once per ticker, cached on the company row. `peer_moves_on` (line 112) gives their same-day moves, which feed the hint as a third benchmark and go into the prompt.

Be ready for: "Why 2%?" The brief suggested it, and it is a setting. The z-score is stored alongside because 2% means different things for different stocks. "Why is the hint never a filter?" Because the thresholds are hand-picked, so it orders the searches and goes into the prompt but every tier still runs (D4, D16).

### Block 3: news and explanations (15 min)

- [news/search.py](../app/services/news/search.py). `plan_searches` (line 28) makes one search per distinct tier, scope and window, so two moves in the same week share searches and macro searches are shared across tickers. `fetch_news` (line 57) checks the cache, runs what is missing in a thread pool, then links articles to moves on the main thread. Read the `is_settled` line (71): a search runs again on re-ingest until two days after its window closed.
- [news/registry.py](../app/services/news/registry.py) and [news/industry_tier.py](../app/services/news/industry_tier.py). A tier is a class with `build_query`, `cache_scope`, `tier` and `max_results`. Adding one is a file and a list entry. The industry tier puts a digest of the query in its cache key so a change of competitors invalidates the cache.
- [explain.py](../app/services/explain.py). `build_user_prompt` (line 50) fills the template, `prompt_articles` (line 80) caps what the model sees per tier, newest first. Then read [prompts/explain_movement_system.md](../app/prompts/explain_movement_system.md) in full. The rules about untrusted article text, `unexplained` being a good answer, weighing the benchmarks and competitors, and misdated articles are all there.
- [repositories/explanations.py](../app/repositories/explanations.py). Article ids the model invents are ignored and scores are clamped. An article counts as cited at relevance 0.5 or above.

Be ready for: "How do you know the explanation is right?" You checked known days by hand and did not measure it. An evaluation set is the first thing you would build next.

### Block 4: the API and chat (15 min)

- [api/tickers.py](../app/api/tickers.py). Seven routes. Note how thin they are: normalise the ticker, call a service, return. The ingest route is the only one with any branching (202 if a job was created, 200 if one was already running).
- [schemas/movement_filters.py](../app/schemas/movement_filters.py). One model is the query string, the chat tool arguments and the repository input. `extra="forbid"` makes a misspelt filter a 422.
- [repositories/movement_queries.py](../app/repositories/movement_queries.py). `_apply_filters` (line 19) is the one place filters become SQL. It only joins the explanation table when a filter needs it.
- [services/ticker_data.py](../app/services/ticker_data.py). The read layer. `to_article_responses` (line 54) applies the article-level filters and the cited-only default. `price_window` (line 117) is why prices default to the analysed period and not the warm-up history.
- [chat/chat_service.py](../app/services/chat/chat_service.py). `chat` (line 102) is the loop. `run_tool` (line 58) turns every failure into an error result the model can read. `replayable_history` (line 44) explains why tool calls are stored but not replayed. `citations_in` (line 91) is the URL check.
- [chat/tool_schema.py](../app/services/chat/tool_schema.py). Tool specs are generated from the Pydantic argument models, so adding a filter to `MovementFilters` also adds it to the chat tool.

Be ready for: "Why tool calling and not RAG?" The questions are structured (ticker, dates, direction, category), so SQL filters fit better than similarity search, and the chat cannot say anything the REST API cannot show (D8).

## Tomorrow: 30 minutes

1. Ten minutes: re-read `run_ingest`, `detect_movements`, `fetch_news` and `chat`. Those four functions are the system.
2. Ten minutes: skim [DECISIONS.md](DECISIONS.md) headings D1 to D24 and read D21 (review fixes), D23 (lean responses) and D24 (repeatability) in full. They are the decisions with the most story behind them.
3. Ten minutes: re-read your answers in [SUBMISSION.md](SUBMISSION.md), especially "Did you get stuck". Each item there has a decision number you can point to.

## Questions to expect, and where the answer lives

| Question | Where |
|---|---|
| Walk me through an ingest | `pipeline.py` `run_ingest`, then the job stages in `enums/ingest_stage.py` |
| How do you decide a move is major | `movements.py` `detect_movements`, D3 |
| How does the system tell company news from macro news | `movements.py` `driver_hint`, `registry.py` `TIER_PRIORITY`, the prompt rules, D4 and D20 |
| What does a re-run cost | `search.py` `is_settled` check, `pipeline.py` `needs_explanation`, D11 and D19 |
| What if the LLM makes something up | The prompt forbids outside knowledge, `save_explanation` drops unknown article ids, `citations_in` drops unknown URLs, D6 |
| What if Exa or OpenAI is down | `search.py` and `pipeline.py` record the failure per search or per move and carry on; the job row lists errors; nothing failed is cached, so the next run retries |
| Why SQLite | D2, and `db.py` for WAL and the busy timeout. Nothing to install for a reviewer. Swap the URL for Postgres and drop the WAL pragma |
| How is it tested | `tests/conftest.py` blanks the keys and uses an in-memory database, `tests/fakes/` has the three fake providers, `tests/test_robustness.py` has the real-file write-lock test |
| Why so many files | D10 and D14. One class per file was a deliberate rule. Say it is heavy for the size and you would accept that criticism |
| How would you scale this | Ingest becomes a queue worker, SQLite becomes Postgres, the provider Protocols and repositories stay. The `session_factory` argument to `run_ingest` is already the seam |
| What would you do next | An evaluation set of known events, scheduled re-ingest, fetching real page dates for cited articles (the misdated-article case in the README limitations) |

## Weak spots to own before they find them

- Accuracy was checked by eye on known days, never measured.
- Explanations can differ between runs. Temperature 0 and a seed narrowed it (D24) and did not remove it.
- Exa's publication dates are sometimes wrong. The prompt has a rule for it and it does not always catch it.
- Only single-day moves. A slow three-day slide is not detected.
- No auth, no rate limiting, no scheduled ingest, one process.
- The driver-hint thresholds are hand-picked numbers.

## Safe to skip

`app/schemas/`, `app/enums/`, `app/errors/`, `app/domain/` and `app/models/` are all declarations with no logic beyond a validator or two. `openapi/*.yaml` is generated by `scripts/export_openapi.py`. `app/utils/` is URL and text cleaning. The other chat tools follow the shape of `list_movements_tool.py`.
