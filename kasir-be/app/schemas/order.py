import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.order import OrderStatus, PaymentMethod


class CartItemIn(BaseModel):
    item_id: uuid.UUID | None = None
    package_id: uuid.UUID | None = None
    quantity: int = Field(ge=1)
    selected_option_choice_ids: list[uuid.UUID] = []
    selected_addon_choice_ids: list[uuid.UUID] = []

    @model_validator(mode="after")
    def item_xor_package(self) -> "CartItemIn":
        if bool(self.item_id) == bool(self.package_id):
            raise ValueError("Provide exactly one of item_id or package_id")
        return self


class OrderCreate(BaseModel):
    payment_method: PaymentMethod
    items: list[CartItemIn] = Field(min_length=1)
    discount_code: str | None = None
    notes: str | None = None
    order_type: Literal["DINE_IN", "TAKE_AWAY"] | None = None
    table_number: str | None = None
    customer_name: str | None = None


class SelfOrderCreate(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    table_number: str | None = None
    notes: str | None = None


class OrderItemRead(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID | None
    package_id: uuid.UUID | None
    item_name_snapshot: str
    unit_price_snapshot: int
    quantity: int
    addon_total_snapshot: int
    line_total: int
    options_snapshot: list | None
    addons_snapshot: list | None

    model_config = {"from_attributes": True}


class OrderRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    operator_id: uuid.UUID | None
    order_number: str
    status: OrderStatus
    payment_method: PaymentMethod
    subtotal: int
    discount_amount: int
    total_amount: int
    discount_code_snapshot: str | None
    notes: str | None
    order_type: str | None = None
    table_number: str | None = None
    customer_name: str | None = None
    created_at: datetime
    items: list[OrderItemRead] = []

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderPreviewRequest(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    discount_code: str | None = None


class OrderPreviewResponse(BaseModel):
    subtotal: int
    discount_amount: int
    total_amount: int
    valid: bool
    message: str
