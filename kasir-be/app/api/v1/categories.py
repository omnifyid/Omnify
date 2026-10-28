import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.core.dependencies import AnyMember, OwnerOrManager
from app.database import get_db
from app.models import StoreMembership
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.common import PaginatedResponse
from app.services import item_service

router = APIRouter()


def _all_cache_keys(store_id: uuid.UUID) -> tuple[str, str, str]:
    s = str(store_id)
    return cache.menu_key(s), cache.items_key(s), cache.cats_key(s)


@router.get("/{store_id}/categories", response_model=PaginatedResponse[CategoryRead])
async def list_categories(
    store_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    if offset == 0:
        cached = await cache.get(cache.cats_key(str(store_id)))
        if cached is not None:
            return {
                "items": cached["items"][:limit],
                "total": cached["total"],
                "limit": limit,
                "offset": 0,
            }

    categories, total = await item_service.list_categories(store_id, db, limit, offset)

    if offset == 0 and limit >= 50:
        await cache.set(
            cache.cats_key(str(store_id)),
            {
                "items": [
                    CategoryRead.model_validate(c).model_dump(mode="json") for c in categories
                ],
                "total": total,
            },
            cache.MENU_TTL,
        )

    return PaginatedResponse(items=categories, total=total, limit=limit, offset=offset)


@router.post("/{store_id}/categories", response_model=CategoryRead, status_code=201)
async def create_category(
    store_id: uuid.UUID,
    payload: CategoryCreate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.create_category(
        store_id, payload.name, payload.sort_order, db, payload.icon
    )
    await cache.delete(*_all_cache_keys(store_id))
    return result


@router.patch("/{store_id}/categories/{cat_id}", response_model=CategoryRead)
async def update_category(
    store_id: uuid.UUID,
    cat_id: uuid.UUID,
    payload: CategoryUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.update_category(
        cat_id, store_id, payload.model_dump(exclude_unset=True), db
    )
    await cache.delete(*_all_cache_keys(store_id))
    return result


@router.delete("/{store_id}/categories/{cat_id}", status_code=204)
async def delete_category(
    store_id: uuid.UUID,
    cat_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    await item_service.delete_category(cat_id, store_id, db)
    await cache.delete(*_all_cache_keys(store_id))
