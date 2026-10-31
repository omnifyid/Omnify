import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Business(Base, TimestampMixin):
    """Owner of a shared catalog; each Store under it is a branch (outlet)."""

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    stores: Mapped[list["Store"]] = relationship(back_populates="business")
