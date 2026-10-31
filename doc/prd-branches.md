# PRD: Branches (Cabang)

## Overview

A **business** owns one menu catalog; each `Store` under it is a branch (outlet). Categories and products are defined once and used by every branch. Each branch can switch a product off and set its own price. Orders, shifts, ingredient stock, recipes, discounts, packages, expenses and settlements stay per store.

## Data

| Table / column | Notes |
|----------------|-------|
| `businesses` | `name`. Parent of stores |
| `stores.business_id` | Required. Stores of one business share the catalog |
| `items.business_id`, `item_categories.business_id` | Catalog scope. `store_id` stays as the creating store |
| `item_store_settings` | `item_id + store_id` unique, `is_sold` (default true), `price` (nullable int, Rupiah). A missing row means sold at the base price |

- Effective price = `item_store_settings.price` if set, else `items.base_price`. Online channel prices (manual or markup) derive from the effective price.
- `items.is_available` and `items.stock` are shared by all branches.
- **The catalog is owned by the parent store** (the business's oldest active store). Create, update, delete, stock, image, platform prices, option/addon groups and recipes of products, and all category writes, return 403 from a branch (`item_service.require_parent`). A branch edits only its own sold toggle and price (`PUT .../branches`). `GET /stores` and `GET /stores/{id}` return `is_parent`, `has_branches` and `parent_store_name`.
- **Recipes follow the parent store.** The parent store is the business's oldest store. A recipe is stored once on the item and edited only in the parent store (`PUT .../recipe` returns 400 elsewhere). A branch sale deducts the parent recipe's quantities from the branch's own ingredients, matched by name (case-insensitive); recipe ingredients the branch lacks deduct nothing.
- A product that is not sold at a branch is rejected by order create and preview there, and is left out of the public menu.

## Endpoints

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/stores/{id}/items` | AnyMember | Whole business catalog; each item has `price` (this branch) and `is_sold`. `is_sold=true/false` filters. The POS passes `is_sold=true` |
| GET | `/stores/{id}/items/{iid}/branches` | OwnerOrManager | One row per branch of the business the caller owns or manages: `store_id`, `store_name`, `is_parent`, `is_sold`, `price` |
| PUT | `/stores/{id}/items/{iid}/branches` | OwnerOrManager | `{branches: [{store_id, is_sold, price}]}`; null/0 price clears the override; other branches → 400 |
| POST | `/stores/{id}/branches` | OwnerOnly | `{name, slug?}`; creates a store in the same business and copies the source store's owners |

Catalog writes (items, categories) clear the menu caches of every branch in the business.

## UI

- Settings → **Cabang** (Owner): branch list and "Tambah cabang". The new branch is selected after creation; the header store switcher changes branch.
- Product editor (full screen): info column (photo, name, category chips, base price, HPP, stock, platform prices, **Dijual di cabang**), recipe column with inline **Opsi** and **Tambahan** cards (saved with the product, no modal), sticky HPP / margin card. **Dijual di cabang** has a switch and price input per branch (placeholder = base price); with one branch it shows a link to Settings. In a branch the recipe is read-only and shows the parent's lines.
- Store switcher shows a **Pusat** / **Cabang** badge when the business has more than one store.
- Products and Categories pages show a notice: in the parent store that changes apply to every branch, in a branch that the catalog is linked to the parent store. In a branch the add button, availability switch, delete, category edit and reorder are disabled; the product editor is read-only except **Dijual di cabang**, and Save sends only the branch settings.
- Product list marks items the current branch does not sell.

## Not implemented

Per-branch stock and availability, per-branch categories, moving users between branches, merging businesses.
