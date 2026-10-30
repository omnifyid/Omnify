import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models import (
    AddonChoice,
    AddonGroup,
    Item,
    ItemCategory,
    ItemChannelPrice,
    OptionChoice,
    OptionGroup,
    OrderChannel,
)
from app.core.exceptions import BadRequestError
from app.schemas.item import AddonGroupCreate, ItemCreate, ItemUpdate, OptionGroupCreate


async def _load_item(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Item:
    result = await db.execute(
        select(Item)
        .options(
            selectinload(Item.option_groups).selectinload(OptionGroup.choices),
            selectinload(Item.addon_groups).selectinload(AddonGroup.choices),
        )
        .where(Item.id == item_id, Item.store_id == store_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("Item not found")
    return item


async def list_items(
    store_id: uuid.UUID,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    available_only: bool = False,
    is_available: bool | None = None,
    stock_out: bool = False,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Item], int]:
    base = select(Item).where(Item.store_id == store_id)
    if category_id:
        base = base.where(Item.category_id == category_id)
    if available_only:
        base = base.where(Item.is_available.is_(True))
        base = base.where((Item.stock.is_(None)) | (Item.stock > 0))
    if is_available is not None:
        base = base.where(Item.is_available.is_(is_available))
    if stock_out:
        base = base.where(Item.stock == 0)
    if search:
        base = base.where(Item.name.ilike(f"%{search.strip()}%"))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    q = (
        base.options(
            selectinload(Item.option_groups).selectinload(OptionGroup.choices),
            selectinload(Item.addon_groups).selectinload(AddonGroup.choices),
        )
        .order_by(Item.sort_order, Item.name)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_item(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Item:
    return await _load_item(item_id, store_id, db)


async def create_item(store_id: uuid.UUID, payload: ItemCreate, db: AsyncSession) -> Item:
    item = Item(
        store_id=store_id,
        name=payload.name,
        description=payload.description,
        base_price=payload.base_price,
        cost_price=payload.cost_price,
        category_id=payload.category_id,
        is_available=payload.is_available,
        sort_order=payload.sort_order,
        stock=payload.stock,
        icon=payload.icon,
    )
    db.add(item)
    await db.flush()
    for og_data in payload.option_groups:
        await _add_option_group(item.id, og_data, db)
    for ag_data in payload.addon_groups:
        await _add_addon_group(item.id, ag_data, db)
    await db.commit()
    return await _load_item(item.id, store_id, db)


async def update_item(
    item_id: uuid.UUID, store_id: uuid.UUID, payload: ItemUpdate, db: AsyncSession
) -> Item:
    item = await _load_item(item_id, store_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def set_item_image(
    item_id: uuid.UUID, store_id: uuid.UUID, image_url: str, db: AsyncSession
) -> Item:
    item = await _load_item(item_id, store_id, db)
    item.image_url = image_url
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def clear_item_image(
    item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession
) -> Item:
    item = await _load_item(item_id, store_id, db)
    item.image_url = None
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def update_stock(
    item_id: uuid.UUID, store_id: uuid.UUID, stock: int | None, db: AsyncSession
) -> Item:
    item = await _load_item(item_id, store_id, db)
    item.stock = stock
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def delete_item(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    item = await _load_item(item_id, store_id, db)
    item.is_available = False
    await db.commit()


async def replace_channel_prices(
    item_id: uuid.UUID, store_id: uuid.UUID, prices: dict[str, int | None], db: AsyncSession
) -> Item:
    item = await _load_item(item_id, store_id, db)
    valid = {c.value for c in OrderChannel}
    unknown = set(prices) - valid
    if unknown:
        raise BadRequestError(f"Unknown channel: {', '.join(sorted(unknown))}")
    if any(p is not None and p < 0 for p in prices.values()):
        raise BadRequestError("Price must be >= 0")
    await db.execute(delete(ItemChannelPrice).where(ItemChannelPrice.item_id == item_id))
    await db.flush()
    for ch, price in prices.items():
        if price:
            db.add(ItemChannelPrice(item_id=item_id, channel=ch, price=price))
    await db.commit()
    await db.refresh(item, ["channel_prices"])
    return item


async def replace_option_groups(
    item_id: uuid.UUID, store_id: uuid.UUID, groups: list[OptionGroupCreate], db: AsyncSession
) -> Item:
    await _load_item(item_id, store_id, db)
    await db.execute(delete(OptionGroup).where(OptionGroup.item_id == item_id))
    await db.flush()
    for og_data in groups:
        await _add_option_group(item_id, og_data, db)
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def replace_addon_groups(
    item_id: uuid.UUID, store_id: uuid.UUID, groups: list[AddonGroupCreate], db: AsyncSession
) -> Item:
    await _load_item(item_id, store_id, db)
    await db.execute(delete(AddonGroup).where(AddonGroup.item_id == item_id))
    await db.flush()
    for ag_data in groups:
        await _add_addon_group(item_id, ag_data, db)
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def _add_option_group(item_id: uuid.UUID, data: OptionGroupCreate, db: AsyncSession) -> None:
    og = OptionGroup(
        item_id=item_id, name=data.name, is_required=data.is_required, sort_order=data.sort_order
    )
    db.add(og)
    await db.flush()
    for c in data.choices:
        db.add(
            OptionChoice(
                group_id=og.id, label=c.label, is_default=c.is_default, sort_order=c.sort_order
            )
        )


async def _add_addon_group(item_id: uuid.UUID, data: AddonGroupCreate, db: AsyncSession) -> None:
    ag = AddonGroup(
        item_id=item_id,
        name=data.name,
        is_required=data.is_required,
        min_select=data.min_select,
        max_select=data.max_select,
        sort_order=data.sort_order,
    )
    db.add(ag)
    await db.flush()
    for c in data.choices:
        db.add(
            AddonChoice(
                group_id=ag.id,
                label=c.label,
                extra_price=c.extra_price,
                is_available=c.is_available,
                sort_order=c.sort_order,
            )
        )


# --- Category helpers ---


async def list_categories(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ItemCategory], int]:
    base = select(ItemCategory).where(ItemCategory.store_id == store_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    result = await db.execute(
        base.order_by(ItemCategory.sort_order, ItemCategory.name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def create_category(
    store_id: uuid.UUID, name: str, sort_order: int, db: AsyncSession, icon: str | None = None
) -> ItemCategory:
    cat = ItemCategory(store_id=store_id, name=name, icon=icon, sort_order=sort_order)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def update_category(
    cat_id: uuid.UUID, store_id: uuid.UUID, data: dict, db: AsyncSession
) -> ItemCategory:
    result = await db.execute(
        select(ItemCategory).where(ItemCategory.id == cat_id, ItemCategory.store_id == store_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundError("Category not found")
    for k, v in data.items():
        if v is not None:
            setattr(cat, k, v)
    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(cat_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(ItemCategory).where(ItemCategory.id == cat_id, ItemCategory.store_id == store_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundError("Category not found")
    await db.delete(cat)
    await db.commit()
