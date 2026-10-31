import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.config import settings
from app.core.dependencies import AnyMember, OwnerOrManager, get_current_user
from app.core.exceptions import BadRequestError
from app.database import get_db
from app.models import StoreMembership, User
from app.schemas.common import PaginatedResponse
from app.schemas.item import (
    BranchSettingRead,
    BranchSettingsUpdate,
    ChannelPricesUpdate,
    AddonGroupCreate,
    ItemCreate,
    ItemRead,
    ItemUpdate,
    OptionGroupCreate,
    StockUpdate,
)
from app.services import item_service

router = APIRouter()


@router.get("/{store_id}/items", response_model=PaginatedResponse[ItemRead])
async def list_items(
    store_id: uuid.UUID,
    category_id: uuid.UUID | None = None,
    available_only: bool = False,
    is_available: bool | None = None,
    stock_out: bool = False,
    is_sold: bool | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    use_cache = (
        not search
        and is_available is None
        and not stock_out
        and is_sold is None
        and not category_id
        and not available_only
        and offset == 0
    )
    if use_cache:
        cached = await cache.get(cache.items_key(str(store_id)))
        if cached is not None:
            return {
                "items": cached["items"][:limit],
                "total": cached["total"],
                "limit": limit,
                "offset": 0,
            }

    items, total = await item_service.list_items(
        store_id, db, category_id, available_only, is_available, stock_out, is_sold, search, limit, offset
    )

    if use_cache and limit >= 500:
        await cache.set(
            cache.items_key(str(store_id)),
            {
                "items": [ItemRead.model_validate(i).model_dump(mode="json") for i in items],
                "total": total,
            },
            cache.MENU_TTL,
        )

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{store_id}/items", response_model=ItemRead, status_code=201)
async def create_item(
    store_id: uuid.UUID,
    payload: ItemCreate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.create_item(store_id, payload, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.get("/{store_id}/items/{item_id}", response_model=ItemRead)
async def get_item(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await item_service.get_item(item_id, store_id, db)


@router.patch("/{store_id}/items/{item_id}", response_model=ItemRead)
async def update_item(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ItemUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.update_item(item_id, store_id, payload, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.delete("/{store_id}/items/{item_id}", status_code=204)
async def delete_item(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    await item_service.delete_item(item_id, store_id, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))


@router.patch("/{store_id}/items/{item_id}/stock", response_model=ItemRead)
async def update_stock(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: StockUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.update_stock(item_id, store_id, payload.stock, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.put("/{store_id}/items/{item_id}/channel-prices", response_model=ItemRead)
async def replace_channel_prices(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ChannelPricesUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.replace_channel_prices(item_id, store_id, payload.prices, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.put("/{store_id}/items/{item_id}/option-groups", response_model=ItemRead)
async def replace_option_groups(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    groups: list[OptionGroupCreate],
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.replace_option_groups(item_id, store_id, groups, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.put("/{store_id}/items/{item_id}/addon-groups", response_model=ItemRead)
async def replace_addon_groups(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    groups: list[AddonGroupCreate],
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.replace_addon_groups(item_id, store_id, groups, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.post("/{store_id}/items/{item_id}/image", response_model=ItemRead)
async def upload_item_image(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    file: UploadFile,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/avif"):
        raise BadRequestError("Only JPEG, PNG, WebP, and AVIF images are allowed")
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    dest = Path(settings.media_dir) / f"item_{item_id}.{ext}"
    dest.write_bytes(await file.read())
    image_url = f"/media/item_{item_id}.{ext}"
    result = await item_service.set_item_image(item_id, store_id, image_url, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.delete("/{store_id}/items/{item_id}/image", response_model=ItemRead)
async def remove_item_image(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.clear_item_image(item_id, store_id, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result


@router.get("/{store_id}/items/{item_id}/branches", response_model=list[BranchSettingRead])
async def get_branch_settings(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await item_service.list_branch_settings(item_id, store_id, user.id, db)


@router.put("/{store_id}/items/{item_id}/branches", response_model=list[BranchSettingRead])
async def put_branch_settings(
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: BranchSettingsUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await item_service.replace_branch_settings(item_id, store_id, user.id, payload.branches, db)
    await cache.delete(*await item_service.business_cache_keys(store_id, db))
    return result
