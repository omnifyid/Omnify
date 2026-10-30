import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class KitchenStatus(str, enum.Enum):
    NEW = "NEW"
    COOKING = "COOKING"
    READY = "READY"
    SERVED = "SERVED"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CARD = "CARD"
    QRIS = "QRIS"
    TRANSFER = "TRANSFER"
    PLATFORM = "PLATFORM"  # online food order; paid out by the platform


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    discount_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discounts.id", ondelete="SET NULL"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status"),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"), nullable=False
    )
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_code_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    table_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # null when the store has kitchen management off or the order is not yet confirmed
    kitchen_status: Mapped[KitchenStatus | None] = mapped_column(
        SAEnum(KitchenStatus, name="kitchen_status"), nullable=True, index=True
    )
    # online food platform (GOFOOD / GRABFOOD / SHOPEEFOOD); null for direct orders
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    channel_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    app_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_payout: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)  # included in total
    driver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # dine-in service charge, in total_amount
    pb1_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # restaurant tax added on top, in total_amount
    refunded_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_payout_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("platform_settlements.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # when the order became CONFIRMED/COMPLETED (payment collected); drives shift cash totals
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    store: Mapped["Store"] = relationship(back_populates="orders")
    operator: Mapped["User"] = relationship()
    discount: Mapped["Discount | None"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    refunds: Mapped[list["OrderRefund"]] = relationship(
        order_by="OrderRefund.refunded_at", lazy="selectin", cascade="all, delete-orphan"
    )
