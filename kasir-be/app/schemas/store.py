import uuid

from pydantic import BaseModel, Field

from app.models.membership import StoreRole


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    show_logo: bool | None = None
    receipt_header: str | None = None
    receipt_footer: str | None = None
    pos_dine_in_enabled: bool | None = None
    pos_table_enabled: bool | None = None
    pos_table_count: int | None = None
    pos_customer_name_enabled: bool | None = None


class StoreRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    is_active: bool
    self_order_enabled: bool = False
    selforder_is_open: bool = True
    show_logo: bool = True
    receipt_header: str | None = None
    receipt_footer: str | None = None
    pos_dine_in_enabled: bool = False
    pos_table_enabled: bool = False
    pos_table_count: int = 10
    pos_customer_name_enabled: bool = False
    role: StoreRole | None = None

    model_config = {"from_attributes": True}


class MemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    store_id: uuid.UUID
    role: StoreRole
    is_active: bool
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None

    model_config = {"from_attributes": True}


class AddMemberIn(BaseModel):
    email: str
    role: StoreRole
    full_name: str | None = None
    phone: str | None = None


class UpdateMemberRoleIn(BaseModel):
    role: StoreRole
