# Conventions

How code in this repo is written. Agreed up front (D14) so every ticket lands the same way. The test for each rule: it either removes duplication we'd otherwise hit, or it sits on a seam the brief itself says will vary.

## Layout & layering

```
app/
  api/            routers — thin: parse → call service → return schema
  services/       orchestration + pure domain logic
  repositories/   ALL database access; functions take a Session, caller owns the transaction
  providers/      adapters for external services (Protocol + one adapter class per file)
  models/         SQLAlchemy tables          domain/   dataclasses passed between layers
  schemas/        Pydantic API models        enums/    closed vocabularies
  constants/      fixed values               errors/   typed exceptions
  prompts/        LLM prompt templates       dependencies.py   the wiring
```

Dependencies point one way: `api → services → repositories / providers`. Pure logic (e.g. `services/movements.py`) does no I/O. ORM objects don't cross the API boundary — schemas do.

## Rules

1. **One class per file** (D10), file named after the class in snake_case; packages re-export from `__init__.py` so call sites stay `from app.models import Price`. Functions may share a module.
2. **No magic values.** Fixed values → `app/constants/<domain>.py`. Anything a deployer might tune → `app/config.py` (`Settings`, env-driven). Nothing inline.
3. **Closed vocabularies are `StrEnum`s** in `app/enums/`, never bare strings. The same enum types the DB column (`enum_column()` in `models/base.py` — stored as its string value), the API filter, the LLM structured-output schema and the chat tool schema.
4. **External services sit behind a `Protocol`** (`MarketDataProvider`, `NewsProvider`, `LLMClient`). Concrete adapters are chosen in exactly one place, `app/dependencies.py`, and injected via `Depends`. Tests pass fakes (`tests/fakes/`) implementing the same Protocol.
5. **Variation points are registries of small classes**, not `if/elif` chains: news tiers, chat tools. Adding one = one new file + one registry entry; the loop that consumes them doesn't change.
6. **One definition per concept.** A filter set is one Pydantic model reused as REST query params, chat-tool arguments and repository input. Tool JSON schemas are generated from Pydantic models, never hand-written.
7. **Errors:** services raise `AppError` subclasses carrying `status_code` + `code`; one handler in `main.py` renders them. No `HTTPException` below the router layer.
8. **Prompts are files** in `app/prompts/`, not inline strings.
9. **Logging, not print.** `logger = logging.getLogger(__name__)`. Every paid external call logs latency and cost.
10. **Type hints everywhere; `ruff` clean** (`ruff format` + `ruff check`, config in `pyproject.toml`) before every commit.
11. **Tests are offline** — no network, no keys, in-memory SQLite (`session` fixture). Seed shapes live in `tests/factories.py`. Live calls are a manual smoke run per ticket, recorded in PLAN.md's "Shipped" line.
12. **Comments say why, not what.** Tradeoffs and deviations go in DECISIONS.md with a `D` number and get referenced from code as `(D12)`.

## Deliberately not used

DI container libraries (`Depends` + one wiring module is enough) · abstract base classes where a Protocol does the job · a repository class per table · Alembic (D2) · async everywhere (sync SQLAlchemy + FastAPI's threadpool is simpler and fast enough) · mypy (hints are for readers; a second checker isn't worth the minutes here).

**Seams, not speculation:** abstraction goes only where the brief implies variation — news source, news tier, LLM, chat tools, filters. Everywhere else, the simplest code that works.
