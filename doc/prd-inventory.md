# PRD: Inventory

## Overview

Per-store ingredient stock (bahan baku). Products have an optional recipe; every sale deducts the recipe's ingredients automatically. Nav item `/inventory` (Owner/Manager).

## Data

| Table | Notes |
|-------|-------|
| `ingredients` | `name` (unique per store), `unit`, `category`, `stock`, `min_stock`, `cost_price` (int Rupiah per unit). Quantities are `Numeric(14,3)`, exposed as floats |
| `recipe_lines` | `item_id + ingredient_id` unique, `quantity` per 1 item sold |
| `stock_movements` | Append-only log: `type` (`INITIAL`/`RESTOCK`/`SALE`/`RETURN`/`OPNAME`), signed `quantity`, `balance_after`, `order_id`, `user_id`, `note` |

Low stock: `stock <= min_stock`. Status chip: **Kritis** under half of `min_stock`, **Menipis** at or under `min_stock`, otherwise **Aman**. The bar is full at twice `min_stock`.

## Rules

- Stock changes only through `inventory_service._move`, which logs a movement. Rows are locked `FOR UPDATE` (ordered by id) before changing.
- `order_service.create_order` calls `deduct_for_order` inside the order savepoint. Stock may go negative; sales are never blocked by ingredient stock. Package lines and items without a recipe deduct nothing.
- Cancelling an order (`update_order_status` → `CANCELLED`) calls `restore_for_order`, which reverses the order's `SALE` movements once (a `RETURN` movement marks it done).
- Stock opname sets stock to the counted value; each non-zero difference is logged as `OPNAME`. Unchanged rows log nothing.
- Deleting an ingredient cascades to recipe lines and movements.
- `items.stock` (finished-goods count) is independent of ingredient stock.

## Endpoints

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/stores/{id}/ingredients` | AnyMember | Paginated; `search`, `low_stock`, `level` (`low` = at or under `min_stock` but not critical, `critical` = under half of it) |
| GET | `/stores/{id}/ingredients/summary` | AnyMember | `count`, `low_count`, `stock_value`, `categories` (drives the KPIs) |
| POST | `/stores/{id}/ingredients` | OwnerOrManager | 201; `initial_stock` logs `INITIAL`; 409 on duplicate name |
| PATCH | `/stores/{id}/ingredients/{iid}` | OwnerOrManager | Metadata only, never stock |
| DELETE | `/stores/{id}/ingredients/{iid}` | OwnerOrManager | 204 |
| POST | `/stores/{id}/ingredients/{iid}/restock` | OwnerOrManager | `{quantity, cost_price?, note?}`; updates unit cost if given |
| POST | `/stores/{id}/inventory/opname` | OwnerOrManager | `{lines: [{ingredient_id, counted}]}` → `{adjusted}` |
| GET | `/stores/{id}/inventory/movements` | AnyMember | Paginated, newest first; `ingredient_id`, `type` |
| GET/PUT | `/stores/{id}/items/{item_id}/recipe` | OwnerOrManager | PUT replaces all lines `{lines: [{ingredient_id, quantity}]}` |

## UI

- `/inventory`: KPIs (ingredient count, low stock, stock value), tabs **Stok** (status chips Semua / Menipis / Kritis filter on the server; list with a stock-level bar and status chip per ingredient, add/edit/delete modal, "Terima" restock modal), **Stock opname** (one row per ingredient: system stock, count input, difference in units and its value in Rupiah; total value of differences, save), **Mutasi** (latest 100 movements).
- Recipe editor: inline "Resep & bahan baku" column of the product editor in `ProductsPanel.svelte` (per-line quantity, unit cost, subtotal, total). Branches follow the parent store's recipe, see [prd-branches.md](prd-branches.md). Existing lines come from `GET .../recipe` (name, unit, cost); new lines are added with `IngredientPicker` (search-as-you-type), so the ingredient list is never loaded in full.

## Not implemented

Multi-outlet stock, transfers, suppliers, purchase orders.
