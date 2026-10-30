# PRD: Self Order (QR Code)

## Overview

Customers scan a QR code at their table, browse the menu on their own device, and submit an order — no login required. The order lands in the kasir dashboard as `PENDING` and waits for a cashier to confirm payment.

---

## Order Status Flow

```
Customer submits → PENDING → cashier confirms payment → CONFIRMED → order served → COMPLETED
                                                      ↘ CANCELLED
```

- Self-orders always start as **PENDING** — the cashier must act before the order is processed
- POS cashier-created orders start as **CONFIRMED** (payment is collected at the point of sale)
- The `initial_status` parameter in `order_service.create_order` controls this distinction

---

## User Flow

1. Staff generates QR codes per table from **Self Order** (`/selforder`)
2. QR code is printed and placed on each table
3. Customer scans QR → opens `/order/{storeId}?table=5` in mobile browser
4. Customer browses menu, selects options/addons, builds cart
5. Customer submits order (no login required)
6. Customer sees success screen; order appears in kasir dashboard as `PENDING`
7. Cashier sees the order in the **Pesanan Menunggu** queue, collects payment, clicks **Konfirmasi**
8. Order moves to `CONFIRMED`; cashier prepares and serves; marks `COMPLETED`

---

## QR Code URL Format

```
https://yourdomain.com/order/{store_id}?table={tableNumber}
```

- `store_id` — UUID of the store
- `table` — table number as a plain integer (e.g. `5`)
- Frontend reads `table` from search params and sends it to the backend as `table_number`
- Backend prepends `"Meja "` and stores it in `orders.notes` (e.g. `"Meja 5"`)
- If the customer adds a note too, they are combined: `"Meja 5 — extra spicy"`

---

## Backend

### Public Endpoints (no auth)

All under prefix `/api/v1/public/` — no `Authorization` header required.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/public/stores/{store_id}/menu` | Returns store info, categories, and available items |
| `POST` | `/public/stores/{store_id}/orders/preview` | Cart totals for the customer: automatic discounts, service charge (when a table is set), PB1; promo codes ignored |
| `POST` | `/public/stores/{store_id}/orders` | Creates a PENDING order; payment method fixed to `CASH`; a table number makes it `DINE_IN` |

Both endpoints verify `store.is_active = True` — returns 404 if not.

#### `GET /public/stores/{store_id}/menu` → `PublicMenuResponse`

```json
{
  "store": { "id": "...", "name": "Kopi Senja", "description": null, "logo_url": null },
  "categories": [ { "id": "...", "name": "Minuman", "icon": "☕" } ],
  "items": [ { "id": "...", "name": "Kopi Susu", "base_price": 18000, "image_url": "/media/...", ... } ]
}
```

- Items filtered: `is_available = True` only; `stock = 0` items included but marked out of stock
- Items include full `option_groups` and `addon_groups` with choices
- Limit: 200 categories, 500 items

#### `POST /public/stores/{store_id}/orders` → `OrderRead` (201)

Request body (`SelfOrderCreate`):
```json
{
  "items": [
    {
      "item_id": "uuid",
      "quantity": 2,
      "selected_option_choice_ids": ["uuid"],
      "selected_addon_choice_ids": ["uuid", "uuid"]
    }
  ],
  "table_number": "5",
  "notes": "extra spicy"
}
```

- `payment_method` is always `CASH` — customer does not choose
- `operator_id` is `null` — no logged-in staff for self-orders
- `initial_status` passed as `OrderStatus.PENDING` — distinguishes from POS orders
- Notes combined server-side: `"Meja {table_number}"` + `" — {notes}"` if both present
- Prices always fetched from DB — client values are ignored

### Schema: `SelfOrderCreate`

```python
class SelfOrderCreate(BaseModel):
    items: list[CartItemIn]
    table_number: str | None = None
    notes: str | None = None
