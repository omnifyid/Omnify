# Kasir — POS SaaS Backend

Multi-tenant Point of Sale REST API built with FastAPI and PostgreSQL. Each store has its own role-based team, catalog, and order history.

## Tech Stack

| Concern | Choice |
|---|---|
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async (`asyncpg`) |
| Migrations | Alembic |
| Validation | Pydantic v2 + pydantic-settings |
| Auth | python-jose (JWT HS256) + passlib[bcrypt] |
| Package manager | uv |
| Testing | pytest + httpx + pytest-asyncio |
| Database | PostgreSQL |

## Project Structure

```
kasir/
├── app/
│   ├── main.py              # FastAPI app, CORS, rate limiter, static media
│   ├── config.py            # Env-driven settings via pydantic-settings
│   ├── database.py          # Async engine, sessionmaker, get_db dependency
│   ├── models/              # SQLAlchemy 2.0 ORM models
│   ├── schemas/             # Pydantic v2 request/response schemas
│   ├── api/v1/              # Route handlers (thin — delegate to services)
│   ├── core/
│   │   ├── security.py      # JWT create/decode, bcrypt, refresh token generation
│   │   ├── dependencies.py  # Auth + role-guard dependency chain
│   │   └── exceptions.py    # Custom HTTP exception helpers
│   └── services/            # Business logic layer
├── alembic/
│   └── versions/            # Pure-SQL migration files
└── tests/
```

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- PostgreSQL database

### Install

```bash
uv sync
uv sync --extra dev   # include test/lint tools
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```ini
DATABASE_URL=postgresql+asyncpg://user:password@host:port/kasir
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
MEDIA_DIR=media
```

### Migrate

```bash
uv run alembic upgrade head
```

### Run

```bash
uv run uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`.

## Auth

Two-token system:

- **Access token** — JWT (HS256), 15-minute TTL. Payload: `sub` (user UUID), `jti`, `type: "access"`.
- **Refresh token** — 64-byte CSPRNG hex string. Stored as `SHA256(token)` in the database, never plaintext. 30-day TTL.

Roles are **not** embedded in the JWT. Every store-scoped request queries `store_memberships` live, so role changes take effect immediately without requiring re-login.

## Roles

Each user can have a different role per store:

| Role | Permissions |
|---|---|
| `OWNER` | Full control: catalog, staff, orders, reports, store settings |
| `MANAGER` | Catalog write, staff read, orders read/status, reports |
| `OPERATOR` | Create orders, read catalog, view own orders |

## API Reference

Base path: `/api/v1`

### Auth — `/auth`

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/auth/register` | Public | Create account |
| POST | `/auth/login` | Public | Get access + refresh tokens |
| POST | `/auth/refresh` | — | Exchange refresh token for new access token |
| POST | `/auth/logout` | — | Revoke one refresh token |
| POST | `/auth/logout-all` | Bearer | Revoke all refresh tokens for current user |

**Rate limits:** register 10/min, login 20/min.

### Users — `/users`

| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/users/me` | Bearer | Get own profile |
| PATCH | `/users/me` | Bearer | Update name or password |

### Stores — `/stores`

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/stores` | Bearer | Create store (caller becomes OWNER) |
| GET | `/stores` | Bearer | List stores the caller belongs to |
| GET | `/stores/{store_id}` | Any member | Get store details |
| PATCH | `/stores/{store_id}` | OWNER/MANAGER | Update name, slug, description |
| DELETE | `/stores/{store_id}` | OWNER | Deactivate store |
| GET | `/stores/{store_id}/members` | OWNER/MANAGER | List store members |
| POST | `/stores/{store_id}/members` | OWNER | Add member by email |
| PATCH | `/stores/{store_id}/members/{uid}` | OWNER | Change member role |
| DELETE | `/stores/{store_id}/members/{uid}` | OWNER | Remove member |

### Catalog

#### Categories — `/stores/{store_id}/categories`

| Method | Path | Access |
|---|---|---|
| GET | `/categories` | Any member |
| POST | `/categories` | OWNER/MANAGER |
| PATCH | `/categories/{cat_id}` | OWNER/MANAGER |
| DELETE | `/categories/{cat_id}` | OWNER/MANAGER |

#### Items — `/stores/{store_id}/items`

| Method | Path | Access |
|---|---|---|
| GET | `/items` | Any member |
| POST | `/items` | OWNER/MANAGER |
| GET | `/items/{item_id}` | Any member |
| PATCH | `/items/{item_id}` | OWNER/MANAGER |
| DELETE | `/items/{item_id}` | OWNER/MANAGER |
| PATCH | `/items/{item_id}/stock` | OWNER/MANAGER |
| PUT | `/items/{item_id}/option-groups` | OWNER/MANAGER |
| PUT | `/items/{item_id}/addon-groups` | OWNER/MANAGER |
| POST | `/items/{item_id}/image` | OWNER/MANAGER |

**Stock tracking** — Items have an optional `stock` field:
- `null` — no tracking, always available (default)
- `0` — out of stock, cannot be ordered
- `>0` — tracked; decremented atomically on each successful order

