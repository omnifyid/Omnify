from pydantic import BaseModel, Field


class ChannelSettingRead(BaseModel):
    channel: str
    enabled: bool
    commission_bp: int
    markup_bp: int
    payout_lag_days: int


class ChannelSettingUpdate(BaseModel):
    enabled: bool | None = None
    commission_bp: int | None = Field(default=None, ge=0, le=10000)
    markup_bp: int | None = Field(default=None, ge=0, le=100000)
    payout_lag_days: int | None = Field(default=None, ge=0, le=60)


class ChannelReportRow(BaseModel):
    channel: str
    order_count: int
    gross: int  # sum of order totals (what customers paid, tax included)
    commission: int
    net: int  # gross - commission: what the platform owes the store
    tax: int  # tax portion already included in gross


class ChannelReport(BaseModel):
    rows: list[ChannelReportRow]
    total_orders: int
    total_gross: int
    total_commission: int
    total_net: int
