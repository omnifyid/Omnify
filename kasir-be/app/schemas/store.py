import uuid

from pydantic import BaseModel, Field

from app.models.membership import StoreRole


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


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
    kitchen_enabled: bool | None = None
    tax_bp: int | None = Field(default=None, ge=0, le=10000)
    service_bp: int | None = Field(default=None, ge=0, le=10000)
    pb1_bp: int | None = Field(default=None, ge=0, le=10000)
    shift_variance_threshold: int | None = Field(default=None, ge=0)
    default_float: int | None = Field(default=None, ge=0)


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
    kitchen_enabled: bool = False
    tax_bp: int = 0
    service_bp: int = 0
    pb1_bp: int = 0
    shift_variance_threshold: int = 20000
    default_float: int = 0
    role: StoreRole | None = None
    # catalog ownership: the parent store owns products; branches follow it
    is_parent: bool = True
    has_branches: bool = False
    parent_store_name: str | None = None

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