`GET /items?available_only=true` excludes both `is_available=false` and `stock=0` items.

`PATCH /items/{item_id}/stock` body: `{ "stock": 50 }` or `{ "stock": null }` to disable tracking.

**Options** — mutually exclusive choices with no price change (e.g., Sugar Level: Normal / Less Sugar). Configured as `OptionGroup` → `OptionChoice[]`.

**Addons** — multi-select with price (e.g., Extra Espresso Shot +Rp5.000). Configured as `AddonGroup` → `AddonChoice[]`, each with `extra_price`. Group supports `min_select` / `max_select`.

#### Packages — `/stores/{store_id}/packages`

Bundles of items at a single flat price (not derived from item prices).

| Method | Path | Access |
|---|---|---|
| GET | `/packages` | Any member |
| POST | `/packages` | OWNER/MANAGER |
| GET | `/packages/{package_id}` | Any member |
| PATCH | `/packages/{package_id}` | OWNER/MANAGER |
| DELETE | `/packages/{package_id}` | OWNER/MANAGER |

### Discounts — `/stores/{store_id}/discounts`

| Method | Path | Access |
|---|---|---|
| GET | `/discounts` | OWNER/MANAGER |
| POST | `/discounts` | OWNER/MANAGER |
| PATCH | `/discounts/{discount_id}` | OWNER/MANAGER |
| DELETE | `/discounts/{discount_id}` | OWNER/MANAGER |
| POST | `/discounts/validate` | Any member |

Two discount types:
- `PERCENTAGE` — value stored as basis points (1000 = 10.00%)
- `FIXED` — fixed rupiah amount deducted

Supports `min_order_amount`, `max_uses`, `expires_at`.

### Orders — `/stores/{store_id}/orders`

| Method | Path | Access |
|---|---|---|
| POST | `/orders` | Any member |
| GET | `/orders` | OWNER/MANAGER |
| GET | `/orders/my` | Any member (own orders only) |
| GET | `/orders/{order_id}` | Any member |
| PATCH | `/orders/{order_id}/status` | OWNER/MANAGER |

Order status flow: `PENDING` → `CONFIRMED` → `COMPLETED` / `CANCELLED`

Payment methods: `CASH`, `CARD`, `QRIS`, `TRANSFER`

Order number format: `ORD-{YYYYMMDD}-{5-digit daily counter}`

### Reports — `/stores/{store_id}/reports`

All report endpoints accept optional `from_date` / `to_date` query params (ISO date).

| Method | Path | Description |
|---|---|---|
| GET | `/reports/sales` | Revenue, order count, avg order value |
| GET | `/reports/top-items` | Best-selling items by quantity/revenue |
| GET | `/reports/by-staff` | Orders and revenue grouped by operator |
| GET | `/reports/by-payment` | Revenue breakdown by payment method |

Access: OWNER/MANAGER only.

## Order Creation (Atomic Flow)

`POST /stores/{store_id}/orders` runs entirely inside a database transaction with `SELECT FOR UPDATE` on any applied discount. Any failure rolls back completely.

1. **Validate** — each cart item is verified: belongs to this store, is available; stock check (`stock=0` → 400 "out of stock", `stock<qty` → 400 "only N unit(s) in stock"); option/addon choices belong to the correct groups; discount is active, unexpired, within `max_uses`.
2. **Calculate** — prices fetched from DB (client-supplied prices ignored):
   ```
   line_total    = (base_price + sum(addon.extra_price)) × quantity
   subtotal      = sum(line_totals)
   discount      = subtotal × value ÷ 10000  (PERCENTAGE)
                 = min(value, subtotal)        (FIXED)
   total_amount  = subtotal − discount_amount
   ```
3. **Snapshot** — `OrderItem` rows freeze `item_name_snapshot`, `unit_price_snapshot`, `options_snapshot`, `addons_snapshot` at creation time so receipts remain accurate after future price changes.
4. **Write** — inserts `Order`, all `OrderItem` rows, decrements `item.stock` for tracked items, increments `discount.used_count` if a code was applied.

The `SELECT FOR UPDATE` on the discount prevents two concurrent requests both passing a `max_uses=1` check.

## Data Design Notes

- All monetary values are **integers** (rupiah). No floats anywhere in financial fields.
- Percentage discounts stored as **basis points** (10% = 1000, not 0.1).
- Refresh tokens stored as `SHA256(raw_token)` — the raw token is returned to the client once and never stored.
- Role resolution is **per-request** via a DB query, not embedded in the JWT.

## Development

### Lint

```bash
uv run ruff check .
uv run ruff format .
```

### Test

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

### New migration

```bash
uv run alembic revision --autogenerate -m "describe_change"
uv run alembic upgrade head
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/kasir` | Async PostgreSQL URL |
| `SECRET_KEY` | `change-me` | JWT signing key — **change in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token TTL |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated CORS origins |
| `MEDIA_DIR` | `media` | Local directory for uploaded item images |
