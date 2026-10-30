import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.channel import OrderChannel
from app.models.finance import ExpenseSource


class ExpenseCreate(BaseModel):
    date: date
    category: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=200)
    amount: int = Field(gt=0)
    source: ExpenseSource
    recurring: bool = False


class ExpenseRead(BaseModel):
    id: uuid.UUID
    date: date
    category: str
    description: str
    amount: int
    source: str
    recurring: bool
    status: str

    model_config = {"from_attributes": True}


class CategoryTotal(BaseModel):
    category: str
    total: int


class ExpenseSummary(BaseModel):
    total: int  # posted only
    posted_count: int
    draft_count: int
    by_category: list[CategoryTotal]


class ChannelOverview(BaseModel):
    channel: str
    outstanding: int  # expected payout not yet received
    outstanding_count: int
    overdue: int
    received_month: int
    commission_month: int


class ReceivableRead(BaseModel):
    id: uuid.UUID
    order_number: str
    channel_order_id: str | None
    created_at: datetime
    total_amount: int
    expected_payout: int
    expected_payout_date: date

    model_config = {"from_attributes": True}


class SettlementCreate(BaseModel):
    channel: OrderChannel
    received_date: date
    amount: int = Field(gt=0)
    order_ids: list[uuid.UUID] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=200)


class SettlementRead(BaseModel):
    id: uuid.UUID
    channel: str
    received_date: date
    amount: int
    expected: int
    diff: int
    order_count: int
    reason: str | None

    model_config = {"from_attributes": True}


class BatchRead(BaseModel):
    date: date
    order_count: int
    gross: int
    expected: int


class ReceivableSelection(BaseModel):
    ids: list[uuid.UUID]
    count: int
    expected: int
