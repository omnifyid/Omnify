import enum
import uuid

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class StoreRole(str, enum.Enum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    OPERATOR = "OPERATOR"


ROLE_RANK: dict[StoreRole, int] = {
    StoreRole.OWNER: 3,
    StoreRole.MANAGER: 2,
    StoreRole.OPERATOR: 1,
}


class StoreMembership(Base, TimestampMixin):
    __tablename__ = "store_memberships"
    __table_args__ = (UniqueConstraint("user_id", "store_id", name="uq_user_store"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[StoreRole] = mapped_column(SAEnum(StoreRole, name="store_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    store: Mapped["Store"] = relationship(back_populates="memberships")
