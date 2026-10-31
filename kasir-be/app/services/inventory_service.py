import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.services.item_service import business_of, parent_store_id
from app.models import Ingredient, Item, Store, MovementType, OrderItem, RecipeLine, StockMovement
from app.schemas.inventory import (
    IngredientCreate,
    IngredientUpdate,
    MovementRead,
    OpnameIn,
    RecipeLineIn,
    RestockIn,
)


def _dec(v: float) -> Decimal:
    return Decimal(str(v))


async def _get_ingredient(
    ingredient_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession, lock: bool = False
) -> Ingredient:
    q = select(Ingredient).where(Ingredient.id == ingredient_id, Ingredient.store_id == store_id)
    if lock:
        q = q.with_for_update()
    ing = (await db.execute(q)).scalar_one_or_none()
    if not ing:
        raise NotFoundError("Ingredient not found")
    return ing


def _move(
    db: AsyncSession,
    ing: Ingredient,
    delta: Decimal,
    kind: MovementType,
    note: str | None = None,
    order_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    """Apply a signed stock delta to a (locked) ingredient and log it."""
    ing.stock = (ing.stock or Decimal(0)) + delta
    db.add(
        StockMovement(
            store_id=ing.store_id,
            ingredient_id=ing.id,
            order_id=order_id,
            user_id=user_id,
            type=kind.value,
            quantity=delta,
            balance_after=ing.stock,
            note=note,
        )
    )


async def list_ingredients(
    store_id: uuid.UUID,
    db: AsyncSession,
    search: str | None = None,
    low_stock: bool = False,
    level: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Ingredient], int]:
    cond = [Ingredient.store_id == store_id]
    if search:
        like = f"%{search}%"
        cond.append(Ingredient.name.ilike(like) | Ingredient.category.ilike(like))
    if low_stock:
        cond.append(Ingredient.stock <= Ingredient.min_stock)
    critical = (Ingredient.stock < Ingredient.min_stock / 2) | (Ingredient.stock < 0)
    if level == "critical":  # under half of min_stock
        cond.append(critical)
    elif level == "low":  # at or under min_stock, not yet critical
        cond.append((Ingredient.stock <= Ingredient.min_stock) & ~critical)
    total = (await db.execute(select(func.count()).select_from(Ingredient).where(*cond))).scalar_one()
    q = select(Ingredient).where(*cond).order_by(Ingredient.name).limit(limit).offset(offset)
    return list((await db.execute(q)).scalars().all()), total


async def ingredient_summary(store_id: uuid.UUID, db: AsyncSession) -> dict:
    count, low, value = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(Ingredient.stock <= Ingredient.min_stock),
                func.coalesce(
                    func.sum(func.greatest(Ingredient.stock, 0) * Ingredient.cost_price), 0
                ),
            ).where(Ingredient.store_id == store_id)
        )
    ).one()
    cats = (
        await db.execute(
            select(Ingredient.category)
            .where(Ingredient.store_id == store_id, Ingredient.category.is_not(None))
            .distinct()
            .order_by(Ingredient.category)
        )
    ).scalars().all()
    return {"count": count, "low_count": low, "stock_value": int(round(float(value))), "categories": list(cats)}


async def create_ingredient(
    store_id: uuid.UUID, payload: IngredientCreate, user_id: uuid.UUID, db: AsyncSession
) -> Ingredient:
    ing = Ingredient(
        store_id=store_id,
        name=payload.name.strip(),
        unit=payload.unit.strip(),
        category=(payload.category or "").strip() or None,
        min_stock=_dec(payload.min_stock),
        cost_price=payload.cost_price,
        stock=Decimal(0),
    )
    db.add(ing)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"Ingredient '{payload.name}' already exists")
    if payload.initial_stock > 0:
        _move(db, ing, _dec(payload.initial_stock), MovementType.INITIAL, "Initial stock", user_id=user_id)
    await db.commit()
    return ing


