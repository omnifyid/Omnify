# PRD: Orders

## Order Flow

1. Cashier builds cart (items + options + addons)
2. Optional: apply discount (promo code or auto-apply)
3. Select payment method
4. Confirm → order created atomically in DB
5. Receipt shown; order moves to COMPLETED

## Order Status

`PENDING` → `CONFIRMED` → `COMPLETED` | `CANCELLED`

Allowed transitions (enforced by `PATCH /orders/{id}/status`, row locked): `PENDING` → `CONFIRMED`/`COMPLETED`/`CANCELLED`; `CONFIRMED` → `COMPLETED`/`CANCELLED`; `COMPLETED` and `CANCELLED` are final. An order with refunds (`refunded_amount > 0`) or a recorded platform payout (`settlement_id`) cannot be cancelled.

## Payment Methods

`CASH`, `CARD`, `QRIS`, `TRANSFER`, `PLATFORM` (online platform orders only, see [prd-channels.md](prd-channels.md))

## Receipt / Snapshot Rules

OrderItems snapshot at creation time:
- `name` (item name at time of order)
- `unit_price` (price at time of order — NOT live catalog price)
- `quantity`
- `options_snapshot` (selected options)
- `addons_snapshot` (selected addons with extra prices)
- `item_discount_amount` (per-line discount applied)

Receipts must be immutable — changing item price later must not affect past orders.

## Pricing Rules

- Client-supplied prices are **ignored**; prices always fetched from DB at order creation
- `subtotal` = sum of all line items before discount
- `discount_amount` = total discount applied
- `total` = `subtotal - discount_amount`

## Atomicity

- Order creation uses `async with db.begin_nested()` (savepoint)
- `SELECT FOR UPDATE` on discount rows prevents concurrent over-redemption
- If discount validation fails mid-transaction, savepoint rolls back

## Discount on Orders

- ORDER-scope discounts: reduce `order.discount_amount`
- ITEM-scope discounts: stored per line in `order_items.item_discount_amount`; also summed into `order.discount_amount`

## Receipt Printing

What the customer receipt and kitchen ticket show, and the paper width, are store settings, see [prd-settings.md](prd-settings.md). The browser print and Bluetooth paths below render the same document.

Two print paths, both triggered from the receipt modal after checkout:

| Button | Mechanism | Works in |
|--------|-----------|----------|
| **Print Struk** | `window.print()` + CSS `@media print` (page width from the paper setting, 58 or 80 mm) | All browsers |
| **Bluetooth** | Web Bluetooth API → ESC/POS bytes → GATT write | Chrome only (HTTPS or localhost required) |

**Bluetooth implementation:**
- `$lib/utils/escpos.ts` — builds `Uint8Array` of ESC/POS commands from an `Order` (32-char width for 58mm paper, partial cut at end)
- `$lib/utils/bluetooth-printer.ts` — GATT connection manager; tries 3 known printer profiles, caches connection across prints
- Bluetooth button only renders when `navigator.bluetooth` is present; errors surface inline in the receipt modal
- "Web Bluetooth API globally disabled" → user-facing message: *Pastikan Bluetooth tidak diblokir*

## Transactions Page (`/transactions`)

- Toolbar: period (today / yesterday / 7 / 30 days), channel chips (all / dine-in / take away / online, online only when a platform is enabled), search (order no., platform ID, customer, notes), and a **list / grid** toggle (choice stored in `localStorage` key `kasir.ordersView`).
- Status chips: all, needs verification (`PENDING`), in kitchen / ready (only when kitchen management is on), confirmed, completed, cancelled. A banner above the toolbar links to the `PENDING` filter when self-orders are waiting.
- Filtering, search and paging (20 per page) happen on the server: `GET /orders` accepts `search` (order no., platform ID, customer, notes), `kind` (`dine`/`take`/`online`) and `state` (`verify`/`kitchen`/`ready`/`confirmed`/`done`/`cancelled`) besides the date range. Status chips show no counts. The banner count is one `status=PENDING&limit=1` request. The page refreshes every 30 s.
- List rows are tinted per state with a colored left bar; grid shows one card per order.
- Clicking an order opens a drawer like new-ui: 370px panel that pushes the list on wide screens (≥1200px) and overlays it below that. It shows status and platform chips, the platform payout box for online orders (gross, commission, expected payout, estimated or paid-out date, app-total mismatch), a progress bar (steps depend on POS / QR / online source and kitchen status), items with options and add-ons, subtotal / discount / total, and a paid line. Footer: Struk (opens the receipt on the detail page), Detail, and the status actions (Konfirmasi or Tolak for `PENDING`; Selesaikan or Batalkan for `CONFIRMED`, cancel needs a second click).
- Order state label: `PENDING` → needs verification; `CONFIRMED` → kitchen status (new / preparing / ready) or confirmed; `COMPLETED`; `CANCELLED`.

## Void & Refund

- Owner/Manager only (no PIN yet), on paid direct orders (`CONFIRMED`/`COMPLETED`, no `channel`). Online platform orders are refunded by the platform.
- `order_refunds` is append-only; `orders.total_amount` never changes, `orders.refunded_amount` accumulates and net value = `total_amount - refunded_amount`. Reports subtract `refunded_amount`.
- `POST /orders/{id}/refund` `{amount, method, reason}`: amount ≤ remaining value.
- `POST /orders/{id}/items/{item_id}/void` `{quantity, method, reason}`: refunds the proportional share of the line (the last unit takes the rounding) and increments `order_items.void_qty`. Voiding every remaining unit is rejected; cancel the order instead. Void does not restore ingredient stock.
- `method`: `CASH` (needs an open shift; lowers the shift's expected cash) or `TRANSFER`.
- UI: drawer buttons "Void item" and "Refund" open a dialog (amount or line + quantity, method, reason); the drawer lists every refund and the net value.

## Kitchen Ticket

Drawer → "Tiket dapur" opens `/transactions/{id}?ticket=1`: print dialog with quantities and modifiers only (voided units excluded), via `window.print()` or Bluetooth ESC/POS (`buildKitchenTicketBytes`).

## Paid orders are never edited

Items, prices and payment method of a paid order do not change. Corrections are separate records: void item, refund, cancel, or a new order. Do not add a "reopen bill" action that reloads a paid order into the POS cart.

## Service Charge & PB1 (direct orders)

- Store settings (Owner): `stores.service_bp` (dine-in service charge) and `stores.pb1_bp` (restaurant tax), basis points, default 0 (off).
- Computed once at order creation by `order_service.direct_order_fees`, rounded half up, and stored as `orders.service_amount` and `orders.pb1_amount`; both are included in `total_amount`.
  - `net` = subtotal after all discounts
  - `service` = `net × service_bp` only when `order_type = DINE_IN`
  - `pb1` = `(net + service) × pb1_bp`
- Self-orders with a table number are dine-in. Online platform orders do not get these fees (their tax stays `tax_bp`, included in the platform price).
- `POST /orders/preview` accepts `order_type` and returns `service_amount` and `pb1_amount`. The POS mirrors the formula for display; the self-order page uses the public preview (below) and falls back to the same formula only until the first response. The server total is authoritative. The public menu returns `service_bp` and `pb1_bp`.
- Shown on the POS cart, cash modal total, receipts (screen and ESC/POS), the transaction drawer and the self-order cart. Existing orders keep 0.
- Refunds use `total_amount` (fees included). Sales reports show revenue without PB1: `(total_amount - pb1_amount) × (total_amount - refunded_amount) / total_amount` per order; service charge stays in revenue. Item-level reports use line totals, which never include fees.
