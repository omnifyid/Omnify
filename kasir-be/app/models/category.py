import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.store import Store


class ItemCategory(Base, TimestampMixin):
    __tablename__ = "item_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    store: Mapped["Store"] = relationship(back_populates="categories")
    items: Mapped[list["Item"]] = relationship(back_populates="category")
