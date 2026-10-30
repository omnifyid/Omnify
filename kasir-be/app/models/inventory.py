import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class MovementType(str, enum.Enum):
    INITIAL = "INITIAL"
    RESTOCK = "RESTOCK"
    SALE = "SALE"
    RETURN = "RETURN"
    OPNAME = "OPNAME"
    ADJUST = "ADJUST"


class Ingredient(Base, TimestampMixin):
    __tablename__ = "ingredients"
    __table_args__ = (UniqueConstraint("store_id", "name", name="uq_ingredient_store_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    cost_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Rupiah per unit
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RecipeLine(Base):
    __tablename__ = "recipe_lines"
    __table_args__ = (UniqueConstraint("item_id", "ingredient_id", name="uq_recipe_item_ingredient"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)  # per 1 item sold

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")


class StockMovement(Base, TimestampMixin):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)  # signed delta
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
