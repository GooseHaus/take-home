# Diagrams

Mermaid diagrams of the system for the debrief. Companion to [REVIEW_GUIDE.md](REVIEW_GUIDE.md). GitHub, VS Code and most Markdown previewers render them.

## 1. Layers

Who is allowed to call whom. Arrows point from caller to callee, and nothing skips a layer.

```mermaid
flowchart TD
    Client([HTTP client])
    Client --> API

    subgraph API["app/api"]
        tickers[tickers.py]
        chat[chat.py]
    end

    subgraph Services["app/services"]
        ingest_requests[ingest_requests.py]
        pipeline[pipeline.py]
        ticker_data[ticker_data.py]
        chat_service[chat/chat_service.py]
        price_ingest[price_ingest.py]
        movements[movements.py]
        peers[peers.py]
        news[news/search.py + tiers]
        explain[explain.py]
        tools[chat/tools/*]
    end

    subgraph Repos["app/repositories"]
        repos[(one file per table)]
    end

    subgraph Providers["app/providers"]
        yf[YFinanceMarketDataProvider]
        exa[ExaNewsProvider]
        oai[OpenAILLMClient]
    end

    DB[(SQLite)]
    Yahoo([yfinance])
    ExaAPI([Exa])
    OpenAI([OpenAI])

    tickers --> ingest_requests
    tickers --> pipeline
    tickers --> ticker_data
    chat --> chat_service
    chat_service --> tools
    tools --> ticker_data
    pipeline --> price_ingest
    pipeline --> peers
    pipeline --> movements
    pipeline --> news
    pipeline --> explain
    Services --> repos
    price_ingest --> yf
    peers --> yf
    peers --> oai
    news --> exa
    explain --> oai
    chat_service --> oai
    repos --> DB
    yf --> Yahoo
    exa --> ExaAPI
    oai --> OpenAI
```

`app/dependencies.py` picks the concrete provider for each Protocol. Tests replace those three functions with fakes.

## 2. Ingest flow

`POST /tickers/{ticker}/ingest`, then the background task. Every database write happens on the pipeline thread. Only the Exa and OpenAI calls fan out.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as tickers.py
    participant J as ingest_requests.py
    participant P as pipeline.run_ingest
    participant Y as yfinance
    participant O as OpenAI
    participant E as Exa
    participant DB as SQLite

    C->>R: POST /tickers/AAPL/ingest {lookback_days?, threshold_pct?, refresh?}
    R->>J: resolve() then open_job() under a lock
    alt job already pending or running
        J-->>R: existing job
        R-->>C: 200 job
    else
        J->>DB: insert ingest_jobs (pending)
        R-->>C: 202 job
        R->>P: BackgroundTasks.add_task(run_ingest)
    end

    Note over P: stage = prices
    P->>Y: history(AAPL, start-100d, end), profile, history(SPY), history(sector ETF)
    P->>O: suggest competitors (skipped if cached on company row)
    P->>Y: history for each competitor ticker
    P->>DB: upsert companies and prices, commit

    Note over P: stage = movements
    P->>P: detect_movements: pct >= threshold, z-score, volume ratio, driver_hint
    P->>DB: upsert movements, delete days no longer qualifying, commit
    P->>P: select_candidates: N largest + last 7 days

    Note over P: stage = news
    P->>P: plan_searches: one per (tier, scope, window)
    P->>DB: read news_search_cache
    par up to 4 threads, uncached or unsettled searches only
        P->>E: search(query, window)
    end
    P->>DB: upsert articles, save cache rows, link movement_articles, commit

    Note over P: stage = explanations
    P->>P: build one prompt per move that is new, refreshed or gained articles
    par up to 6 threads
        P->>O: structured(ExplanationOutput)
    end
    P->>DB: upsert explanations, set relevance on links, commit

    Note over P: stage = complete
    P->>DB: job status = done, detail = counts, cost, errors
    C->>R: GET /tickers/AAPL/status
    R-->>C: job row
```

On any `AppError` the job is marked failed with the error's message. On any other exception the job says "Unexpected X. See the server log." Finished stages stay committed, so re-posting resumes at no cost.

## 3. Read flow

`GET /tickers/{ticker}` and its sub-resources. No outside calls.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as tickers.py
    participant T as ticker_data.py
    participant Q as movement_queries.py
    participant DB as SQLite

    C->>R: GET /tickers/AAPL?direction=down&min_confidence=0.7&sort=magnitude
    R->>R: parse query string into TickerDataQuery (MovementFilters + include_prices), 422 on unknown key
    R->>T: get_ticker_data(session, "AAPL", filters, include_prices)
    T->>DB: require_company (404 if missing)
    T->>Q: query_movements(filters)
    Q->>DB: one SELECT with the filters as WHERE clauses, explanation and articles eager-loaded, plus a COUNT
    T->>T: to_movement_response per row: apply article scope (cited|all|none), tier, min_relevance, snippets
    T->>DB: analysed_period from finished jobs, prices in that window
    T-->>R: TickerDataResponse
    R-->>C: 200 JSON
```

