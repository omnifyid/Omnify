import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.finance import EXPENSE_CATEGORIES
from app.models.membership import StoreRole


class ReceiptOptions(BaseModel):
    """Paper width and which lines the customer receipt and kitchen ticket print."""

    paper: Literal["58", "80"] = "58"
    show_addr: bool = True
    show_phone: bool = True
    show_cashier: bool = True
    show_cust: bool = True
    show_no: bool = True
    show_mods: bool = True
    show_tax: bool = True
    show_pay: bool = True
    k_title: str = Field(default="Pesanan Baru", max_length=30)
    k_outlet: bool = True
    k_server: bool = True
    k_cust: bool = True


class MethodVariants(BaseModel):
    """A payment method with optional variants (EDC banks, QRIS providers)."""

    enabled: bool = True
    options: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("options")
    @classmethod
    def clean(cls, v: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for name in v:
            name = name.strip()[:40]
            if name:
                seen.setdefault(name.lower(), name)
        return list(seen.values())


class PaymentOptions(BaseModel):
    """Which methods the POS offers; EDC banks and QRIS providers the cashier picks from."""

    cash: bool = True
    edc: MethodVariants = MethodVariants()
    qris: MethodVariants = MethodVariants()
    transfer: bool = True


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
    is_open: bool | None = None
    show_logo: bool | None = None
    receipt_header: str | None = None
    receipt_footer: str | None = None
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=30)
    receipt_options: ReceiptOptions | None = None
    payment_options: PaymentOptions | None = None
    expense_categories: list[str] | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("expense_categories")
    @classmethod
    def clean_categories(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        seen: dict[str, str] = {}
        for name in v:
            name = name.strip()[:50]
            if name:
                seen.setdefault(name.lower(), name)
        if not seen:
            raise ValueError("At least one category is required")
        return list(seen.values())
    pos_dine_in_enabled: bool | None = None
    pos_table_enabled: bool | None = None
    pos_table_count: int | None = None
    pos_customer_name_enabled: bool | None = None
    kitchen_enabled: bool | None = None
    inventory_enabled: bool | None = None
    finance_enabled: bool | None = None
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
    is_open: bool = True
    show_logo: bool = True
    receipt_header: str | None = None
    receipt_footer: str | None = None
    address: str | None = None
    phone: str | None = None
    receipt_options: ReceiptOptions = ReceiptOptions()
    payment_options: PaymentOptions = PaymentOptions()
    expense_categories: list[str] = Field(default_factory=lambda: list(EXPENSE_CATEGORIES))
    pos_dine_in_enabled: bool = False
    pos_table_enabled: bool = False
    pos_table_count: int = 10
    pos_customer_name_enabled: bool = False
    kitchen_enabled: bool = False
    inventory_enabled: bool = True
    finance_enabled: bool = True
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

    @field_validator("expense_categories", mode="before")
    @classmethod
    def default_categories(cls, v):
        return v or list(EXPENSE_CATEGORIES)

    @field_validator("receipt_options", "payment_options", mode="before")
    @classmethod
    def default_options(cls, v):
        return v or {}

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
