"""initial_schema

Revision ID: 215de5d32fc4
Revises:
Create Date: 2026-05-03 15:15:28.073856

"""

from typing import Sequence, Union

from alembic import op

revision: str = "215de5d32fc4"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Pure SQL migration — no sa.Enum objects so SQLAlchemy never auto-fires
# its own CREATE TYPE logic from target_metadata scanning.
UPGRADE_SQL = """
-- Enums
CREATE TYPE store_role     AS ENUM ('OWNER', 'MANAGER', 'OPERATOR');
CREATE TYPE discount_type  AS ENUM ('PERCENTAGE', 'FIXED');
CREATE TYPE order_status   AS ENUM ('PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED');
CREATE TYPE payment_method AS ENUM ('CASH', 'CARD', 'QRIS', 'TRANSFER');

-- Users
CREATE TABLE users (
    id               UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    email            VARCHAR(255) NOT NULL UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    full_name        VARCHAR(255) NOT NULL,
    is_active        BOOLEAN      NOT NULL DEFAULT true,
    is_superadmin    BOOLEAN      NOT NULL DEFAULT false,
    created_at       TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX ix_users_email ON users (email);

-- Stores
CREATE TABLE stores (
    id          UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    logo_url    VARCHAR(512),
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX ix_stores_slug ON stores (slug);

-- Store memberships
CREATE TABLE store_memberships (
    id         UUID       NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id    UUID       NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    store_id   UUID       NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    role       store_role NOT NULL,
    is_active  BOOLEAN    NOT NULL DEFAULT true,
    created_at TIMESTAMP  NOT NULL DEFAULT now(),
    updated_at TIMESTAMP  NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_store UNIQUE (user_id, store_id)
);
CREATE INDEX ix_store_memberships_user_id  ON store_memberships (user_id);
CREATE INDEX ix_store_memberships_store_id ON store_memberships (store_id);

-- Item categories
CREATE TABLE item_categories (
    id         UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id   UUID         NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name       VARCHAR(100) NOT NULL,
    sort_order INTEGER      NOT NULL DEFAULT 0,
    created_at TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX ix_item_categories_store_id ON item_categories (store_id);

-- Items
CREATE TABLE items (
    id           UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id     UUID         NOT NULL REFERENCES stores(id)          ON DELETE CASCADE,
    category_id  UUID                  REFERENCES item_categories(id) ON DELETE SET NULL,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    base_price   INTEGER      NOT NULL,
    image_url    VARCHAR(512),
    is_available BOOLEAN      NOT NULL DEFAULT true,
    sort_order   INTEGER      NOT NULL DEFAULT 0,
    created_at   TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX ix_items_store_id    ON items (store_id);
CREATE INDEX ix_items_category_id ON items (category_id);

-- Option groups (mutually exclusive choices, no price)
CREATE TABLE option_groups (
    id          UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    item_id     UUID         NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    is_required BOOLEAN      NOT NULL DEFAULT false,
    sort_order  INTEGER      NOT NULL DEFAULT 0
);
CREATE INDEX ix_option_groups_item_id ON option_groups (item_id);

-- Option choices
CREATE TABLE option_choices (
    id         UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    group_id   UUID         NOT NULL REFERENCES option_groups(id) ON DELETE CASCADE,
    label      VARCHAR(100) NOT NULL,
    is_default BOOLEAN      NOT NULL DEFAULT false,
    sort_order INTEGER      NOT NULL DEFAULT 0
);
CREATE INDEX ix_option_choices_group_id ON option_choices (group_id);

-- Addon groups (multi-select with price)
CREATE TABLE addon_groups (
    id          UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    item_id     UUID         NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    is_required BOOLEAN      NOT NULL DEFAULT false,
    min_select  INTEGER      NOT NULL DEFAULT 0,
    max_select  INTEGER,
    sort_order  INTEGER      NOT NULL DEFAULT 0
);
CREATE INDEX ix_addon_groups_item_id ON addon_groups (item_id);

-- Addon choices
CREATE TABLE addon_choices (
    id           UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    group_id     UUID         NOT NULL REFERENCES addon_groups(id) ON DELETE CASCADE,
    label        VARCHAR(100) NOT NULL,
    extra_price  INTEGER      NOT NULL DEFAULT 0,
    is_available BOOLEAN      NOT NULL DEFAULT true,
    sort_order   INTEGER      NOT NULL DEFAULT 0
);
CREATE INDEX ix_addon_choices_group_id ON addon_choices (group_id);

-- Packages
CREATE TABLE packages (
    id           UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id     UUID         NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    flat_price   INTEGER      NOT NULL,
    is_available BOOLEAN      NOT NULL DEFAULT true,
    sort_order   INTEGER      NOT NULL DEFAULT 0,
    created_at   TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX ix_packages_store_id ON packages (store_id);

-- Package items
CREATE TABLE package_items (
    id         UUID    NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    package_id UUID    NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    item_id    UUID    NOT NULL REFERENCES items(id)    ON DELETE RESTRICT,
    quantity   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX ix_package_items_package_id ON package_items (package_id);

-- Discounts
CREATE TABLE discounts (
    id                UUID          NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id          UUID          NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    code              VARCHAR(50)   NOT NULL,
    discount_type     discount_type NOT NULL,
    value             INTEGER       NOT NULL,
    min_order_amount  INTEGER,
    max_uses          INTEGER,
    used_count        INTEGER       NOT NULL DEFAULT 0,
    is_active         BOOLEAN       NOT NULL DEFAULT true,
    expires_at        TIMESTAMPTZ,
    created_at        TIMESTAMP     NOT NULL DEFAULT now(),
    updated_at        TIMESTAMP     NOT NULL DEFAULT now()
);
CREATE INDEX ix_discounts_store_id ON discounts (store_id);
CREATE INDEX ix_discounts_code     ON discounts (code);

-- Orders
CREATE TABLE orders (
    id                      UUID           NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id                UUID           NOT NULL REFERENCES stores(id)    ON DELETE RESTRICT,
    operator_id             UUID           NOT NULL REFERENCES users(id)     ON DELETE RESTRICT,
    discount_id             UUID                    REFERENCES discounts(id) ON DELETE SET NULL,
    order_number            VARCHAR(30)    NOT NULL,
    status                  order_status   NOT NULL DEFAULT 'PENDING',
    payment_method          payment_method NOT NULL,
    subtotal                INTEGER        NOT NULL,
    discount_amount         INTEGER        NOT NULL DEFAULT 0,
    total_amount            INTEGER        NOT NULL,
    discount_code_snapshot  VARCHAR(50),
    notes                   TEXT,
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMP      NOT NULL DEFAULT now(),
    updated_at              TIMESTAMP      NOT NULL DEFAULT now()
);
CREATE INDEX ix_orders_store_id    ON orders (store_id);
CREATE INDEX ix_orders_operator_id ON orders (operator_id);
CREATE INDEX ix_orders_order_number ON orders (order_number);

-- Order items (price snapshots frozen at order time)
CREATE TABLE order_items (
    id                   UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    order_id             UUID         NOT NULL REFERENCES orders(id)   ON DELETE CASCADE,
    item_id              UUID                  REFERENCES items(id)    ON DELETE SET NULL,
    package_id           UUID                  REFERENCES packages(id) ON DELETE SET NULL,
    item_name_snapshot   VARCHAR(255) NOT NULL,
    unit_price_snapshot  INTEGER      NOT NULL,
    quantity             INTEGER      NOT NULL,
    addon_total_snapshot INTEGER      NOT NULL DEFAULT 0,
    line_total           INTEGER      NOT NULL,
    options_snapshot     JSONB,
    addons_snapshot      JSONB
);
CREATE INDEX ix_order_items_order_id ON order_items (order_id);

-- Refresh tokens
CREATE TABLE refresh_tokens (
    id          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ  NOT NULL,
    is_revoked  BOOLEAN      NOT NULL DEFAULT false,
    user_agent  VARCHAR(512)
);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS discounts;
DROP TABLE IF EXISTS package_items;
DROP TABLE IF EXISTS packages;
DROP TABLE IF EXISTS addon_choices;
DROP TABLE IF EXISTS addon_groups;
DROP TABLE IF EXISTS option_choices;
DROP TABLE IF EXISTS option_groups;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS item_categories;
DROP TABLE IF EXISTS store_memberships;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS users;
DROP TYPE IF EXISTS payment_method;
DROP TYPE IF EXISTS order_status;
DROP TYPE IF EXISTS discount_type;
DROP TYPE IF EXISTS store_role;
"""


def _run_sql(sql: str) -> None:
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            op.execute(stmt)


def upgrade() -> None:
    _run_sql(UPGRADE_SQL)


def downgrade() -> None:
    _run_sql(DOWNGRADE_SQL)
