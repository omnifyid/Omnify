# CLAUDE.md — kasir-be

FastAPI + SQLAlchemy async + PostgreSQL. Project knowledge lives in [../doc/](../doc/); start with [architecture](../doc/architecture.md) (layers, auth, multi-tenancy, money, order atomicity), [conventions](../doc/conventions.md), [db-schema](../doc/db-schema.md) and [demo-data](../doc/demo-data.md).

## Commands

```bash
uv sync --extra dev                                  # install dependencies incl. test/lint
uv run uvicorn app.main:app --reload                 # start dev server
uv run alembic upgrade head                          # run migrations
uv run alembic revision --autogenerate -m "message"  # create migration
uv run pytest                                        # run all tests
uv run pytest tests/path/test_file.py::test_name     # run single test
uv run ruff check . && uv run ruff format .          # lint and format
uv run python seed.py                                # reset and seed demo data
uv run python seed.py --clear                        # remove demo data
```

Requires `.env` copied from `.env.example`. Key vars: `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`.

## Notes

- Use `bcrypt` directly, not passlib (incompatible with bcrypt 4.x).
- Auth endpoints are rate limited with slowapi (register 10/min, login 20/min).