`/movements` and `/prices` are the same path without the other half. `/movements/{day}` uses fixed filters (all articles, with snippets).

## 4. Chat flow

`POST /chat`. The tools call the same `ticker_data.py` functions as the REST routes.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as chat.py
    participant S as chat_service.chat
    participant O as OpenAI
    participant T as chat tools
    participant DB as SQLite

    C->>R: POST /chat {message, ticker?, conversation_id?}
    R->>S: chat(session, llm, settings, request)
    S->>DB: list ingested tickers for the system prompt
    S->>DB: replayable_history: earlier questions and final answers only
    loop up to 6 rounds
        S->>O: chat(context + new messages, tool specs)
        alt model returns an answer
            O-->>S: content
        else model returns tool calls
            O-->>S: tool_calls
            S->>T: run_tool: validate args with the Pydantic model, run
            T->>DB: same queries as REST
            T-->>S: result dict, or {"error": ...}
            S->>S: collect every {title, url} in the result as a citable article
        end
    end
    opt still calling tools after 6 rounds
        S->>O: chat(..., no tools, "answer with what you have")
    end
    S->>S: citations_in: keep only URLs that appear in the answer and came from a tool
    S->>DB: store every message of this turn, including tool calls
    S-->>R: ChatResponse {conversation_id, answer, citations, tool_calls}
    R-->>C: 200 JSON
```

## 5. Ingest job lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: POST /ingest creates the row
    pending --> running: run_ingest sets the first stage
    running --> running: prices, movements, news, explanations (each commits)
    running --> done: finish_job, stage = complete
    running --> failed: AppError or unexpected exception
    pending --> failed: server restarted (fail_interrupted_jobs at startup)
    running --> failed: server restarted (fail_interrupted_jobs at startup)
    done --> [*]
    failed --> [*]
```

A pending or running job blocks a second ingest of the same ticker (the POST returns it with 200). Done and failed jobs do not.

## 6. Models

One SQLAlchemy class per file in `app/models/`. Types shown as stored in SQLite. Enum columns are plain strings.

```mermaid
erDiagram
    companies {
        string ticker PK
        string name
        string sector
        string industry
        string sector_etf
        json peers "list of {name, ticker}"
        datetime updated_at
    }
    prices {
        string ticker PK "also SPY, sector ETFs and peers"
        date date PK
        float open
        float high
        float low
        float close
        int volume
    }
    movements {
        int id PK
        string ticker "unique with date"
        date date
        float close
        float prev_close
        float pct_change
        float zscore
        float volume_ratio
        float market_pct_change
        float sector_pct_change
        float excess_vs_market
        float excess_vs_sector
        string driver_hint "market | sector | idiosyncratic"
        date window_start
        date window_end
    }
    articles {
        int id PK
        string url UK
        string title
        string source
        datetime published_at
        string snippet
    }
    movement_articles {
        int movement_id PK, FK
        int article_id PK, FK
        string tier "company | industry | macro"
        float relevance "0..1, set by the explanation"
    }
    explanations {
        int movement_id PK, FK
        string summary
        string category "company | industry | macro | unexplained"
        float confidence
        string model
        datetime created_at
    }
    news_search_cache {
        string cache_key PK "tier:scope:window_start:window_end"
        json article_ids
        float cost_dollars
        datetime fetched_at
    }
    ingest_jobs {
        int id PK
        string ticker
        string status "pending | running | done | failed"
        string stage
        json detail "params, counts, cost, errors"
        string error
        datetime started_at
        datetime finished_at
    }
    chat_messages {
        int id PK
        string conversation_id
        string role
        json content "full OpenAI message dict"
        datetime created_at
    }

    companies ||--o{ movements : "ticker"
    companies ||--o{ prices : "ticker"
    companies ||--o{ ingest_jobs : "ticker"
    movements ||--o| explanations : "movement_id"
    movements ||--o{ movement_articles : "movement_id"
    articles ||--o{ movement_articles : "article_id"
    news_search_cache }o..o{ articles : "article_ids (JSON, no FK)"
```

The `ticker` links to `companies` are by value, not declared foreign keys, because `prices` also holds benchmark and peer rows that have no company row.

## 7. Schemas

