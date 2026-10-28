# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Also mirrored in AGENTS.md for compatibility with other AI tools.

## Commands

```bash
uv sync                                              # install dependencies
uv sync --extra dev                                  # include test/lint tools
uv run uvicorn app.main:app --reload                 # start dev server
uv run alembic upgrade head                          # run migrations
uv run alembic revision --autogenerate -m "message"  # create migration
uv run pytest                                        # run all tests
uv run pytest tests/path/test_file.py::test_name     # run single test
uv run pytest --cov=app --cov-report=term-missing    # with coverage
uv run ruff check .                                  # lint
uv run ruff format .                                 # format
uv run python seed.py                                # seed demo data
uv run python seed.py --reset                        # wipe and re-seed
```

Requires `.env` copied from `.env.example`. Key vars: `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`.

## Architecture

FastAPI + SQLAlchemy 2.0 async (asyncpg) + PostgreSQL + Pydantic v2 + Alembic. Python 3.12+.

Layered: **Routes (thin) → Services (business logic) → Models (ORM)**. DB queries belong in services only, never in routes.

```
app/
├── main.py              # app setup, CORS, rate limiter, static media mount
├── config.py            # pydantic-settings from .env
├── database.py          # AsyncSession engine, get_db dependency
├── core/
│   ├── security.py      # JWT HS256, bcrypt, refresh token generation
│   ├── dependencies.py  # auth dependency chain + role guards
│   └── exceptions.py    # typed HTTPException subclasses
├── models/              # SQLAlchemy 2.0 ORM (Mapped, mapped_column, UUID PKs, TimestampMixin)
├── schemas/             # Pydantic v2 request/response DTOs
├── api/v1/              # route handlers per domain; central router in api/router.py
└── services/            # one service module per domain
```

## Key Patterns

**Auth — two-token system:**
- Access token: JWT HS256, 15-min TTL. Payload has `sub` (user_id), `jti`, `type: "access"`.
- Refresh token: 64-byte random hex. Stored as `SHA256(raw)` in DB — never plaintext.
- **Roles are NOT in the JWT.** Every store-scoped request queries `store_memberships` live so role changes take effect immediately.

**RBAC dependency chain:**
```
oauth2_scheme → get_current_user → get_store_membership(store_id) → require_roles(...)
```
Pre-built guards in `core/dependencies.py`: `OwnerOnly`, `OwnerOrManager`, `AnyMember`. Declare in route signature via `Depends(...)`.

**Multi-tenancy:** Every resource (Item, Category, Discount, Order) is scoped to a `Store` via FK. Store ID is always in the URL path (`/stores/{store_id}/...`). Users access stores via `StoreMembership`.

**Order creation atomicity:** Uses `async with db.begin_nested()` (savepoint) + `SELECT FOR UPDATE` on discount rows to prevent concurrent over-redemption. OrderItems snapshot name, price, options, and addons at creation — receipts survive future catalog changes. Client-supplied prices are ignored; prices are always fetched from DB.

**Money and percentages:** All monetary values are integers (Rupiah, never floats). Percentage discounts stored as basis points (1000 = 10%).

**Options vs Addons:** OptionGroups are mutually exclusive (size, ice level), no extra price. AddonGroups are multi-select with `extra_price` per choice.

**Password hashing:** Uses `bcrypt` directly — passlib was removed due to bcrypt 4.x incompatibility.

**Rate limiting:** slowapi Limiter on auth endpoints (register: 10/min, login: 20/min).

## Demo Data

`seed.py` creates store "Kopi Senja" with 5 categories, 28 items, 52 option groups, 42 addon groups, and three users. Idempotent — skips existing records. `--reset` deletes and re-creates all demo data.

- `owner@demo.com` / `demo1234`
- `manager@demo.com` / `demo1234`
- `operator@demo.com` / `demo1234`