async def update_ingredient(
    ingredient_id: uuid.UUID, store_id: uuid.UUID, payload: IngredientUpdate, db: AsyncSession
) -> Ingredient:
    ing = await _get_ingredient(ingredient_id, store_id, db)
    data = payload.model_dump(exclude_unset=True)
    if "min_stock" in data:
        data["min_stock"] = _dec(data["min_stock"])
    if "category" in data:
        data["category"] = (data["category"] or "").strip() or None
    for k, v in data.items():
        if v is not None or k == "category":
            setattr(ing, k, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Ingredient name already exists")
    return ing


async def delete_ingredient(ingredient_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    ing = await _get_ingredient(ingredient_id, store_id, db)
    await db.delete(ing)
    await db.commit()


async def restock(
    ingredient_id: uuid.UUID, store_id: uuid.UUID, payload: RestockIn, user_id: uuid.UUID, db: AsyncSession
) -> Ingredient:
    ing = await _get_ingredient(ingredient_id, store_id, db, lock=True)
    if payload.cost_price is not None:
        ing.cost_price = payload.cost_price
    _move(db, ing, _dec(payload.quantity), MovementType.RESTOCK, payload.note, user_id=user_id)
    await db.commit()
    return ing


async def stock_opname(
    store_id: uuid.UUID, payload: OpnameIn, user_id: uuid.UUID, db: AsyncSession
) -> int:
    """Set stock to the physically counted value; each difference is logged as OPNAME."""
    counted = {l.ingredient_id: _dec(l.counted) for l in payload.lines}
    rows = (
        await db.execute(
            select(Ingredient)
            .where(Ingredient.store_id == store_id, Ingredient.id.in_(counted))
            .order_by(Ingredient.id)
            .with_for_update()
        )
    ).scalars().all()
    if len(rows) != len(counted):
        raise NotFoundError("Ingredient not found")
    adjusted = 0
    for ing in rows:
        delta = counted[ing.id] - ing.stock
        if delta != 0:
            _move(db, ing, delta, MovementType.OPNAME, "Stock opname", user_id=user_id)
            adjusted += 1
    await db.commit()
    return adjusted


async def list_movements(
    store_id: uuid.UUID,
    db: AsyncSession,
    ingredient_id: uuid.UUID | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MovementRead], int]:
    cond = [StockMovement.store_id == store_id]
    if ingredient_id:
        cond.append(StockMovement.ingredient_id == ingredient_id)
    if kind:
        cond.append(StockMovement.type == kind)
    total = (await db.execute(select(func.count()).select_from(StockMovement).where(*cond))).scalar_one()
    q = (
        select(StockMovement)
        .where(*cond)
        .order_by(StockMovement.created_at.desc(), StockMovement.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(q)).unique().scalars().all()
    return [
        MovementRead(
            id=m.id,
            ingredient_id=m.ingredient_id,
            ingredient_name=m.ingredient.name,
            unit=m.ingredient.unit,
            type=m.type,
            quantity=float(m.quantity),
            balance_after=float(m.balance_after),
            note=m.note,
            order_id=m.order_id,
            created_at=m.created_at,
        )
        for m in rows
    ], total


async def get_recipe(item_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> list[RecipeLine]:
    item = (
        await db.execute(select(Item.id).where(Item.id == item_id, Item.business_id == business_of(store_id)))
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Item not found")
    q = select(RecipeLine).where(RecipeLine.item_id == item_id).order_by(RecipeLine.id)
    return list((await db.execute(q)).unique().scalars().all())


async def set_recipe(
    item_id: uuid.UUID, store_id: uuid.UUID, lines: list[RecipeLineIn], db: AsyncSession
) -> list[RecipeLine]:
    await get_recipe(item_id, store_id, db)  # 404 check
    if store_id != await parent_store_id(store_id, db):
        raise BadRequestError("Recipe is managed by the parent store")
    ids = [l.ingredient_id for l in lines]
    if len(set(ids)) != len(ids):
        raise BadRequestError("Duplicate ingredient in recipe")
    if ids:
        found = (
            await db.execute(
                select(func.count()).select_from(Ingredient).where(
                    Ingredient.store_id == store_id, Ingredient.id.in_(ids)
                )
            )
        ).scalar_one()
        if found != len(ids):
            raise BadRequestError("Unknown ingredient in recipe")
    await db.execute(delete(RecipeLine).where(RecipeLine.item_id == item_id))
    for l in lines:
        db.add(RecipeLine(item_id=item_id, ingredient_id=l.ingredient_id, quantity=_dec(l.quantity)))
    await db.commit()
    return await get_recipe(item_id, store_id, db)


async def _need_for(store_id: uuid.UUID, qty_by_item: dict[uuid.UUID, int], db: AsyncSession) -> dict[uuid.UUID, Decimal]:
    """Ingredient quantities the given item quantities use (a branch uses the parent's recipe, matched by name)."""
    recipe = (
        await db.execute(select(RecipeLine).where(RecipeLine.item_id.in_(qty_by_item)))
    ).unique().scalars().all()
    need: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    if store_id == await parent_store_id(store_id, db):
        for r in recipe:
            need[r.ingredient_id] += r.quantity * qty_by_item[r.item_id]
    else:
        by_name: dict[str, Decimal] = defaultdict(Decimal)
        for r in recipe:
            by_name[r.ingredient.name.lower()] += r.quantity * qty_by_item[r.item_id]
        if by_name:
            own = (
                await db.execute(
                    select(Ingredient).where(
                        Ingredient.store_id == store_id, func.lower(Ingredient.name).in_(list(by_name))
                    )
                )
            ).scalars().all()
            for ing in own:
                need[ing.id] += by_name[ing.name.lower()]
    return need


async def deduct_for_order(
    store_id: uuid.UUID, order_id: uuid.UUID, order_number: str, lines: list[OrderItem], db: AsyncSession
) -> None:
    """Deduct recipe ingredients for a new order. Stock may go negative; sales are never blocked."""
    if not (await db.execute(select(Store.inventory_enabled).where(Store.id == store_id))).scalar_one():
        return  # inventory module is off for this store
    qty_by_item: dict[uuid.UUID, int] = defaultdict(int)
    for l in lines:
        if l.item_id:
            qty_by_item[l.item_id] += l.quantity
    if not qty_by_item:
        return
    need = await _need_for(store_id, qty_by_item, db)
    if not need:
        return
    ings = (
        await db.execute(
            select(Ingredient).where(Ingredient.id.in_(need)).order_by(Ingredient.id).with_for_update()
        )
    ).scalars().all()
    for ing in ings:
        _move(db, ing, -need[ing.id], MovementType.SALE, f"Order {order_number}", order_id=order_id)


async def restore_for_item(
    store_id: uuid.UUID, order_id: uuid.UUID, order_number: str, item_id: uuid.UUID | None, quantity: int, db: AsyncSession
) -> None:
    """Return the ingredients of `quantity` units of one item taken off an open bill."""
    if not item_id or not (await db.execute(select(Store.inventory_enabled).where(Store.id == store_id))).scalar_one():
        return
    need = await _need_for(store_id, {item_id: quantity}, db)
    if not need:
        return
    ings = (
        await db.execute(
            select(Ingredient).where(Ingredient.id.in_(need)).order_by(Ingredient.id).with_for_update()
        )
    ).scalars().all()
    for ing in ings:
        _move(db, ing, need[ing.id], MovementType.RETURN, f"Void {order_number}", order_id=order_id)


async def restore_for_order(
    store_id: uuid.UUID, order_id: uuid.UUID, order_number: str, db: AsyncSession
) -> None:
    """Return stock deducted for an order that is being cancelled. Safe to call twice."""
    moves = (
        await db.execute(
            select(StockMovement).where(
                StockMovement.order_id == order_id, StockMovement.store_id == store_id
            )
        )
    ).unique().scalars().all()
    # net of earlier partial returns (voided lines), so this is safe to call twice
    sold: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for m in moves:
        if m.type == MovementType.SALE.value:
            sold[m.ingredient_id] += -m.quantity
        elif m.type == MovementType.RETURN.value:
            sold[m.ingredient_id] -= m.quantity
    sold = {k: v for k, v in sold.items() if v > 0}
    if not sold:
        return
    ings = (
        await db.execute(
            select(Ingredient).where(Ingredient.id.in_(sold)).order_by(Ingredient.id).with_for_update()
        )
    ).scalars().all()
    for ing in ings:
        _move(db, ing, sold[ing.id], MovementType.RETURN, f"Cancelled {order_number}", order_id=order_id)
