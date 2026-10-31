# API Contracts

## URL Pattern

All store-scoped resources follow:
```
/stores/{store_id}/{resource}
/stores/{store_id}/{resource}/{resource_id}
```

## RBAC Guards (backend)

Declared in route via `Depends(...)`. Defined in `app/core/dependencies.py`.

| Guard | Allowed roles |
|-------|--------------|
| `OwnerOnly` | Owner |
| `OwnerOrManager` | Owner, Manager |
| `AnyMember` | Owner, Manager, Operator |

## Pagination

All list endpoints return:
```json
{ "items": [...], "total": 100, "limit": 20, "offset": 0 }
```

Query params: `?limit=N&offset=N`

Backend schema: `PaginatedResponse[T]` from `app/schemas/common.py`  
Frontend type: `PaginatedResponse<T>` from `$lib/api/types.ts`  
Frontend helper: `paginatedItems(response)` → `response.items`

## Frontend API Client

Location: `$lib/api/client.ts`

```typescript
import { api } from '$lib/api/client';

api.get<PaginatedResponse<Discount>>(`/stores/${storeId}/discounts?limit=20&offset=0`)
api.post(`/stores/${storeId}/discounts`, payload)
api.patch(`/stores/${storeId}/discounts/${id}`, payload)
api.delete(`/stores/${storeId}/discounts/${id}`)
```

## Key Endpoints

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| POST | `/admin/seed/reset` | Super admin | Needs `DEMO_MODE=true`. Remove demo data and seed it again, see [demo-data.md](demo-data.md) |
| DELETE | `/admin/seed` | Super admin | Remove demo data only |
| GET | `/auth/demo-accounts` | Public | Demo accounts and password for the login screen; empty unless `DEMO_MODE=true` |
| POST | `/auth/forgot-password` | Public | Sends reset email when account exists; always 204 unless email provider fails |
| POST | `/auth/reset-password` | Public | Consumes reset token and updates password |
| GET | `/stores/{id}/discounts` | OwnerOrManager | Paginated |
| POST | `/stores/{id}/discounts` | OwnerOrManager | 201 on create |
| PATCH | `/stores/{id}/discounts/{did}` | OwnerOrManager | Partial update |
| DELETE | `/stores/{id}/discounts/{did}` | OwnerOrManager | 204 no body |
| POST | `/stores/{id}/discounts/validate` | AnyMember | Validate promo code |
| GET | `/stores/{id}/categories` | AnyMember | Paginated |
| GET | `/stores/{id}/items` | AnyMember | Paginated, filterable; business catalog with this branch's `price`/`is_sold` |
| PUT | `/stores/{id}/items/{iid}/branches` | OwnerOrManager | Per-branch sold/price, see [prd-branches.md](prd-branches.md) |
| POST | `/stores/{id}/branches` | OwnerOnly | Create a branch in the same business |
| GET | `/stores/{id}/orders` | AnyMember | Paginated; `status`, `payment_method`, `date_from`, `date_to`, `search`, `kind`, `state` |
| POST | `/stores/{id}/orders/{oid}/refund` | OwnerOrManager | See [prd-orders.md](prd-orders.md) |
| POST | `/stores/{id}/orders/{oid}/items/{iid}/void` | OwnerOrManager | See [prd-orders.md](prd-orders.md) |
| GET | `/stores/{id}/channels` | AnyMember | Online platform settings and `reports/by-channel`; see [prd-channels.md](prd-channels.md) |
| GET | `/stores/{id}/expenses` | OwnerOrManager | Paginated; expenses and platform settlements in [prd-finance.md](prd-finance.md) |
| GET | `/stores/{id}/ingredients` | AnyMember | Paginated; inventory endpoints in [prd-inventory.md](prd-inventory.md) |

## Query Parameters

### Items (`GET /stores/{id}/items`)

| Param | Type | Notes |
|-------|------|-------|
| `limit` | int | Pagination limit |
| `offset` | int | Pagination offset |
| `search` | str | Filter by item name (case-insensitive) |
| `is_available` | bool \| null | Filter by availability (`true`, `false`, or omit for all) |
| `stock_out` | bool | If `true`, returns only items with `stock <= 0` |
| `is_sold` | bool \| null | `true` = sold at this branch (POS), `false` = switched off here, omit for all |

### Orders (`GET /stores/{id}/orders`)

| Param | Type | Notes |
|-------|------|-------|
| `limit` | int | Pagination limit |
| `offset` | int | Pagination offset |
| `payment_method` | str | Filter by payment method (`CASH`, `CARD`, `QRIS`, `TRANSFER`) |
| `date_from` | str (ISO 8601) | Filter orders created on or after this date |
| `date_to` | str (ISO 8601) | Filter orders created on or before this date |
