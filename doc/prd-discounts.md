# PRD: Discounts

## Overview

Discounts reduce the price of an order or specific items. They can be applied manually (via promo code) or automatically (no code needed).

## Discount Types

| Type | Value format | Notes |
|------|-------------|-------|
| `PERCENTAGE` | Basis points (1000 = 10%) | Optional `max_discount_amount` cap (Rupiah) |
| `FIXED` | Rupiah integer | No cap field |

**Frontend ↔ Backend conversion (PERCENTAGE only):**
- Form shows/accepts human-readable % (e.g. `20` for 20%)
- `buildPayload` multiplies by 100 before sending: `20 → 2000`
- `startEdit` divides by 100 on load: `2000 → 20`
- `discountSummary` divides by 100 for display: `2000 → "20%"`
- A migration (`e1f2a3b4c5d6`) was run to fix legacy records that were stored without this conversion (value=20 instead of 2000)

## Scope

| Scope | Description |
|-------|-------------|
| `ORDER` | Applied to the whole cart subtotal |
| `ITEM` | Applied to matching line items only |

## Item Scope Targets

When `scope = ITEM`, a `target_type` must be set:
- `ALL` — applies to every item in the cart
- `CATEGORY` — applies to items in a specific `target_category_id`
- `ITEM` — applies to a specific `target_item_id`

## Validation Rules (backend `validate()`)

1. Discount must exist, be active, and code must match
2. `expires_at` must not be in the past
3. `max_uses` must not be exceeded (`used_count >= max_uses`)
4. `min_order_amount` must be met by `cart_subtotal`
5. For ITEM scope: per-line discount calculated via `calc_line_discount()` + `line_matches_discount()`

## Auto-apply

- `is_automatic = True` → no code required; cashier doesn't enter anything
- `is_automatic = False` → `code` field required (non-empty)
- Frontend sends `code: null` for auto-apply discounts

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | Display name (required) |
| `code` | str \| null | Promo code; null for auto-apply |
| `discount_type` | enum | `PERCENTAGE` or `FIXED` |
| `value` | int | Basis points or Rupiah |
| `max_discount_amount` | int \| null | Cap for PERCENTAGE only |
| `scope` | enum | `ORDER` or `ITEM` |
| `target_type` | enum \| null | `ALL`, `CATEGORY`, `ITEM` (ITEM scope only) |
| `target_item_id` | UUID \| null | — |
| `target_category_id` | UUID \| null | — |
| `is_automatic` | bool | — |
| `min_order_amount` | int \| null | Minimum cart total to apply |
| `max_uses` | int \| null | null = unlimited |
| `used_count` | int | Incremented on order completion |
| `expires_at` | datetime \| null | UTC |
| `is_active` | bool | Soft on/off toggle |

## UI

- List page: table with Name/Code, Value, Scope·Target, Auto badge, Active status, Edit/Delete
- Create & Edit: modal (bottom sheet on mobile, centered on desktop)
- Page header has "Add Discount" button that opens create modal

## POS Promo Code Check

The POS cart panel has an inline promo code row: `[input][Apply button]`.

- Clicking Apply (or pressing Enter) calls `POST /stores/{store_id}/orders/preview`
- Request body: `{ discount_code, items: [{ item_id, quantity, selected_option_choice_ids, selected_addon_choice_ids }] }`
- Response: `{ subtotal, discount_amount, total_amount, valid, message }`
- If valid: discount row appears in order summary, Charge button and cash modal show discounted total
- Cart mutations (add/remove/qty change) clear the applied promo result
- The preview endpoint is read-only — no DB writes, no `used_count` increment, no locks
- `OrderPreviewRequest` / `OrderPreviewResponse` schemas in `app/schemas/order.py`
