import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember, OwnerOrManager
from app.database import get_db
from app.models import StoreMembership
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    IngredientCreate,
    IngredientRead,
    IngredientSummary,
    IngredientUpdate,
    MovementRead,
    OpnameIn,
    OpnameResult,
    RecipeLineRead,
    RecipeUpdate,
    RestockIn,
)
from app.services import inventory_service

router = APIRouter()


def _recipe_read(lines) -> list[RecipeLineRead]:
    return [
        RecipeLineRead(
            ingredient_id=l.ingredient_id,
            ingredient_name=l.ingredient.name,
            unit=l.ingredient.unit,
            quantity=float(l.quantity),
            cost_price=l.ingredient.cost_price,
        )
        for l in lines
    ]


@router.get("/{store_id}/ingredients", response_model=PaginatedResponse[IngredientRead])
async def list_ingredients(
    store_id: uuid.UUID,
    search: str | None = None,
    low_stock: bool = False,
    level: Literal["low", "critical"] | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    items, total = await inventory_service.list_ingredients(
        store_id, db, search, low_stock, level, limit, offset
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/ingredients/summary", response_model=IngredientSummary)
async def ingredient_summary(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_service.ingredient_summary(store_id, db)


@router.post("/{store_id}/ingredients", response_model=IngredientRead, status_code=201)
async def create_ingredient(
    store_id: uuid.UUID,
    payload: IngredientCreate,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_service.create_ingredient(store_id, payload, m.user_id, db)


@router.patch("/{store_id}/ingredients/{ingredient_id}", response_model=IngredientRead)
async def update_ingredient(
    store_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    payload: IngredientUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_service.update_ingredient(ingredient_id, store_id, payload, db)


@router.delete("/{store_id}/ingredients/{ingredient_id}", status_code=204)
async def delete_ingredient(
    store_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    await inventory_service.delete_ingredient(ingredient_id, store_id, db)


@router.post("/{store_id}/ingredients/{ingredient_id}/restock", response_model=IngredientRead)
async def restock_ingredient(
    store_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    payload: RestockIn,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_service.restock(ingredient_id, store_id, payload, m.user_id, db)


@router.post("/{store_id}/inventory/opname", response_model=OpnameResult)
async def stock_opname(
    store_id: uuid.UUID,
    payload: OpnameIn,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return OpnameResult(adjusted=await inventory_service.stock_opname(store_id, payload, m.user_id, db))


@router.get("/{store_id}/inventory/movements", response_model=PaginatedResponse[MovementRead])
async def list_movements(
    store_id: uuid.UUID,
    ingredient_id: uuid.UUID | None = None,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await inventory_service.list_movements(
        store_id, db, ingredient_id, type, limit, offset
    )
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/items/{item_id}/recipe", response_model=list[RecipeLineRead])
async def get_recipe(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return _recipe_read(await inventory_service.get_recipe(item_id, store_id, db))


@router.put("/{store_id}/items/{item_id}/recipe", response_model=list[RecipeLineRead])
async def set_recipe(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: RecipeUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return _recipe_read(await inventory_service.set_recipe(item_id, store_id, payload.lines, db))