Pydantic models in `app/schemas/`. These are the serialisers: FastAPI validates input against the request models and output against the response models, and the LLM's structured output is parsed into the `llm` models.

### API request and response

```mermaid
classDiagram
    class MovementFilters {
        date start
        date end
        Direction direction
        float min_abs_change
        ExplanationCategory category
        DriverHint driver_hint
        float min_confidence
        bool explained_only
        ArticleScope articles = cited
        NewsTier tier
        float min_relevance
        bool include_snippets = false
        MovementSort sort = date_desc
        int limit
        int offset
    }
    class TickerDataQuery {
        bool include_prices = true
    }
    class PriceQuery {
        date start
        date end
    }
    class IngestRequest {
        date start
        date end
        int lookback_days
        float threshold_pct
        int max_movements
        bool refresh = false
    }
    MovementFilters <|-- TickerDataQuery

    class TickerDataResponse {
        TickerSummaryResponse summary
        IngestJobResponse latest_ingest
        MovementFilters filters
        int total_movements
        MovementResponse[] movements
        PriceResponse[] prices
    }
    class MovementListResponse {
        string ticker
        MovementFilters filters
        int total_movements
        MovementResponse[] movements
    }
    class PriceListResponse {
        string ticker
        date start
        date end
        PriceResponse[] prices
    }
    class TickerSummaryResponse {
        CompanyResponse company
        date first_price_date
        date last_price_date
        int movement_count
        int explained_count
    }
    class CompanyResponse {
        string ticker
        string name
        string sector
        string industry
        string sector_etf
        PeerResponse[] peers
    }
    class PeerResponse {
        string name
        string ticker
    }
    class MovementResponse {
        string ticker
        date date
        float pct_change
        float close
        float prev_close
        float zscore
        float volume_ratio
        float market_pct_change
        float sector_pct_change
        float excess_vs_market
        float excess_vs_sector
        DriverHint driver_hint
        date news_window_start
        date news_window_end
        PeerMoveResponse[] peer_moves
        ExplanationResponse explanation
        ArticleResponse[] articles
    }
    class PeerMoveResponse {
        string name
        string ticker
        float pct_change
    }
    class ExplanationResponse {
        string summary
        ExplanationCategory category
        float confidence
        string model
        datetime created_at
    }
    class ArticleResponse {
        int id
        string url
        string title
        string source
        datetime published_at
        string snippet
        NewsTier tier
        float relevance
        bool cited
    }
    class PriceResponse {
        date date
        float open
        float high
        float low
        float close
        int volume
    }
    class IngestJobResponse {
        int id
        string ticker
        JobStatus status
        string stage
        dict detail
        string error
        datetime started_at
        datetime finished_at
    }
    class ErrorResponse {
        ErrorBody error
    }
    class ErrorBody {
        string code
        string message
    }

    TickerDataResponse *-- TickerSummaryResponse
    TickerDataResponse *-- IngestJobResponse
    TickerDataResponse *-- MovementFilters
    TickerDataResponse *-- "0..*" MovementResponse
    TickerDataResponse *-- "0..*" PriceResponse
    MovementListResponse *-- "0..*" MovementResponse
    PriceListResponse *-- "0..*" PriceResponse
    TickerSummaryResponse *-- CompanyResponse
    CompanyResponse *-- "0..4" PeerResponse
    MovementResponse *-- "0..*" PeerMoveResponse
    MovementResponse *-- "0..1" ExplanationResponse
    MovementResponse *-- "0..*" ArticleResponse
    ErrorResponse *-- ErrorBody
```

### Chat

```mermaid
classDiagram
    class ChatRequest {
        string message
        string ticker
        string conversation_id
    }
    class ChatResponse {
        string conversation_id
        string answer
        Citation[] citations
        ToolCallTrace[] tool_calls
    }
    class Citation {
        string title
        string url
        string source
    }
    class ToolCallTrace {
        string name
        dict arguments
    }
    class ChatMessageResponse {
        string role
        string content
        datetime created_at
    }
    ChatResponse *-- "0..*" Citation
    ChatResponse *-- "0..*" ToolCallTrace

    class MovementFilters
    class ListMovementsArgs {
        string ticker
        int limit
    }
    class GetMovementArgs {
        string ticker
        date date
    }
    class SearchArticlesArgs {
        string query
        string ticker
        date start
        date end
        NewsTier tier
        int limit
    }
    class PriceSummaryArgs {
        string ticker
        date start
        date end
    }
    class EmptyArgs
    MovementFilters <|-- ListMovementsArgs
    note for ListMovementsArgs "Tool argument models. Their JSON schema is generated and sent to OpenAI as the tool spec."
```

