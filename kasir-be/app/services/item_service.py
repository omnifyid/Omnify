import uuid

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AddonChoice,
    AddonGroup,
    Item,
    ItemCategory,
    ItemChannelPrice,
    ItemStoreSetting,
    OptionChoice,
    OptionGroup,
    OrderChannel,
    Store,
)
from app.core.exceptions import BadRequestError
from app.schemas.item import AddonGroupCreate, ItemCreate, ItemUpdate, OptionGroupCreate


def business_of(store_id: uuid.UUID):
    """Scalar subquery: the business a store belongs to (catalog scope)."""
    return select(Store.business_id).where(Store.id == store_id).scalar_subquery()


async def parent_store_id(store_id: uuid.UUID, db: AsyncSession) -> uuid.UUID:
    """The business's first store; branches follow its recipes."""
    return (
        await db.execute(
            select(Store.id)
            .where(Store.business_id == business_of(store_id), Store.is_active.is_(True))
            .order_by(Store.created_at, Store.id)
            .limit(1)
        )
    ).scalar_one()


async def require_parent(store_id: uuid.UUID, db: AsyncSession) -> None:
    """Catalog (products, categories, modifiers) is edited in the parent store only."""
    if store_id != await parent_store_id(store_id, db):
        raise ForbiddenError("The catalog is managed by the parent store")


def not_hidden_in(store_id: uuid.UUID):
    """Condition: the item is not switched off for this store."""
    return ~exists().where(
        ItemStoreSetting.item_id == Item.id,
        ItemStoreSetting.store_id == store_id,
        ItemStoreSetting.is_sold.is_(False),
    )


async def attach_store_view(items: list[Item], store_id: uuid.UUID, db: AsyncSession) -> None:
    """Sets the per-store `price` and `is_sold` on each item (instance attrs, not persisted)."""
    if not items:
        return
    rows = (
        await db.execute(
            select(ItemStoreSetting).where(
                ItemStoreSetting.store_id == store_id,
                ItemStoreSetting.item_id.in_([i.id for i in items]),
            )
        )
    ).scalars()
    by_item = {r.item_id: r for r in rows}
    for it in items:
        r = by_item.get(it.id)
        it.price = (r.price if r and r.price else None) or it.base_price
        it.is_sold = r.is_sold if r else True


async def business_cache_keys(store_id: uuid.UUID, db: AsyncSession) -> list[str]:
    """Menu/items/categories cache keys of every branch sharing this store's catalog."""
    from app import cache

    ids = (await db.execute(select(Store.id).where(Store.business_id == business_of(store_id)))).scalars()
    keys: list[str] = []
    for sid in ids:
        keys += [cache.menu_key(str(sid)), cache.items_key(str(sid)), cache.cats_key(str(sid))]
    return keys


async def effective_price(item: Item, store_id: uuid.UUID, db: AsyncSession) -> int:
    await attach_store_view([item], store_id, db)
    return item.price


