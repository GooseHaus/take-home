# Conventions

How code in this repo is written (see D14 in [DECISIONS.md](DECISIONS.md)). Each rule either removes duplication or covers something the brief says can vary.

## Layout

```
app/
  api/            routers: parse the request, call a service, return a schema
  services/       orchestration and domain logic
  repositories/   all database access. Functions take a Session; the caller owns the transaction
  providers/      adapters for external services. One Protocol and one adapter class per file
  models/         SQLAlchemy tables
  domain/         dataclasses passed between layers
  schemas/        Pydantic models for the API and the LLM
  enums/          closed sets of values
  constants/      fixed values
  errors/         typed exceptions
  prompts/        LLM prompt templates
  dependencies.py provider wiring
```

Dependencies go one way: `api` to `services` to `repositories` and `providers`. Pure logic such as `services/movements.py` does no I/O. ORM objects stay inside the services; the API returns schemas.

## Rules

1. One class per file, named after the class in snake_case. Packages re-export from `__init__.py`. Functions can share a module.
2. No magic values. Fixed values go in `app/constants/<domain>.py`. Values a deployer might change go in `app/config.py`.
3. Closed sets of values are `StrEnum`s in `app/enums/`. The same enum types the database column (through `enum_column()` in `models/base.py`), the API filter, the LLM output schema and the chat tool schema.
4. External services sit behind a `Protocol` (`MarketDataProvider`, `NewsProvider`, `LLMClient`). Adapters are chosen in `app/dependencies.py` and injected with `Depends`. Tests use the fakes in `tests/fakes/`.
5. Things that vary are small classes in a registry, not `if/elif` chains. This applies to news tiers and chat tools. Adding one means a new file and a registry entry.
6. Define each concept once. A filter set is one Pydantic model used for REST query parameters, chat tool arguments and repository input. Tool JSON schemas are generated from Pydantic models.
7. Services raise `AppError` subclasses that carry a `status_code` and a `code`. One handler in `main.py` turns them into responses. No `HTTPException` below the routers.
8. Prompts are files in `app/prompts/`.
9. Use `logging`, not `print`. Every paid external call logs its latency and cost.
10. Type hints everywhere. `ruff format` and `ruff check` must pass before a commit.
11. Tests are offline: no network, no keys, in-memory SQLite through the `session` fixture. Test data builders are in `tests/factories.py` and `tests/seed.py`. Live calls are a manual check per ticket, recorded in PLAN.md.
12. Comments explain why, not what. Tradeoffs go in DECISIONS.md with a D number that the code can reference, for example `(D12)`.

## Not used, on purpose

- DI container libraries. `Depends` and one wiring module are enough.
- Abstract base classes where a Protocol works.
- A repository class per table.
- Alembic (D2).
- Async everywhere. Sync SQLAlchemy with FastAPI's threadpool is simpler and fast enough.
- mypy.

Abstractions go only where the brief implies variation: news source, news tier, LLM, chat tools and filters. Everywhere else, use the simplest code that works.
