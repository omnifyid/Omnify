# Demo Login

Base URL: `http://localhost:8000`

## Accounts

| Role | Email | Password |
|---|---|---|
| Owner | owner@demo.com | demo1234 |
| Manager | manager@demo.com | demo1234 |
| Operator | operator@demo.com | demo1234 |

## Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "owner@demo.com",
  "password": "demo1234"
}
```

Response:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<token>",
  "token_type": "bearer"
}
```

Use `access_token` as Bearer token on all protected endpoints:

```http
Authorization: Bearer <access_token>
```

## Role Permissions

| Endpoint | Owner | Manager | Operator |
|---|:---:|:---:|:---:|
| View catalog | ✓ | ✓ | ✓ |
| Create order | ✓ | ✓ | ✓ |
| Manage catalog (items, categories) | ✓ | ✓ | — |
| Manage discounts | ✓ | ✓ | — |
| View reports | ✓ | ✓ | — |
| Manage staff | ✓ | — | — |
| Store settings | ✓ | — | — |

## Demo Store

| Field | Value |
|---|---|
| Name | Kopi Senja |
| Slug | `kopi-senja` |

Store ID is returned from `GET /api/v1/stores` after login.
