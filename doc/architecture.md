# Architecture

## Repository

Single git repo (monorepo) at the project root. One `.gitignore` at the root covers both apps.

```
omnify/
├── kasir-fe/   # frontend (SvelteKit SPA + Capacitor)
├── kasir-be/   # backend (FastAPI)
└── doc/        # project docs
```

Each app keeps its own tooling (`package.json` / `pyproject.toml`) and Dockerfile; there is no root workspace tool.

## Docker (server)

Root `docker-compose.yml` runs `db` (Postgres 16), `redis`, `be` (:8000) and `fe` (:3000). Config comes from a root `.env` (template: `.env.example`). `be` gets `DATABASE_URL` pointing at `db`.

```bash
cp .env.example .env   # fill in secrets
docker compose up -d --build
```

Local dev does not use compose: run the apps directly against a local Postgres via `kasir-be/.env`.

## Stack

**Frontend** (`kasir-fe/`)
- SvelteKit + Svelte 5 (runes: `$state`, `$derived`, `$effect`)
- TypeScript, Tailwind CSS
- Built as a **SPA** (`adapter-static`, `fallback: 'index.html'`) — deployed to web via Nginx and bundled into Android via Capacitor
- API client: `$lib/api/client` — `api.get/post/patch/delete`
- Types: `$lib/api/types.ts`
- Pagination helper: `paginatedItems()` in `$lib/api/pagination.ts`
- Print utilities: `$lib/utils/escpos.ts` (ESC/POS builder), `$lib/utils/bluetooth-printer.ts` (Web Bluetooth GATT)

**Deployment**
- Web: Docker + Nginx serves the static `build/` output on port 80 (exposed as 3000 externally)
- Android: Capacitor bundles the same static build into an APK
- Backend: Docker + `entrypoint.sh` runs `alembic upgrade head` then starts uvicorn

**Backend** (`kasir-be/`)
- FastAPI + SQLAlchemy 2.0 async (asyncpg) + PostgreSQL
- Pydantic v2 + Alembic migrations
- Python 3.12+, dependency management via `uv`

## Backend Layer Pattern

```
Routes (thin) → Services (business logic) → Models (ORM)
```
- DB queries belong in services only, never in routes
- Routes under `app/api/v1/`, services in `app/services/`, models in `app/models/`, schemas in `app/schemas/`

## Auth

- Access token: JWT HS256, 15-min TTL. Payload: `sub` (user_id), `jti`, `type: "access"`.
- Refresh token: 64-byte random hex, stored as `SHA256(raw)` in DB.
- Password reset token: 64-byte random hex sent by email through Resend, stored as `SHA256(raw)`, single-use, 30-min TTL.
- **Roles are NOT in the JWT** — queried live from `store_memberships` on every request.

## Multi-tenancy

Every resource (Item, Category, Discount, Order) is scoped to a `Store` via FK. Store ID always in URL path (`/stores/{store_id}/...`). Users access stores via `StoreMembership`.

## Money

- All monetary values: **integers (Rupiah, never floats)**
- Percentage discounts: **basis points** (1000 = 10.00%)

## Order Atomicity

- `async with db.begin_nested()` (savepoint) + `SELECT FOR UPDATE` on discount rows
- OrderItems snapshot name, price, options, addons at creation — receipts survive catalog changes
- Client-supplied prices are ignored; prices always fetched from DB

## Key Commands

```bash
uv run uvicorn app.main:app --reload   # start backend dev server
uv run alembic upgrade head            # run migrations
uv run alembic revision --autogenerate -m "message"  # create migration
uv run pytest                          # run tests
```
