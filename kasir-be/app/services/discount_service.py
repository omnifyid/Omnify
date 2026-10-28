import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Discount
from app.models.discount import DiscountScope, DiscountTarget, DiscountType
from app.schemas.discount import DiscountCreate, DiscountUpdate


async def list_discounts(
    store_id: uuid.UUID, db: AsyncSession, limit: int = 20, offset: int = 0
) -> tuple[list[Discount], int]:
    base = select(Discount).where(Discount.store_id == store_id)
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()
    result = await db.execute(base.offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def create_discount(
    store_id: uuid.UUID, payload: DiscountCreate, db: AsyncSession
) -> Discount:
    discount = Discount(
        store_id=store_id,
        name=payload.name,
        code=payload.code,
        discount_type=payload.discount_type,
        value=payload.value,
        min_order_amount=payload.min_order_amount,
        max_uses=payload.max_uses,
        is_active=payload.is_active,
        expires_at=payload.expires_at,
        max_discount_amount=payload.max_discount_amount,
        scope=payload.scope,
        target_type=payload.target_type,
        target_item_id=payload.target_item_id,
        target_category_id=payload.target_category_id,
        is_automatic=payload.is_automatic,
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


async def update_discount(
    discount_id: uuid.UUID, store_id: uuid.UUID, payload: DiscountUpdate, db: AsyncSession
) -> Discount:
    discount = await _get(discount_id, store_id, db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(discount, k, v)
    await db.commit()
    await db.refresh(discount)
    return discount


async def delete_discount(discount_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    discount = await _get(discount_id, store_id, db)
    await db.delete(discount)
    await db.commit()


async def list_automatic_item_discounts(store_id: uuid.UUID, db: AsyncSession) -> list[Discount]:
    """Returns active, non-expired automatic ITEM-scope discounts for a store."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(Discount).where(
            Discount.store_id == store_id,
            Discount.scope == DiscountScope.ITEM,
            Discount.is_automatic.is_(True),
            Discount.is_active.is_(True),
        )
    )
    discounts = list(result.scalars().all())
    return [
        d for d in discounts
        if not (d.expires_at and d.expires_at.replace(tzinfo=UTC) < now)
        and not (d.max_uses is not None and d.used_count >= d.max_uses)
    ]


def calc_line_discount(discount: Discount, line_subtotal: int) -> int:
    """Compute discount amount for a single line item (no DB access)."""
    if discount.discount_type == DiscountType.PERCENTAGE:
        amount = (line_subtotal * discount.value) // 10000
        if discount.max_discount_amount is not None:
            amount = min(amount, discount.max_discount_amount)
    else:
        amount = min(discount.value, line_subtotal)
    return amount


def line_matches_discount(
    discount: Discount, item_id: uuid.UUID | None, category_id: uuid.UUID | None
) -> bool:
    """Check whether a line item matches the discount's target."""
    if discount.target_type == DiscountTarget.ALL:
        return True
    if discount.target_type == DiscountTarget.ITEM:
        return item_id is not None and item_id == discount.target_item_id
    if discount.target_type == DiscountTarget.CATEGORY:
        return category_id is not None and category_id == discount.target_category_id
    return False


async def validate(
    code: str,
    store_id: uuid.UUID,
    cart_subtotal: int,
    db: AsyncSession,
    cart_items: list[dict] | None = None,
) -> tuple[bool, int, list[dict], str]:
    """Returns (valid, total_discount_amount, item_discounts, message).

    item_discounts is a list of {"item_id": uuid, "discount_amount": int}.
    For ORDER-scope discounts, item_discounts is always [].
    """
    result = await db.execute(
        select(Discount).where(
            Discount.store_id == store_id,
            Discount.code == code,
            Discount.is_active.is_(True),
        )
    )
    discount = result.scalar_one_or_none()
    if not discount:
        return False, 0, [], "Invalid promo code"
    if discount.expires_at and discount.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return False, 0, [], "Promo code has expired"
    if discount.max_uses is not None and discount.used_count >= discount.max_uses:
        return False, 0, [], "Promo code usage limit reached"
    if discount.min_order_amount and cart_subtotal < discount.min_order_amount:
        return False, 0, [], f"Minimum order amount is {discount.min_order_amount}"

    if discount.scope == DiscountScope.ITEM:
        item_discounts: list[dict] = []
        for ci in (cart_items or []):
            if not line_matches_discount(discount, ci.get("item_id"), ci.get("category_id")):
                continue
            d_amount = calc_line_discount(discount, ci["line_subtotal"])
            if d_amount > 0:
                item_discounts.append({"item_id": ci.get("item_id"), "discount_amount": d_amount})
        total = sum(d["discount_amount"] for d in item_discounts)
        return True, total, item_discounts, "Valid"

    # ORDER scope
    if discount.discount_type == DiscountType.PERCENTAGE:
        amount = (cart_subtotal * discount.value) // 10000
        if discount.max_discount_amount is not None:
            amount = min(amount, discount.max_discount_amount)
    else:
        amount = min(discount.value, cart_subtotal)

    return True, amount, [], "Valid"


async def _get(discount_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Discount:
    result = await db.execute(
        select(Discount).where(Discount.id == discount_id, Discount.store_id == store_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise NotFoundError("Discount not found")
    return d
