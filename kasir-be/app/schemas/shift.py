import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.shift import CashMovementType


class ShiftOpen(BaseModel):
    opening_cash: int = Field(ge=0)


class ShiftClose(BaseModel):
    counted: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=300)


class ShiftReview(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class CashMovementCreate(BaseModel):
    type: CashMovementType
    amount: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=1, max_length=200)


class CashMovementRead(BaseModel):
    id: uuid.UUID
    type: str
    amount: int
    category: str
    reason: str
    created_at: datetime
    user_name: str | None


class ShiftRead(BaseModel):
    id: uuid.UUID
    status: str
    opened_by_name: str | None
    opened_at: datetime
    opening_cash: int
    carry_expected: int | None
    closed_by_name: str | None
    closed_at: datetime | None
    counted_cash: int | None
    expected_cash: int | None  # live while open, snapshot once closed
    variance: int | None
    note: str | None
    review_note: str | None


class MethodTotal(BaseModel):
    method: str
    total: int
    count: int


class ShiftDetail(ShiftRead):
    cash_sales: int
    cash_refunds: int
    cash_in: int
    cash_out: int
    non_cash: list[MethodTotal]
    movements: list[CashMovementRead]


class ShiftCurrent(BaseModel):
    shift: ShiftRead | None
    cash_sales: int
    cash_refunds: int
    cash_in: int
    cash_out: int
    last_counted_cash: int | None
    last_closed_at: datetime | None
    # open shift: expected drawer cash now; otherwise last count + cash sales since
    cash_on_hand: int | None
    default_float: int
    variance_threshold: int


class ShiftSummary(BaseModel):
    count: int
    open_count: int
    review_count: int  # closed, awaiting review
    big_count: int  # |variance| above the store limit
    total_variance: int
