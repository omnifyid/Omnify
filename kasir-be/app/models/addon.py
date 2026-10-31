import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AddonGroup(Base):
    """Multi-select addons with individual extra prices. E.g. 'Extra Shots'."""

    __tablename__ = "addon_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_select: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_select: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    item: Mapped["Item"] = relationship(back_populates="addon_groups")
    choices: Mapped[list["AddonChoice"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class AddonChoice(Base):
    """A single selectable addon with an extra price delta (integer rupiah)."""

    __tablename__ = "addon_choices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("addon_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    extra_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # preselected at the cashier
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    group: Mapped["AddonGroup"] = relationship(back_populates="choices")
