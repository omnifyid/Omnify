import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class DiscountType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class DiscountScope(str, enum.Enum):
    ORDER = "ORDER"
    ITEM = "ITEM"


class DiscountTarget(str, enum.Enum):
    ALL = "ALL"
    CATEGORY = "CATEGORY"
    ITEM = "ITEM"


class Discount(Base, TimestampMixin):
    __tablename__ = "discounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    discount_type: Mapped[DiscountType] = mapped_column(
        SAEnum(DiscountType, name="discount_type"), nullable=False
    )
    # PERCENTAGE: basis points (1000 = 10.00%). FIXED: rupiah integer.
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    min_order_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cap for PERCENTAGE discounts (rupiah); None = no cap
    max_discount_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scope: Mapped[DiscountScope] = mapped_column(
        SAEnum(DiscountScope, name="discount_scope"),
        nullable=False,
        default=DiscountScope.ORDER,
        server_default="ORDER",
    )
    # Only relevant when scope=ITEM
    target_type: Mapped[DiscountTarget | None] = mapped_column(
        SAEnum(DiscountTarget, name="discount_target"), nullable=True
    )
    target_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    target_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("item_categories.id", ondelete="SET NULL"), nullable=True
    )
    # If True, applied automatically without cashier entering a code
    is_automatic: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    store: Mapped["Store"] = relationship(back_populates="discounts")
