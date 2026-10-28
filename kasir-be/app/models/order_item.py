import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class OrderItem(Base):
    """
    All price and label fields are snapshots frozen at order creation time.
    Changing item prices later does not corrupt historical orders.
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("packages.id", ondelete="SET NULL"), nullable=True
    )
    item_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    addon_total_snapshot: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    item_discount_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    line_total: Mapped[int] = mapped_column(Integer, nullable=False)
    # [{"group": "Sugar Level", "label": "Less Sugar"}]
    options_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # [{"group": "Extras", "label": "Extra Shot", "extra_price": 5000}]
    addons_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
    item: Mapped["Item | None"] = relationship()
    package: Mapped["Package | None"] = relationship()
