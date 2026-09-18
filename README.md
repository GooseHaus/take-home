# Stock Movement Explainer

Give it a ticker. It fetches a year of prices, finds the days the stock made a major move, searches the news around each one at three levels — **company**, **industry/competitors**, **macro** — and has an LLM write a short, cited explanation with a category and a confidence score. Then query everything through a REST API, or just ask questions in a chat endpoint.

```
$ curl -s localhost:8000/chat -H 'content-type: application/json' \
    -d '{"message": "Why did AAPL drop at the end of July?"}'

AAPL dropped 7.35% on 2026-07-31 because of a company-specific post-earnings selloff … weak forward guidance,
with supply-chain and memory-chip constraints weighing on the outlook … classified as a company move with 0.97
confidence.   [CNBC] [Investor's Business Daily] [Reuters]
```

**Stack:** Python 3.11 · FastAPI · SQLite (SQLAlchemy 2) · yfinance · [Exa](https://exa.ai) for news · OpenAI for explanations and chat.

---

## Quickstart

You need Python 3.11+, an [Exa API key](https://dashboard.exa.ai/api-keys) (free tier is plenty) and an OpenAI API key.

```bash
git clone https://github.com/GooseHaus/take-home.git && cd take-home
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then fill in EXA_API_KEY and OPENAI_API_KEY
uvicorn app.main:app
```

Interactive docs: <http://localhost:8000/docs>. `GET /health` tells you whether both keys were picked up.

Run the tests (offline — no keys or network needed):

```bash
pip install -r requirements-dev.txt
pytest
ruff check . && ruff format --check .
```

---

## Walkthrough

### 1. Ingest a ticker

```bash
curl -s -X POST localhost:8000/tickers/AAPL/ingest
```

Returns `202` with a job; the work runs in the background (about a minute for a first ticker, ~$0.50 of Exa credit and a few cents of OpenAI). Poll it:

```bash
curl -s localhost:8000/tickers/AAPL/status
```

```json
{ "status": "done", "stage": "complete",
  "detail": { "movements": 40, "selected": 25, "explained": 25,
              "news": { "searches_run": 75, "searches_cached": 0, "cost_dollars": 0.525 }, "errors": [] } }
```

The body is optional. Everything has a default:

```bash
curl -s -X POST localhost:8000/tickers/MSFT/ingest -H 'content-type: application/json' \
  -d '{"start": "2026-01-01", "end": "2026-06-30", "threshold_pct": 3, "max_movements": 10}'
```

| Field | Default | Meaning |
|---|---|---|
| `start` / `end` | last 365 days | Period to analyse (`lookback_days` is an alternative to `start`) |
| `threshold_pct` | `2.0` | What counts as a major move: absolute close-to-close change, in percent |
| `max_movements` | `25` | Cost guard — only the N largest moves get news searches and an explanation |
| `refresh` | `false` | Re-explain moves that already have an explanation |

**Ingest is idempotent.** Re-posting never repeats a news search or an explanation it has already paid for (a re-run takes under a second). A second ticker reuses the macro searches the first one paid for.

### 2. Get all stock and news data for a ticker

```bash
curl -s "localhost:8000/tickers/AAPL"
```

One response: company profile, daily prices, every major movement, and for each its explanation and articles.

```json
{
  "date": "2026-07-31", "pct_change": -7.35, "zscore": -4.1, "volume_ratio": 2.6,
  "market_pct_change": 0.72, "sector_pct_change": -0.22, "driver_hint": "idiosyncratic",
  "explanation": { "category": "company", "confidence": 0.97,
                   "summary": "Apple fell 7.35% … after its earnings report and a weak forward forecast …" },
  "articles": [ { "title": "Apple disappoints with forecast dogged by supply chain struggles | Reuters",
                  "url": "https://www.reuters.com/…", "tier": "company", "relevance": 0.96, "cited": true } ]
}
```

Filters (all optional, all combinable):

| Filter | Example | Effect |
|---|---|---|
| `start`, `end` | `start=2026-01-01&end=2026-03-31` | Date range (also bounds the prices returned) |
| `direction` | `direction=down` | Only losses / only gains |
| `min_abs_change` | `min_abs_change=4` | Moves of at least 4% either way |
| `category` | `category=macro` | `company` · `industry` · `macro` · `unexplained` |
| `driver_hint` | `driver_hint=market` | What prices alone suggested: `market` · `sector` · `idiosyncratic` |
| `min_confidence` | `min_confidence=0.8` | Explanation confidence |
| `explained_only` | `explained_only=true` | Drop moves outside the explained top-N |
| `tier`, `min_relevance` | `min_relevance=0.5` | Narrow the **articles shown** inside each movement (never drops movements) |
| `sort` | `sort=magnitude` | `date_desc` (default) · `date_asc` · `magnitude` |
| `limit`, `offset` | `limit=10` | Pagination over movements; `total_movements` is the unpaged count |
| `include_prices`, `include_news` | `include_prices=false` | Trim the response |

```bash
# The market-driven sell-offs, with only the articles the explanation relied on
curl -s "localhost:8000/tickers/AAPL?direction=down&category=macro&min_relevance=0.5&include_prices=false"

# One movement in full, with every article that was considered
curl -s localhost:8000/tickers/AAPL/movements/2026-07-31

# What has been ingested
curl -s localhost:8000/tickers
```

### 3. Chat with the data

```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message": "Why did AAPL drop at the end of July?"}'
```

```json
{ "conversation_id": "3f2a…",
  "answer": "AAPL dropped **7.35% on 2026-07-31** because of a company-specific post-earnings selloff …",
  "citations": [ { "title": "Apple (AAPL) Q3 2026 earnings report: Live updates", "url": "https://www.cnbc.com/…", "source": "cnbc.com" } ],
  "tool_calls": [ { "name": "list_movements", "arguments": { "ticker": "AAPL", "start": "2026-07-25", "end": "2026-07-31", "direction": "down" } } ] }
```

Pass `conversation_id` back for follow-ups:

```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"conversation_id": "3f2a…", "message": "Was that just Apple, or was the whole market down that day?"}'
```

Things worth trying: *"Which of Microsoft's big moves this year were macro or industry-driven?"* · *"What were AAPL's three biggest drops and what caused them?"* · *"Which moves involved tariffs?"* · *"How did MSFT do in Q2?"* · a ticker you haven't ingested (it tells you how to ingest it rather than guessing).

The chat model can only read: it answers through five tools that wrap the same queries as the REST endpoints. `citations` lists the articles the answer links to — restricted to URLs the tools actually returned — and `tool_calls` shows which lookups the answer was built from. `GET /chat/{conversation_id}` returns the transcript.

---

## How it works

```
            POST /tickers/{t}/ingest  ──►  202 + job row
                      │ background task
   ┌──────────────────▼────────────────────────────────────────────────┐
   │ 1. prices       yfinance: the ticker, SPY, and its sector ETF      │
   │ 2. movements    |close-to-close| ≥ 2%  + z-score, volume ratio,    │
   │                 excess return vs market & sector → driver hint     │
   │ 3. news         Exa, three tiers per movement, cached by key       │
   │                 company · industry (+LLM-suggested peers) · macro  │
   │ 4. explanation  OpenAI structured output: summary, category,       │
   │                 confidence, per-article relevance                  │
   └──────────────────┬────────────────────────────────────────────────┘
                      ▼
                   SQLite
                      ▲
        ┌─────────────┴──────────────┐
 GET /tickers/{t} (+filters)     POST /chat
        └──── one shared read layer + one MovementFilters model ────┘
```

**The key ideas**

- **Do the expensive work once.** Ingest makes every paid call and stores the result; the data endpoint and chat are read-only views. Filters are SQL, answers are reproducible, and nothing is billed twice.
- **Let prices say where to look.** Before any search, each move is compared with SPY and the stock's sector ETF. If the whole market fell 3%, company headlines that day are probably noise. That `driver_hint` orders the news tiers and is given to the LLM as evidence — it's how the [Hard] macro tier gets answered sensibly: every AAPL move the prices flagged as market-driven came back categorised `macro`.
- **"Unexplained" is an allowed answer.** The model must cite from the candidate articles it was given and may say the evidence doesn't account for the move. Three of MSFT's 25 explained moves came back `unexplained` rather than invented.
- **One definition per concept.** `MovementFilters` is the REST query string, the chat tool's arguments (its JSON schema is generated from the model) and the repository's input. Enums type the DB columns, the API, and the LLM's structured output alike.
- **Seams where the brief implies variation.** News source, LLM and market data sit behind Protocols wired in one file; news tiers and chat tools are registries of small classes — adding the industry and macro tiers was two files and one registry line.

### Layout

```
app/
  api/            thin routers                 services/      orchestration + pure logic (movements.py does no I/O)
  repositories/   all database access          providers/     yfinance · Exa · OpenAI, each behind a Protocol
  models/ domain/ schemas/ enums/ errors/      one class per file
  constants/      fixed values                 prompts/       LLM prompts as reviewable .md files
  dependencies.py the wiring                   config.py      env-driven settings
tests/            120 offline tests; fakes/ implement the Protocols
development_docs/ roadmap, tickets, conventions and the decision log
```

`development_docs/` is how this was built: [ROADMAP](development_docs/ROADMAP.md) (phases with timeboxes and cut lines), [PLAN](development_docs/PLAN.md) (tickets, with what shipped and the live numbers), [CONVENTIONS](development_docs/CONVENTIONS.md), and [DECISIONS](development_docs/DECISIONS.md) — 18 entries, each with the tradeoff and when to revisit. [SUBMISSION](development_docs/SUBMISSION.md) has the written answers.

### Configuration

| Variable | Default | |
|---|---|---|
| `EXA_API_KEY` | — | Required for ingest |
| `OPENAI_API_KEY` | — | Required for ingest and chat |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Any chat-completions model with structured output and tool calling |
| `DATABASE_URL` | `sqlite:///data/app.db` | |
| `MOVE_THRESHOLD_PCT` | `2.0` | Default major-move cutoff |
| `MAX_MOVEMENTS_WITH_NEWS` | `25` | Default cost guard |
| `LOG_LEVEL` | `INFO` | Every paid call logs its latency and cost |

Without keys the app still boots and serves anything already ingested; ingest and chat return a `503` naming the missing key.

---

## Limitations, honestly

- **Attribution is plausible, not causal.** An explanation says which news most likely accounts for a move, with a confidence; it is not proof, and it is not investment advice.
- **Single-day moves only.** A slow 10% slide over two weeks is invisible to a daily threshold.
- **News recall depends on Exa's date metadata.** Published-date bounds are hard filters, so undated or misdated pages are missed; the search window is padded by a day to compensate.
- **Background jobs are in-process.** A restart mid-ingest loses the job (re-post it — completed work is kept). Fine for one process; a real deployment wants a durable queue.
- **SQLite, no migrations.** A schema change means deleting `data/app.db`.
- **No auth or rate limiting**, and `search_articles` is a substring match rather than full-text search.
- **Cached searches don't expire**, which is right for history and wrong for a window that includes today.

**What I'd do next:** an evaluation set of known events (earnings dates, FOMC days) to measure category accuracy rather than eyeball it; multi-day drawdowns and runs; a durable job queue and Postgres; incremental "since last ingest" updates; SQLite FTS5 (then embeddings if needed) for article search; streaming chat responses.
