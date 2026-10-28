import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember, OwnerOrManager
from app.database import get_db
from app.models import StoreMembership
from app.schemas.common import PaginatedResponse
from app.schemas.discount import (
    DiscountCreate,
    DiscountRead,
    DiscountUpdate,
    ItemDiscountOut,
    ValidateDiscountIn,
    ValidateDiscountOut,
)
from app.services import discount_service

router = APIRouter()


@router.get("/{store_id}/discounts", response_model=PaginatedResponse[DiscountRead])
async def list_discounts(
    store_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    items, total = await discount_service.list_discounts(store_id, db, limit, offset)
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{store_id}/discounts", response_model=DiscountRead, status_code=201)
async def create_discount(
    store_id: uuid.UUID,
    payload: DiscountCreate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await discount_service.create_discount(store_id, payload, db)


@router.patch("/{store_id}/discounts/{discount_id}", response_model=DiscountRead)
async def update_discount(
    store_id: uuid.UUID,
    discount_id: uuid.UUID,
    payload: DiscountUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await discount_service.update_discount(discount_id, store_id, payload, db)


@router.delete("/{store_id}/discounts/{discount_id}", status_code=204)
async def delete_discount(
    store_id: uuid.UUID,
    discount_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    await discount_service.delete_discount(discount_id, store_id, db)


@router.post("/{store_id}/discounts/validate", response_model=ValidateDiscountOut)
async def validate_discount(
    store_id: uuid.UUID,
    payload: ValidateDiscountIn,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    cart_items = [ci.model_dump() for ci in payload.cart_items]
    valid, amount, raw_item_discounts, message = await discount_service.validate(
        payload.code, store_id, payload.cart_subtotal, db, cart_items=cart_items
    )
    item_discounts = [ItemDiscountOut(**d) for d in raw_item_discounts]
    return ValidateDiscountOut(
        valid=valid, discount_amount=amount, item_discounts=item_discounts, message=message
    )
