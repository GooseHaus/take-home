# Submission answers

> DRAFT. Edit before submitting, then delete this note. Question 1 is factual. Questions 2 to 4 ask for your own view.

## 1. Process from start to finish

I planned before writing code. The roadmap has six timeboxed phases, each with an exit criterion and a note on what to cut if it overran. There is also a ticket plan and a decision log, all in `development_docs/`. I worked with Claude Code as a pair. I set the architecture, the conventions and the git workflow and reviewed each ticket. It wrote most of the code. Each ticket finished with offline tests, a lint pass and one live run against the real APIs.

Assumptions:

- Daily prices are enough.
- The news period for a move runs from the previous trading day to the day after. That covers after-hours earnings, weekends and next-day coverage.
- A reviewer should be able to run it with two API keys and nothing else to install.
- An explanation is a likely cause, not a proven one.

Main decisions and tradeoffs:

- Ingest does all the paid work once and stores it. The data endpoint and chat only read (D1). News search and LLM calls for 25 moves take about a minute and cost money, so they don't belong in a GET. The cost is that data is only as fresh as the last ingest.
- A major move is an absolute close-to-close change of 2% or more, as the brief suggests (D3). I also store a z-score against recent volatility, because 2% means something different for KO than for TSLA. Prices are split-adjusted so a split isn't detected as a crash (D12). Only single-day moves are covered.
- Prices decide where to look for news (D4). Each move is compared with SPY and the sector ETF, which gives a hint of `market`, `sector` or `idiosyncratic`. The hint orders the searches and goes into the LLM prompt. This was my approach to the hard tier: finding macro news is easy, knowing when macro is the answer is not. In testing, every AAPL move with a market hint was categorised `macro`. The thresholds are hand-picked, so it is only a hint and never filters anything out.
- Exa for news (D5), because it can search back a full year. NewsAPI's free tier only goes back about 30 days. The three tiers are small strategy classes. Macro searches don't depend on the ticker, so their cache is shared between tickers. Exa's date filter drops undated pages, which costs some coverage.
- Competitor prices do the same job for the industry tier (D20). The LLM suggests competitors with tickers, ingest fetches their prices, and each explanation sees how they moved that day. Competitors moving together points to an industry cause, and a stock moving alone points to a company cause.
- The LLM can answer `unexplained` and can only cite the articles it was given (D6). Inventing a cause for every move would be the worst way for this to fail.
- Chat uses tool calling over the same queries as the REST API, not embeddings (D8, D18). Questions about this data are structured (ticker, dates, direction), so SQL filters are a better fit than similarity search. One `MovementFilters` model is the query string, the chat tool schema and the repository input (D17).
- SQLite and in-process background jobs (D2, D7), so there is nothing to set up. This is acceptable because ingest can be repeated safely: if a job dies, posting it again resumes it at no extra cost.
- I agreed the code conventions after Phase 1 (D14) and spent one 15-minute ticket bringing the existing code in line.
- Build order: I got the whole pipeline working with company news only, then added the industry and macro tiers. If I had run out of time I would still have had a complete system for the easy tier.

## 2. Are you happy with your solution?

Mostly. It covers everything in the brief, and I think the price-based hint is a good answer to the macro tier. It fails honestly: unexplained moves, tickers that aren't ingested and provider errors are all reported as what they are. It is cheap to run (about $0.50 and a minute for a first ticker, nothing for a re-run) and the 181 tests run offline.

What I'm less happy with:

- I checked accuracy by looking at known days (an earnings miss, market-wide selloffs). I did not measure it, so I can't say how often the category is right.
- Fresh news depends on someone running ingest again. There is no schedule.
- Ingest is slower than it needs to be. I limited Exa to 4 parallel searches because I didn't know the rate limit.
- There are a lot of files for a project this size. That was a deliberate choice for extensibility, but a reviewer could fairly call it heavy.

## 3. What would you do differently?

- Build a small evaluation set first: 20 to 30 known events with the expected category, and tune the prompts and thresholds against it.
- Agree the conventions before writing any code, not after Phase 1.
- Only run the macro search when the market actually moved that day. That would cut about a third of the searches.
- Think about re-ingest from the start. I first cached every search permanently, which was wrong for a move from yesterday, and I fixed it late (D19).

## 4. Did you get stuck anywhere?

Nothing blocked me for long. Seven things cost time:

- FastAPI stopped reading my filter model from the query string, and every request returned 422. A Pydantic model is only read as query parameters when it is the endpoint's only query parameter, and I had added two separate flags next to it. I found it by calling the endpoint directly and reading the error location. The fix was a small subclass that includes the flags (D17).
- A field named `date` shadowed the `date` type and broke the annotations after it, first in a SQLAlchemy model and later in a Pydantic schema. The fix was `import datetime as dt`.
- In-memory SQLite gives each connection its own empty database, so tests couldn't see the tables until the engine used a single shared connection.
- A final review found that the pipeline held SQLite's write lock while it waited on network calls, so a chat request or a second ingest during that window failed with "database is locked". My tests could not see it because they all shared one in-memory connection. I changed the pipeline to fetch first and write afterwards, and added a test on a real database file that fails against the old code (D21).
- My first "all data" response was 633 KB for one ticker. I only noticed when I ran the documented request myself. 85% of it was search results the explanation had rejected. The default now returns the cited articles without excerpts (134 KB), and the rest is behind two parameters and two sub-resources (D23).
- My README did not work on Windows. I followed it myself from a fresh clone in the Command Prompt and hit `cp`, single-quoted JSON in curl, and `curl -s` hiding the fact that the server was not running. The earlier dry run had passed because it ran in Git Bash. I rewrote the commands so they work in both shells and verified them in cmd (D22).
- Three tests passed only on my machine. A dry run from a fresh clone, with a new venv and no `.env`, showed they were using my real API key because they never injected a fake LLM. The test setup now blanks the keys, so local runs behave like CI.

One design change came from testing. After I added the industry and macro tiers, moves that were already explained were skipped, so they never saw the new articles. I added a `refresh` flag that re-explains a move without repeating any cached search (D15). Later, a question about stale news led to D19: searches for recent moves run again until the news settles, and recent moves are always explained.
