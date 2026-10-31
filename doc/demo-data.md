# Demo Data

## What it creates

One business, **Kopi Senja**, with three stores set up differently. Kemang is the parent store (oldest); the others are branches that follow its catalog.

| | Kemang (parent) | Senopati | BSD |
|-|-----------------|----------|-----|
| Kitchen | on | on | off |
| Self-order QR | on, open | on, closed | off |
| Dine-in / tables / customer name | on / 12 tables / on | on / off / off | off |
| Service charge / PB1 / included tax | 5% / 10% / 11% | 0 / 10% / 11% | 0 / 0 / 0 |
| Online platforms | GoFood, GrabFood, ShopeeFood | GoFood, GrabFood | none |
| Products not sold / own prices | none / none | 3 / 5 | 5 / 3 |
| Ingredients and recipes | 22 | 17 (subset) | none |
| Packages / discounts | 2 / 7 | 1 / 2 | 0 / 1 |
| Cash difference limit / default float | Rp 20.000 / 500.000 | Rp 10.000 / 300.000 | Rp 20.000 / 200.000 |
| Shift today | open | open | none |

Shared by all: 5 categories, 28 products with option and add-on groups, manual platform prices for three products, HPP from recipes.

Each store has 14 days of history: orders (direct and online, all payment methods, dine-in and take-away, automatic and code discounts, packages, cancelled ones), kitchen tickets in every state, pending QR self-orders (Kemang), voids and refunds, daily shifts (reviewed, awaiting review, large cash difference with a note, today's open shift), drawer cash in/out with matching expenses, operating expenses with recurring drafts, ingredient stock (initial, restocks, sales, returns, a stock count, low-stock items), and platform payouts (settled with and without a difference, outstanding, overdue).

## Accounts

Password `demo1234` for all.

| Email | Role |
|-------|------|
| `owner@demo.com` | Owner of all three stores |
| `manager@demo.com` | Manager of Kemang and Senopati |
| `operator@demo.com` | Operator of Kemang |
| `kasir.senopati@demo.com` | Operator of Senopati |
| `manager.bsd@demo.com`, `kasir.bsd@demo.com` | Manager / operator of BSD |

## Login screen

With `DEMO_MODE=true`, the login page lists the demo accounts (never super admins) from `GET /auth/demo-accounts`; picking one fills the email and the demo password. With it off the endpoint returns an empty list and the login page shows no shortcuts.

## Reset

The reset is a development/demo tool. It creates accounts with a known password, so the HTTP endpoints only work when `DEMO_MODE=true` is set on the server (default `false`; otherwise 403 and the admin page hides the card). The seed never creates a super admin: use an existing one, or run `uv run python seed.py --admin` (password from `DEMO_ADMIN_PASSWORD`, or a random one printed once).

- **Super admin → Demo data → Reset & seed** (needs `DEMO_MODE=true`) (`POST /admin/seed/reset`) removes the demo data and creates it again. **Remove demo data** (`DELETE /admin/seed`) only removes it.
- CLI: `uv run python seed.py` (reset and seed), `uv run python seed.py --clear` (remove only).
- Removed: the demo stores (by slug), every store whose members are all demo accounts, their orders, and the demo users. Super admins and every other store or user are kept.
- The generator is `app/services/seed_service.py` (menu in `seed_data.py`). Data is written in bulk with the same fee, markup, discount and tax helpers as order creation, and dates are relative to the moment it runs.
