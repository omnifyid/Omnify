# PRD: Kitchen Management

## Overview

Per-store opt-in kitchen display (KDS). Owner/Manager toggles **Manajemen Dapur** in Settings (`stores.kitchen_enabled`, default `false`). When off, the `/kitchen` nav item is hidden and no kitchen state is recorded.

## Kitchen Status

Separate from `OrderStatus`. `orders.kitchen_status`: `NEW → COOKING → READY → SERVED` (nullable).

- Set to `NEW` when an order becomes `CONFIRMED` while the store has kitchen enabled: POS orders at creation, self-orders when the cashier confirms.
- `null` when kitchen is off, or the order is still `PENDING`.
- `order_items.is_done` is the per-line prep checklist.
- The board shows orders with `status = CONFIRMED` and `kitchen_status` in `NEW/COOKING/READY`; `SERVED`, completed or cancelled orders drop off.

## Endpoints

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/stores/{id}/kitchen/orders` | AnyMember | Paginated, oldest first |
| PATCH | `/stores/{id}/orders/{oid}/kitchen` | AnyMember | `{kitchen_status}` |
| PATCH | `/stores/{id}/orders/{oid}/items/{iid}/kitchen` | AnyMember | `{is_done}` |

Both PATCH routes return `OrderRead` and 400 if the store has kitchen disabled or the order is not in the kitchen flow.

## UI — `/kitchen`

Three columns (Baru / Diproses / Siap diambil; tabs on mobile). Ticket: order no., table/customer, elapsed timer (amber ≥ 8 min, red ≥ 15 min), item checklist with options/addons, order notes, advance button. Tickets in Diproses and Siap diambil have a back button that moves them one column back. "Sudah diambil" asks for confirmation first; after it an 8 s Undo toast returns the ticket to Siap diambil. Polls every 10 s.

Recipes/availability tab is not implemented.
