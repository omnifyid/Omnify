# PRD: Finance (Keuangan)

## Overview

Nav item `/finance` (Owner/Manager) with three tabs: **Shift & Kas**, **Pengeluaran** and **Pencairan platform**. Payables are not implemented.

## Shift & cash

| Table / column | Notes |
|----------------|-------|
| `shifts` | One open shift per store (partial unique index). `opening_cash`, `carry_expected` (system estimate at open), `counted_cash`, `expected_cash` + `variance` (snapshot at close), `note`, `status` (`OPEN`/`CLOSED`/`REVIEWED`), `review_note` |
| `cash_movements` | Cash `IN`/`OUT` inside a shift; `expense_id` when the OUT is an expense |
| `orders.confirmed_at` | Set when an order becomes `CONFIRMED`/`COMPLETED`; defines which shift a cash sale belongs to |
| `stores.shift_variance_threshold`, `stores.default_float` | Difference limit (default Rp 20.000) and fallback opening cash |

- Expected cash = `opening_cash` + `CASH` orders (status `CONFIRMED`/`COMPLETED`, `confirmed_at` inside the shift window) − cash refunds (`order_refunds` with `method = CASH`, `refunded_at` inside the window) + cash in − cash out. `PLATFORM` orders are not cash.
- Cash on hand with no open shift = last closed shift's `counted_cash` + `CASH` sales confirmed since it closed. The next open pre-fills this estimate; the cashier enters the counted amount and the gap is kept in `carry_expected` vs `opening_cash`.
- Closing takes a single counted total. A difference above the store limit requires a note; the shift then waits for Owner/Manager review. There is no PIN.
- Handover = close the shift, then the next cashier opens one starting from the counted cash.
- A cash-out in an expense category also creates a `DRAWER` expense. A `DRAWER` expense needs an open shift, is dated today, and creates the matching cash-out.
- POS payments are not blocked when no shift is open.

## Expenses

| Table | Notes |
|-------|-------|
| `expenses` | `date`, `category`, `description`, `amount` (int Rupiah), `source` (`BANK`/`EWALLET`/`PETTY`/`DRAWER`), `recurring`, `status` (`DRAFT`/`POSTED`), `user_id` |

- Categories are a fixed list in `ExpensesPanel.svelte` (Sewa, Listrik & air, Gaji & upah, Bahan non-stok, Marketing, Perbaikan & perawatan, Transport, Internet & software, Lain-lain).
- Creating a `recurring` expense also creates a `DRAFT` for the same day next month (clamped to month end). Confirming a draft posts it and creates the next draft.
- Only drafts can be deleted. Summary totals count `POSTED` only; drafts always show in the list regardless of the period.

## Platform payouts

| Table / column | Notes |
|----------------|-------|
| `platform_settlements` | `channel`, `received_date`, `amount` (received), `expected`, `diff` (`amount - expected`), `order_count`, `reason` |
| `orders.expected_payout_date` | Set at creation from `channel_settings.payout_lag_days` |
| `orders.settlement_id` | Null until the order is covered by a settlement |

- Receivable = channel order with status `CONFIRMED`/`COMPLETED`, no `settlement_id`.
- A settlement covers a chosen set of receivables of one channel (rows locked `FOR UPDATE`). `expected` is the sum of their `expected_payout`; a non-zero `diff` requires `reason`.
- Cancelling an already-settled order does not reverse the settlement.

## Endpoints

Shift endpoints (`/stores/{id}/shifts...`):

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/shifts/current` | AnyMember | Open shift with live expected cash, `cash_on_hand`, last count, limits |
| POST | `/shifts` | AnyMember | 201; `{opening_cash}`; 409 if one is open |
| POST | `/shifts/{sid}/close` | AnyMember | `{counted, note?}`; 400 if difference > limit and no note |
| POST | `/shifts/{sid}/cash-movements` | AnyMember | 201; `{type, amount, category, reason}`; shift must be open |
| GET | `/shifts` | OwnerOrManager | Paginated (20); `status`, `date_from`, `big_variance` |
| GET | `/shifts/summary` | OwnerOrManager | `date_from`; `count`, `open_count`, `review_count`, `big_count`, `total_variance` |
| GET | `/shifts/{sid}` | OwnerOrManager | Totals, non-cash payments, movements |
| POST | `/shifts/{sid}/review` | OwnerOrManager | `{note?}`; `CLOSED` → `REVIEWED` |

Expense and settlement endpoints (all OwnerOrManager):

| Method | Path | Notes |
|--------|------|-------|
| GET | `/stores/{id}/expenses` | Paginated; `category`, `source`, `date_from`, `date_to` |
| GET | `/stores/{id}/expenses/summary` | Same filters; `total`, `posted_count`, `draft_count`, `by_category` |
| POST | `/stores/{id}/expenses` | 201; `{date, category, description, amount, source, recurring}` |
| POST | `/stores/{id}/expenses/{eid}/confirm` | Draft → posted |
| DELETE | `/stores/{id}/expenses/{eid}` | 204; drafts only |
| GET | `/stores/{id}/settlements/overview` | Per channel: `outstanding`, `outstanding_count`, `overdue`, `received_month`, `commission_month` |
| GET | `/stores/{id}/settlements/batches` | Paginated; `channel` required; unsettled orders grouped by payout date (`date`, `order_count`, `gross`, `expected`) |
| GET | `/stores/{id}/settlements/receivables` | Paginated; `channel` required, `up_to` optional; unsettled orders |
| GET | `/stores/{id}/settlements/receivables/selection` | `channel`, `up_to?`; `{ids, count, expected}` for the payout form's default selection |
| GET | `/stores/{id}/settlements` | Paginated history; `channel` |
| POST | `/stores/{id}/settlements` | 201; `{channel, received_date, amount, order_ids, reason?}` |

## UI

- **Topbar chip** (all roles): "Buka shift" or cashier · since · cash on hand; menu for Kas masuk, Kas keluar, Tutup shift (shows expected, difference, note).
- **Shift & Kas**: period chips, KPIs, status filters, table; row opens detail with review action. Variance limit and default opening cash are in Settings (Owner).
- **Pengeluaran**: period chips (today/7/30/60 days), category and source filters, summary cards (total, top categories), table with draft Confirm/Delete, "Catat pengeluaran" modal.
- **Pencairan platform**: one card per platform (not yet paid out, overdue, received this month, commission this month); batches (server-grouped by payout date) with status (pending / due today / late N days) and "Catat cair"; payout history; "Catat pencairan" modal (default selection from `selection`, adjustable per row in a paged list; received amount, date, difference reason).
