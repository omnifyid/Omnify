# DB Schema

## Relationships

```
stores
  ├── store_memberships → users
  ├── item_categories
  ├── items → item_categories (FK)
  │     ├── option_groups → option_choices
  │     └── addon_groups → addon_choices
  ├── discounts
  └── orders → order_items
```

## Key Tables

| Table | Notes |
|-------|-------|
| `stores` | Root tenant entity |
| `store_memberships` | `user_id + store_id + role (OWNER/MANAGER/OPERATOR)` |
| `users` | `email`, bcrypt `password_hash`, `refresh_token_hash` |
| `password_reset_tokens` | Hashed single-use password reset tokens, expiry, consumed timestamp |
| `item_categories` | `name`, `icon` (emoji), `store_id` |
| `items` | `name`, `price` (int, Rupiah), `cost_price` (HPP, nullable int, Rupiah; staff-only, omitted from the public menu), `is_available`, `stock`, `store_id`, `category_id` |
| `discounts` | See [prd-discounts.md](prd-discounts.md) |
| `orders` | `status`, `payment_method` (`CASH`/`CARD`/`QRIS`/`TRANSFER`/`PLATFORM`), `channel` (nullable), `subtotal`, `discount_amount`, `total`, `kitchen_status` (nullable), `store_id` |
| `stores.kitchen_enabled` | Opt-in kitchen management, see [prd-kitchen.md](prd-kitchen.md) |
| `stores.service_bp`, `stores.pb1_bp`, `orders.service_amount`, `orders.pb1_amount` | Dine-in service charge and PB1 on direct orders, see [prd-orders.md](prd-orders.md) |
| `ingredients`, `recipe_lines`, `stock_movements` | Ingredient stock, product recipes, stock log, see [prd-inventory.md](prd-inventory.md) |
| `channel_settings`, `item_channel_prices` | Per store + channel: `enabled`, `commission_bp`, `markup_bp`, `payout_lag_days`; per item + channel manual `price`. `stores.tax_bp`; order channel columns, see [prd-channels.md](prd-channels.md) |
| `expenses`, `platform_settlements` | Operating expenses; payouts received from online platforms (`orders.settlement_id`, `orders.expected_payout_date`), see [prd-finance.md](prd-finance.md) |
| `order_refunds` | Append-only void/refund log per order (`type`, `method`, `amount`, `reason`, `refunded_at`); `orders.refunded_amount`, `order_items.void_qty`, see [prd-orders.md](prd-orders.md) |
| `order_items` | `is_done` (kitchen checklist), `void_qty`. Snapshot of `name`, `unit_price`, `quantity`, `options_snapshot`, `addons_snapshot` |

## Model Conventions

- All PKs: `UUID` (`default=uuid.uuid4`)
- `TimestampMixin`: adds `created_at`, `updated_at` to every model
- Cascade deletes: child rows deleted when parent store is deleted (`ondelete="CASCADE"`)
- Soft FK on discount targets: `ondelete="SET NULL"` (item/category deleted → discount target becomes null)

## Options vs Addons

| | OptionGroup | AddonGroup |
|-|-------------|------------|
| Selection | Mutually exclusive (radio) | Multi-select (checkbox) |
| Price | No extra price | `extra_price` per choice |
| Example | Size, Ice level | Extra shot, Topping |

## Migration Pattern

```python
# Adding non-nullable column to existing table — always include server_default
op.add_column('table', sa.Column('col', sa.String(100), nullable=False, server_default=''))

# Making column nullable
op.alter_column('table', 'col', existing_type=sa.String(50), nullable=True)
```