### LLM structured output

```mermaid
classDiagram
    class ExplanationOutput {
        string summary
        ExplanationCategory category
        float confidence
        ArticleRelevance[] article_relevance
    }
    class ArticleRelevance {
        int article_id
        float relevance
    }
    class PeersOutput {
        PeerSuggestion[] peers
    }
    class PeerSuggestion {
        string name
        string ticker
    }
    ExplanationOutput *-- "1..*" ArticleRelevance
    PeersOutput *-- "0..*" PeerSuggestion
    note for ExplanationOutput "Passed as response_format to chat.completions.parse. Unknown article ids are dropped and scores clamped before storage."
```

## 8. Protocols and strategy registries

The three seams where a fake or a new implementation drops in.

```mermaid
classDiagram
    class MarketDataProvider {
        <<Protocol>>
        fetch_history(ticker, start, end) DataFrame
        fetch_profile(ticker) Profile
    }
    class YFinanceMarketDataProvider
    class FakeMarketDataProvider
    MarketDataProvider <|.. YFinanceMarketDataProvider
    MarketDataProvider <|.. FakeMarketDataProvider

    class NewsProvider {
        <<Protocol>>
        search(query, start, end, limit) NewsSearchResult
    }
    class ExaNewsProvider
    class FakeNewsProvider
    NewsProvider <|.. ExaNewsProvider
    NewsProvider <|.. FakeNewsProvider

    class LLMClient {
        <<Protocol>>
        string model
        structured(system, user, response_model) T
        chat(messages, tools) ChatTurn
    }
    class OpenAILLMClient
    class FakeLLMClient
    LLMClient <|.. OpenAILLMClient
    LLMClient <|.. FakeLLMClient

    class NewsTierStrategy {
        <<Protocol>>
        NewsTier tier
        int max_results
        build_query(movement, company) str
        cache_scope(movement, company) str
    }
    class CompanyTier
    class IndustryTier
    class MacroTier
    NewsTierStrategy <|.. CompanyTier
    NewsTierStrategy <|.. IndustryTier
    NewsTierStrategy <|.. MacroTier
    note for NewsTierStrategy "NEWS_TIERS registry in news/registry.py. TIER_PRIORITY orders them per driver hint."

    class ChatTool {
        <<Protocol>>
        string name
        string description
        type args_model
        run(session, args) dict
    }
    class ListTickersTool
    class ListMovementsTool
    class GetMovementTool
    class SearchArticlesTool
    class PriceSummaryTool
    ChatTool <|.. ListTickersTool
    ChatTool <|.. ListMovementsTool
    ChatTool <|.. GetMovementTool
    ChatTool <|.. SearchArticlesTool
    ChatTool <|.. PriceSummaryTool
    note for ChatTool "CHAT_TOOLS registry in chat/tools/registry.py."
```

## 9. Errors

```mermaid
classDiagram
    class Exception
    class AppError {
        int status_code = 500
        string code = internal_error
        string message
    }
    class InvalidTicker {
        422
    }
    class TickerNotFound {
        404
    }
    class TickerNotIngested {
        404
    }
    class MovementNotFound {
        404
    }
    class ConversationNotFound {
        404
    }
    class ProviderError {
        502
    }
    class ProviderNotConfigured {
        503
    }
    Exception <|-- AppError
    AppError <|-- InvalidTicker
    AppError <|-- TickerNotFound
    AppError <|-- TickerNotIngested
    AppError <|-- MovementNotFound
    AppError <|-- ConversationNotFound
    AppError <|-- ProviderError
    AppError <|-- ProviderNotConfigured
    note for AppError "One handler in main.py maps any AppError to {error: {code, message}}. In the pipeline an AppError message goes on the job row; anything else is logged only."
```

## 10. Driver hint decision

The price-only heuristic in `movements.driver_hint`. A benchmark explains a move when it went the same direction, moved at least 1% itself, and covers at least 40% of the stock's move.

```mermaid
flowchart TD
    A[Move of pct on day D] --> B{SPY explains?}
    B -- yes --> M[market]
    B -- no --> C{Sector ETF explains?}
    C -- yes --> S[sector]
    C -- no --> D{Peer median explains?<br/>needs 2+ peers with prices}
    D -- yes --> S
    D -- no --> I[idiosyncratic]
    M --> O[Orders the news tiers: macro, industry, company]
    S --> P[Orders the news tiers: industry, company, macro]
    I --> Q[Orders the news tiers: company, industry, macro]
```

Every tier still runs. The hint sets the link order (an article found by two tiers keeps the first one's label) and goes into the explanation prompt as evidence.
