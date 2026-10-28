import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.discount import DiscountScope, DiscountTarget, DiscountType


class DiscountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    discount_type: DiscountType
    # PERCENTAGE: basis points (1000 = 10.00%). FIXED: rupiah.
    value: int = Field(ge=1)
    min_order_amount: int | None = None
    max_uses: int | None = None
    is_active: bool = True
    expires_at: datetime | None = None
    # Cap for PERCENTAGE discounts; None = no cap
    max_discount_amount: int | None = None
    scope: DiscountScope = DiscountScope.ORDER
    target_type: DiscountTarget | None = None
    target_item_id: uuid.UUID | None = None
    target_category_id: uuid.UUID | None = None
    is_automatic: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "DiscountCreate":
        if not self.is_automatic and not (self.code and self.code.strip()):
            raise ValueError("code is required when is_automatic is False")
        if self.max_discount_amount is not None and self.discount_type != DiscountType.PERCENTAGE:
            raise ValueError("max_discount_amount is only valid for PERCENTAGE discounts")
        if self.scope == DiscountScope.ORDER and self.target_type is not None:
            raise ValueError("target_type must be None for ORDER scope discounts")
        if self.scope == DiscountScope.ITEM:
            if self.target_type == DiscountTarget.ITEM and self.target_item_id is None:
                raise ValueError("target_item_id required when target_type is ITEM")
            if self.target_type == DiscountTarget.CATEGORY and self.target_category_id is None:
                raise ValueError("target_category_id required when target_type is CATEGORY")
        return self


class DiscountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = None
    discount_type: DiscountType | None = None
    value: int | None = Field(default=None, ge=1)
    max_discount_amount: int | None = None
    scope: DiscountScope | None = None
    target_type: DiscountTarget | None = None
    target_item_id: uuid.UUID | None = None
    target_category_id: uuid.UUID | None = None
    is_automatic: bool | None = None
    min_order_amount: int | None = None
    max_uses: int | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class DiscountRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    code: str | None
    discount_type: DiscountType
    value: int
    min_order_amount: int | None
    max_uses: int | None
    used_count: int
    is_active: bool
    expires_at: datetime | None
    max_discount_amount: int | None
    scope: DiscountScope
    target_type: DiscountTarget | None
    target_item_id: uuid.UUID | None
    target_category_id: uuid.UUID | None
    is_automatic: bool

    model_config = {"from_attributes": True}


class CartItemIn(BaseModel):
    item_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    # (unit_price + addon_total) × quantity, before any item discount
    line_subtotal: int = Field(ge=0)


class ItemDiscountOut(BaseModel):
    item_id: uuid.UUID | None
    discount_amount: int


class ValidateDiscountIn(BaseModel):
    code: str
    cart_subtotal: int = Field(ge=0)
    # Provide for ITEM-scope discounts to get per-line breakdown
    cart_items: list[CartItemIn] = []


class ValidateDiscountOut(BaseModel):
    valid: bool
    discount_amount: int
    item_discounts: list[ItemDiscountOut] = []
    message: str
