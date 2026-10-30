# PRD: Online Platforms (GoFood, GrabFood, ShopeeFood)

## Overview

The cashier records orders that arrive through a food-delivery platform. The platform collects payment from the customer and pays the store out periodically, net of commission. The app does not receive money; it records what each platform owes. Owner/Manager track what each platform owes and record payouts in **Keuangan → Pencairan platform**, see [prd-finance.md](prd-finance.md).

## Settings (per store, Owner only)

- `channel_settings` row per store + channel: `enabled`, `commission_bp`, `markup_bp` (basis points; 2000 = 20%), `payout_lag_days` (default 2; the order's `expected_payout_date` = order date + lag). Missing rows read as disabled, 0, 0.
- `stores.tax_bp`: tax already included in online prices (basis points). Editable in Settings by the Owner.
- The POS shows the **Online** tab only when at least one channel is enabled.

## Order rules (`order_service.create_order`)

- `channel` (`GOFOOD`/`GRABFOOD`/`SHOPEEFOOD`) requires `channel_order_id`; `payment_method` is forced to `PLATFORM`.
- Channel must be enabled, else 400. A non-cancelled order with the same `channel` + `channel_order_id` (case-insensitive) gives 409.
- Online unit price and each add-on price = `amount × (1 + markup)` rounded up to the next Rp500 (`channel_service.ceil_markup`). The POS mirrors this in `mk()`.
- A manual platform price (`item_channel_prices`, one row per item + channel) replaces the base price for that platform; markup then applies to add-ons only. Items without one use the markup price.
- Discounts (code and automatic) are not applied.
- `commission_amount = round(total × commission_bp / 10000)`, `expected_payout = total − commission_amount`, `tax_amount` = tax portion of the (tax-inclusive) total. All three are stored on the order, so later rate changes do not alter past orders.
- `app_total` is the total shown in the platform app. It is stored for reference; the POS warns on mismatch, the API does not reject it.
- Orders start `CONFIRMED` (kitchen flow and ingredient deduction run as usual). Cancelling follows the normal cancel path; cancelled orders are excluded from the channel report.

## Endpoints

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/stores/{id}/channels` | AnyMember | All three channels with defaults filled in |
| PATCH | `/stores/{id}/channels/{channel}` | OwnerOnly | `{enabled, commission_bp, markup_bp}` |
| GET | `/stores/{id}/reports/by-channel` | OwnerOrManager | `from_date`, `to_date`; per channel: `order_count`, `gross`, `commission`, `net`, `tax` |
| PUT | `/stores/{id}/items/{item_id}/channel-prices` | OwnerOrManager | `{prices: {GOFOOD: 25000, GRABFOOD: null}}` replaces all manual prices of the item; null/0 clears. `ItemRead.channel_prices` returns them (staff only, not in the public menu) |
| POST | `/stores/{id}/orders` | AnyMember | Accepts `channel`, `channel_order_id`, `app_total`, `driver_name` (optional) |

## UI

- POS cart: order-type tabs gain **Online**. Online shows platform logo buttons, platform order ID, customer name, app note, app total; hides discount and payment method; charge button reads "Kirim ke dapur". Menu prices switch to the platform price.
- Product edit modal: **Harga per platform online** lists each enabled platform with an input; the placeholder is the automatic markup price.
- Transactions list shows the platform name in the payment badge and can filter by `PLATFORM`.

## Not implemented

Refunds/partial cancels from the platform.