async def _load_item(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Item:
    result = await db.execute(
        select(Item)
        .options(
            selectinload(Item.option_groups).selectinload(OptionGroup.choices),
            selectinload(Item.addon_groups).selectinload(AddonGroup.choices),
        )
        .where(Item.id == item_id, Item.business_id == business_of(store_id))
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("Item not found")
    await attach_store_view([item], store_id, db)
    return item


async def list_items(
    store_id: uuid.UUID,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    available_only: bool = False,
    is_available: bool | None = None,
    stock_out: bool = False,
    is_sold: bool | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Item], int]:
    base = select(Item).where(Item.business_id == business_of(store_id))
    if is_sold is True:
        base = base.where(not_hidden_in(store_id))
    elif is_sold is False:
        base = base.where(~not_hidden_in(store_id))
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
    items = list(result.scalars().all())
    await attach_store_view(items, store_id, db)
    return items, total


async def _check_category(category_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    found = await db.execute(
        select(ItemCategory.id).where(
            ItemCategory.id == category_id, ItemCategory.business_id == business_of(store_id)
        )
    )
    if found.scalar_one_or_none() is None:
        raise BadRequestError("Category not found")


async def get_item(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Item:
    return await _load_item(item_id, store_id, db)


async def create_item(store_id: uuid.UUID, payload: ItemCreate, db: AsyncSession) -> Item:
    await require_parent(store_id, db)
    business_id = (await db.execute(select(Store.business_id).where(Store.id == store_id))).scalar_one()
    if payload.category_id:
        await _check_category(payload.category_id, store_id, db)
    item = Item(
        store_id=store_id,
        business_id=business_id,
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
    await require_parent(store_id, db)
    item = await _load_item(item_id, store_id, db)
    if payload.category_id:
        await _check_category(payload.category_id, store_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def set_item_image(
    item_id: uuid.UUID, store_id: uuid.UUID, image_url: str, db: AsyncSession
) -> Item:
    await require_parent(store_id, db)
    item = await _load_item(item_id, store_id, db)
    item.image_url = image_url
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def clear_item_image(
    item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession
) -> Item:
    await require_parent(store_id, db)
    item = await _load_item(item_id, store_id, db)
    item.image_url = None
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def update_stock(
    item_id: uuid.UUID, store_id: uuid.UUID, stock: int | None, db: AsyncSession
) -> Item:
    await require_parent(store_id, db)
    item = await _load_item(item_id, store_id, db)
    item.stock = stock
    await db.commit()
    return await _load_item(item_id, store_id, db)


async def delete_item(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    await require_parent(store_id, db)
    item = await _load_item(item_id, store_id, db)
    item.is_available = False
    await db.commit()


async def replace_channel_prices(
    item_id: uuid.UUID, store_id: uuid.UUID, prices: dict[str, int | None], db: AsyncSession
) -> Item:
    await require_parent(store_id, db)
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
    await require_parent(store_id, db)
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
    await require_parent(store_id, db)
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
    base = select(ItemCategory).where(ItemCategory.business_id == business_of(store_id))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    result = await db.execute(
        base.order_by(ItemCategory.sort_order, ItemCategory.name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def attach_category_stats(store_id: uuid.UUID, categories: list[ItemCategory], db: AsyncSession) -> None:
    """Sets item_count on each category (one grouped query)."""
    if not categories:
        return
    rows = (
        await db.execute(
            select(Item.category_id, func.count())
            .where(Item.business_id == business_of(store_id), Item.category_id.in_([c.id for c in categories]))
            .group_by(Item.category_id)
        )
    ).all()
    stats = {r[0]: r for r in rows}
    for c in categories:
        r = stats.get(c.id)
        c.item_count = r[1] if r else 0


async def create_category(
    store_id: uuid.UUID, name: str, sort_order: int, db: AsyncSession, icon: str | None = None
) -> ItemCategory:
    await require_parent(store_id, db)
    business_id = (await db.execute(select(Store.business_id).where(Store.id == store_id))).scalar_one()
    cat = ItemCategory(store_id=store_id, business_id=business_id, name=name, icon=icon, sort_order=sort_order)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def update_category(
    cat_id: uuid.UUID, store_id: uuid.UUID, data: dict, db: AsyncSession
) -> ItemCategory:
    await require_parent(store_id, db)
    result = await db.execute(
        select(ItemCategory).where(ItemCategory.id == cat_id, ItemCategory.business_id == business_of(store_id))
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
    await require_parent(store_id, db)
    result = await db.execute(
        select(ItemCategory).where(ItemCategory.id == cat_id, ItemCategory.business_id == business_of(store_id))
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundError("Category not found")
    await db.delete(cat)
    await db.commit()


# --- Per-branch settings ---


async def list_branch_settings(item_id: uuid.UUID, store_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """One row per branch of the item's business that the user can manage."""
    from app.models import StoreMembership, StoreRole

    await _load_item(item_id, store_id, db)
    stores = (
        await db.execute(
            select(Store)
            .join(StoreMembership, StoreMembership.store_id == Store.id)
            .where(
                Store.business_id == business_of(store_id),
                Store.is_active.is_(True),
                StoreMembership.user_id == user_id,
                StoreMembership.is_active.is_(True),
                StoreMembership.role.in_([StoreRole.OWNER, StoreRole.MANAGER]),
            )
            .order_by(Store.name)
        )
    ).scalars().all()
    rows = {
        r.store_id: r
        for r in (
            await db.execute(select(ItemStoreSetting).where(ItemStoreSetting.item_id == item_id))
        ).scalars()
    }
    parent_id = await parent_store_id(store_id, db)
    return [
        {
            "store_id": st.id,
            "store_name": st.name,
            "is_parent": st.id == parent_id,
            "is_sold": rows[st.id].is_sold if st.id in rows else True,
            "price": rows[st.id].price if st.id in rows else None,
        }
        for st in stores
    ]


async def replace_branch_settings(
    item_id: uuid.UUID, store_id: uuid.UUID, user_id: uuid.UUID, settings: list, db: AsyncSession
) -> list[dict]:
    allowed = {r["store_id"] for r in await list_branch_settings(item_id, store_id, user_id, db)}
    for entry in settings:
        if entry.store_id not in allowed:
            raise BadRequestError("Branch not found or not manageable")
        row = (
            await db.execute(
                select(ItemStoreSetting).where(
                    ItemStoreSetting.item_id == item_id, ItemStoreSetting.store_id == entry.store_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = ItemStoreSetting(item_id=item_id, store_id=entry.store_id)
            db.add(row)
        row.is_sold = entry.is_sold
        row.price = entry.price or None
    await db.commit()
    return await list_branch_settings(item_id, store_id, user_id, db)
