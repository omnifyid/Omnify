# CLAUDE.md — kasir-fe

SvelteKit + Svelte 5 frontend for the Kasir POS system.

## Commands

```bash
npm install          # install dependencies
npm run dev          # start dev server (http://localhost:5173)
npm run build        # production build
npm run check        # svelte-check type checking
npm run lint         # eslint + prettier check
npm run format       # prettier format
```

## Key Patterns

**Svelte 5 runes:** use `$state`, `$derived`, `$effect` for local component state — not legacy stores.

**API client** (`$lib/api/client.ts`):
```typescript
import { api } from '$lib/api/client';
api.get<PaginatedResponse<T>>('/stores/${storeId}/resource?limit=20&offset=0')
api.post('/stores/${storeId}/resource', payload)
api.patch('/stores/${storeId}/resource/${id}', payload)
api.delete('/stores/${storeId}/resource/${id}')
```

**Pagination:** always type as `PaginatedResponse<T>`, extract items with `paginatedItems()` from `$lib/api/pagination.ts`.

**Modal state reset:** always reset all form fields in `openCreate()` before setting `creatingOpen = true`.

**Discount percentage:** form shows/accepts human % (`20`), `buildPayload` multiplies ×100 before sending (`2000`), `startEdit` divides ÷100 on load.

## Design System

See [../doc/design-system.md](../doc/design-system.md) for CSS vars, utility classes, and modal/page-header patterns.

## Further Docs

- [../doc/architecture.md](../doc/architecture.md) — full stack overview
- [../doc/conventions.md](../doc/conventions.md) — naming rules, enum values
- [../doc/api-contracts.md](../doc/api-contracts.md) — endpoint reference
- [../doc/prd-discounts.md](../doc/prd-discounts.md) — discount feature spec
- [../doc/prd-orders.md](../doc/prd-orders.md) — order flow spec