```

### `order_service.create_order` — `initial_status` parameter

```python
async def create_order(
    store_id, operator_id, payload, db,
    initial_status: OrderStatus = OrderStatus.CONFIRMED,
) -> Order:
```

- Default `CONFIRMED` — POS flow (payment collected at time of order)
- Public endpoint passes `OrderStatus.PENDING` — cashier must confirm after collecting payment

### Model Change: `operator_id` nullable

`orders.operator_id` was made nullable via migration `b2c3d4e5f6a7` — self-orders have no logged-in operator.

---

## Cashier Workflow (Frontend)

### Pesanan Menunggu queue — `/transactions`

When there are any `PENDING` orders, an amber panel appears at the top of the Transactions page:

```
┌─ Pesanan Menunggu Konfirmasi (2) ────────────────────────────────┐
│  ORD-20250523-00001  Meja 5  14:32 · Rp 45.000  [Konfirmasi] [Detail] │
│  ORD-20250523-00002  Meja 2  14:35 · Rp 28.000  [Konfirmasi] [Detail] │
└──────────────────────────────────────────────────────────────────┘
```

- Loaded in parallel with the main transaction list on every page load
- **Konfirmasi** button sets status to `CONFIRMED` inline (no page navigation required)
- **Detail** link opens `/transactions/{id}` for full order review

### Transaction detail — `/transactions/[id]`

Status-aware action panel:

| Order status | Actions shown |
|---|---|
| `PENDING` | **Konfirmasi Pesanan** (amber) + Selesaikan + Batalkan |
| `CONFIRMED` | Selesaikan + Batalkan |
| `COMPLETED` / `CANCELLED` | Read-only message, no buttons |

---

## Frontend — Customer Pages

### Self-Order Page — `/order/[storeId]`

**Route:** `kasir-fe/src/routes/order/[storeId]/+page.svelte`

Public route — no auth required. Excluded from auth redirect and AppShell in `+layout.svelte`.

#### UI Sections

**Header** (sticky) — store name + "Meja N" label; cart icon with count when non-empty

**Category tabs** (sticky, horizontal scroll) — "Semua" + one per category; filters the item grid

**Item grid** (2-col, 3-col on sm+)
- Thumbnail shows `image_url` → plain SVG placeholder (no emoji)
- `stock = 0` → "Habis" overlay, card disabled
- Items **without** modifiers: tap → add 1 to cart; inline +/− on card
- Items **with** `option_groups` or `addon_groups`: tap → opens customization sheet; qty badge in thumbnail corner when in cart

**Sticky cart bar** (bottom) — count · "Lihat Pesanan" · total; opens cart sheet

**Cart bottom sheet**
- Each line: thumbnail, name, modifier summary, unit price, qty +/−, line total
- Optional notes textarea
- Total + "Kirim Pesanan" button

**Customization bottom sheet** (items with modifiers)
- Hero image or gradient placeholder
- Item name, description, base price
- **Option groups** — radio buttons; `is_required` groups show "Wajib" badge; required groups without selection block the confirm button
- **Addon groups** — checkboxes; `+Rp X.XXX` per choice; only `is_available` choices shown
- Qty selector (min 1)
- Confirm button shows running total: `"Tambah ke Pesanan — Rp XX.XXX"`
- Pre-selects `is_default` choices on first open; restores cart selections on re-open

**Success screen** — checkmark, "Pesanan Diterima!", table + order number, "Pesan Lagi"

#### Cart State

```typescript
type CartEntry = {
  item: MenuItem;
  qty: number;
  selectedOptionChoiceIds: string[];
  selectedAddonChoiceIds: string[];
};

cart: Map<itemId, CartEntry>  // one slot per item ID
```

Unit price = `base_price + Σ(extra_price of selected addons)`. Cart total = `Σ(unitPrice × qty)`.

---

### QR Management Page — `/selforder`

**Route:** `kasir-fe/src/routes/selforder/+page.svelte`
**Access:** OWNER and MANAGER only

- **Table count** input + **label prefix** input (default "Meja"); settings saved in `localStorage` keyed by store ID
- **Generate** — builds QR data URLs client-side via `qrcode` npm package; colors: `dark=#5c3d2e`, `light=#fffdf9`
- **QR card**: QR image · label ("Meja N") · "Buka" (opens self-order URL in new tab) · "Print" (single card)
- **"Print Semua"** — prints all cards

Print CSS uses visibility technique:
```css
@media print {
  :global(*) { visibility: hidden; }
  .print-area { visibility: visible; position: fixed; inset: 0; }
  .print-area * { visibility: visible; }
  .has-print-target .qr-card:not(.print-target) { display: none !important; }
  .no-print { display: none !important; }
}
```

---

## Auth Bypass

`+layout.svelte` excludes `/order/*` from auth redirect and AppShell:

```typescript
let isOrder = $derived(currentPath.startsWith('/order'));
// onMount: if (!auth.isAuthenticated && !isLogin && !isOrder) goto('/login')
// template: {#if isLogin || isOrder} {@render children()} ...
```

---

## Files

| File | Role |
|------|------|
| `kasir-be/app/api/v1/public.py` | Public menu + order endpoints; passes `initial_status=PENDING` |
| `kasir-be/app/api/router.py` | Registers public router at `/public` |
| `kasir-be/app/services/order_service.py` | `create_order` accepts `initial_status` param (default `CONFIRMED`) |
| `kasir-be/app/schemas/order.py` | `SelfOrderCreate` schema |
| `kasir-be/app/models/order.py` | `operator_id` made nullable |
| `kasir-be/alembic/versions/b2c3d4e5f6a7_nullable_order_operator.py` | Migration: nullable operator_id |
| `kasir-fe/src/routes/order/[storeId]/+page.svelte` | Customer self-order page |
| `kasir-fe/src/routes/selforder/+page.svelte` | Owner/manager QR management page |
| `kasir-fe/src/routes/transactions/+page.svelte` | Pesanan Menunggu queue panel |
| `kasir-fe/src/routes/transactions/[id]/+page.svelte` | Status-aware confirm/complete/cancel actions |
| `kasir-fe/src/routes/+layout.svelte` | Auth bypass for `/order/*` |
| `kasir-fe/src/lib/components/Sidebar.svelte` | Self Order nav entry (OWNER/MANAGER) |

---

## Limitations & Future Work

- One cart configuration per item ID — cannot order the same item with two different option sets in one submission
- No promo code input on self-orders (always CASH); automatic discounts still apply and show in the cart
- No real-time push to customer after order status changes (customer sees static success screen)
- QR codes generated client-side per session — not stored in DB; regenerate if stale
- Table number is a free string; no server-side table list validation
- Payment method locked to CASH — QRIS/transfer self-pay not yet supported
