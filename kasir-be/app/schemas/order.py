import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.channel import OrderChannel
from app.models.order import KitchenStatus, OrderStatus, PaymentMethod
from app.models.refund import RefundMethod


class CartItemIn(BaseModel):
    item_id: uuid.UUID | None = None
    package_id: uuid.UUID | None = None
    quantity: int = Field(ge=1)
    selected_option_choice_ids: list[uuid.UUID] = []
    selected_addon_choice_ids: list[uuid.UUID] = []
    note: str | None = Field(default=None, max_length=200)  # custom note for this line

    @model_validator(mode="after")
    def item_xor_package(self) -> "CartItemIn":
        if bool(self.item_id) == bool(self.package_id):
            raise ValueError("Provide exactly one of item_id or package_id")
        return self


class OrderCreate(BaseModel):
    payment_method: PaymentMethod | None = None  # defaults to PLATFORM for online orders
    items: list[CartItemIn] = Field(min_length=1)
    discount_code: str | None = None
    notes: str | None = None
    order_type: Literal["DINE_IN", "TAKE_AWAY"] | None = None
    table_number: str | None = None
    customer_name: str | None = None
    guest_count: int | None = Field(default=None, ge=1, le=999)
    segment: str | None = Field(default=None, max_length=40)
    channel: OrderChannel | None = None
    channel_order_id: str | None = Field(default=None, max_length=50)
    app_total: int | None = Field(default=None, ge=0)
    driver_name: str | None = Field(default=None, max_length=100)
    payment_provider: str | None = Field(default=None, max_length=40)  # EDC bank / QRIS provider
    cash_received: int | None = Field(default=None, ge=0)  # cash handed over; must cover the total
    open_bill: bool = False  # save unpaid and send to the kitchen; paid later via POST /orders/{id}/pay

    @model_validator(mode="after")
    def check_channel(self) -> "OrderCreate":
        if self.channel:
            if self.open_bill:
                raise ValueError("Online platform orders cannot be open bills")
            if not (self.channel_order_id or "").strip():
                raise ValueError("channel_order_id is required for online orders")
            self.payment_method = PaymentMethod.PLATFORM
        elif self.open_bill:
            self.payment_method = self.payment_method or PaymentMethod.CASH  # placeholder until paid
        elif self.payment_method is None:
            raise ValueError("payment_method is required")
        return self


class OrderAddItems(BaseModel):
    """Extra lines for an open bill, plus optional changes to its table / guest details."""

    items: list[CartItemIn] = Field(min_length=1)
    table_number: str | None = None
    customer_name: str | None = None
    guest_count: int | None = Field(default=None, ge=1, le=999)
    segment: str | None = Field(default=None, max_length=40)


class OrderPay(BaseModel):
    payment_method: PaymentMethod
    payment_provider: str | None = Field(default=None, max_length=40)
    cash_received: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def not_platform(self) -> "OrderPay":
        if self.payment_method == PaymentMethod.PLATFORM:
            raise ValueError("PLATFORM is not a payment method for open bills")
        return self


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
    note: str | None = None
    added_at: datetime | None = None
    is_done: bool = False
    void_qty: int = 0

    model_config = {"from_attributes": True}


class RefundRead(BaseModel):
    id: uuid.UUID
    type: str
    method: str
    amount: int
    reason: str
    quantity: int | None
    order_item_id: uuid.UUID | None
    refunded_at: datetime

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
    guest_count: int | None = None
    segment: str | None = None
    kitchen_status: KitchenStatus | None = None
    channel: str | None = None
    channel_order_id: str | None = None
    app_total: int | None = None
    commission_amount: int | None = None
    expected_payout: int | None = None
    tax_amount: int | None = None
    expected_payout_date: date | None = None
    driver_name: str | None = None
    service_amount: int = 0
    pb1_amount: int = 0
    refunded_amount: int = 0
    cash_received: int | None = None
    payment_provider: str | None = None
    operator_name: str | None = None
    refunds: list[RefundRead] = []
    settlement_id: uuid.UUID | None = None
    created_at: datetime
    items: list[OrderItemRead] = []

    model_config = {"from_attributes": True}


class RefundCreate(BaseModel):
    amount: int = Field(gt=0)
    method: RefundMethod
    reason: str = Field(min_length=1, max_length=200)


class VoidCreate(BaseModel):
    quantity: int = Field(gt=0)
    method: RefundMethod | None = None  # not needed on an open bill
    reason: str = Field(min_length=1, max_length=200)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class KitchenStatusUpdate(BaseModel):
    kitchen_status: KitchenStatus


class KitchenItemUpdate(BaseModel):
    is_done: bool


class OrderPreviewRequest(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    discount_code: str | None = None
    order_type: Literal["DINE_IN", "TAKE_AWAY"] | None = None


class OrderPreviewResponse(BaseModel):
    subtotal: int
    discount_amount: int
    service_amount: int = 0
    pb1_amount: int = 0
    total_amount: int
    valid: bool
    message: str
