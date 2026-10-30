import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class OrderChannel(str, enum.Enum):
    GOFOOD = "GOFOOD"
    GRABFOOD = "GRABFOOD"
    SHOPEEFOOD = "SHOPEEFOOD"


class ChannelSetting(Base, TimestampMixin):
    __tablename__ = "channel_settings"
    __table_args__ = (UniqueConstraint("store_id", "channel", name="uq_channel_store"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    commission_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    markup_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payout_lag_days: Mapped[int] = mapped_column(Integer, default=2, nullable=False)


class ItemChannelPrice(Base):
    """Manual price of an item on a platform; replaces the base price (markup is skipped)."""

    __tablename__ = "item_channel_prices"
    __table_args__ = (UniqueConstraint("item_id", "channel", name="uq_item_channel_price"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
