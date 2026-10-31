import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    self_order_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    selforder_is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_logo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pos_dine_in_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pos_table_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pos_table_count: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    pos_customer_name_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kitchen_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    service_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # service charge on dine-in, basis points
    pb1_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # restaurant tax added to direct orders, basis points
    shift_variance_threshold: Mapped[int] = mapped_column(Integer, default=20000, nullable=False)
    default_float: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # tax included in online prices, basis points
    receipt_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_footer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # catalog role, set by store_service.attach_catalog_info (not columns)
    is_parent = True
    has_branches = False
    parent_store_name = None

    business: Mapped["Business"] = relationship(back_populates="stores")
    memberships: Mapped[list["StoreMembership"]] = relationship(back_populates="store")
    categories: Mapped[list["ItemCategory"]] = relationship(back_populates="store")
    items: Mapped[list["Item"]] = relationship(back_populates="store")
    packages: Mapped[list["Package"]] = relationship(back_populates="store")
    discounts: Mapped[list["Discount"]] = relationship(back_populates="store")
    orders: Mapped[list["Order"]] = relationship(back_populates="store")
