# Conventions

## Backend

- **Pagination**: all list endpoints return `PaginatedResponse[T]` — `{items, total, limit, offset}`. Import from `app/schemas/common.py`. Never return plain lists from list routes.
- **PATCH updates**: use `model_dump(exclude_unset=True)` so only sent fields are updated.
- **DB PKs**: UUID everywhere — `id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)`.
- **Nullable columns**: use `Mapped[str | None]` + `nullable=True`. Non-nullable columns get a `server_default` when added via migration.
- **Enum values**: use exact DB enum strings. `DiscountType` → `PERCENTAGE`, `FIXED` (NOT `FIXED_AMOUNT`). `DiscountScope` → `ORDER`, `ITEM`. `DiscountTarget` → `ALL`, `CATEGORY`, `ITEM`.
- **Money**: integers only (Rupiah). Percentage discounts in basis points (1000 = 10%).
- **Migrations**: always set `server_default` when adding a non-nullable column to an existing table.

## Frontend

- **Discount type enum**: `'PERCENTAGE' | 'FIXED'` — use `FIXED` not `FIXED_AMOUNT`.
- **Discount usage field**: `used_count` (not `use_count`).
- **Paginated API calls**: always type as `PaginatedResponse<T>`, extract with `paginatedItems()`.
- **Svelte 5 reactivity**: use `$state`, `$derived`, `$effect` runes — not stores for local component state.
- **Modal state reset**: always reset all form fields in `openCreate()` before setting `creatingOpen = true`.
- **Code field**: frontend sends `null` for empty code (auto-apply discounts). Backend accepts `code: str | None`.
- **i18n**: UI copy uses `$lib/i18n/language.svelte` and typed English keys from `$lib/i18n/messages.ts`. Indonesian (`id`) is the default language. Keep code variables and message keys in English, e.g. `store -> Toko` for `id` and `store -> Store` for `en`.

## Naming

| Concept | Backend | Frontend |
|---------|---------|----------|
| Discount usage count | `used_count` | `used_count` |
| Discount type fixed | `FIXED` | `FIXED` |
| Paginated list | `PaginatedResponse[T]` | `PaginatedResponse<T>` |

## Data tables

- Every data table has pagination, 20 rows per page (`PAGE_SIZE` in `$lib/utils/paging`) using `<Pagination>` from `$lib/components/Pagination.svelte`.
- Paging, filtering and search are server-side (`limit`/`offset`, `PaginatedResponse<T>`). Never load a whole table to page or filter it in the browser. Totals and KPIs come from a dedicated summary endpoint, not from counting loaded rows. Filter chips do not show per-chip counts.
- Reset to page 1 whenever a filter, search, or period changes; debounce search requests (350 ms).
