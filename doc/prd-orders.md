# PRD: Orders

## Order Flow

1. Cashier builds cart (items + options + addons)
2. Optional: apply discount (promo code or auto-apply)
3. Select payment method
4. Confirm → order created atomically in DB
5. Receipt shown; order moves to COMPLETED

## Order Status

`PENDING` → `CONFIRMED` → `COMPLETED` | `CANCELLED`

## Payment Methods

`CASH`, `CARD`, `QRIS`, `TRANSFER`

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

Two print paths, both triggered from the receipt modal after checkout:

| Button | Mechanism | Works in |
|--------|-----------|----------|
| **Print Struk** | `window.print()` + CSS `@media print` (58mm, `size: 58mm auto`) | All browsers |
| **Bluetooth** | Web Bluetooth API → ESC/POS bytes → GATT write | Chrome only (HTTPS or localhost required) |

**Bluetooth implementation:**
- `$lib/utils/escpos.ts` — builds `Uint8Array` of ESC/POS commands from an `Order` (32-char width for 58mm paper, partial cut at end)
- `$lib/utils/bluetooth-printer.ts` — GATT connection manager; tries 3 known printer profiles, caches connection across prints
- Bluetooth button only renders when `navigator.bluetooth` is present; errors surface inline in the receipt modal
- "Web Bluetooth API globally disabled" → user-facing message: *Pastikan Bluetooth tidak diblokir*
