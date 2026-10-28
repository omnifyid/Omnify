import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember, OwnerOrManager, get_current_user
from app.database import get_db
from app.models import StoreMembership, User
from app.models.order import OrderStatus, PaymentMethod
from app.schemas.common import PaginatedResponse
from app.schemas.order import (
    OrderCreate,
    OrderPreviewRequest,
    OrderPreviewResponse,
    OrderRead,
    OrderStatusUpdate,
)
from app.services import order_service

router = APIRouter()


@router.post("/{store_id}/orders", response_model=OrderRead, status_code=201)
async def create_order(
    store_id: uuid.UUID,
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.create_order(store_id, current_user.id, payload, db)


@router.post("/{store_id}/orders/preview", response_model=OrderPreviewResponse)
async def preview_order(
    store_id: uuid.UUID,
    payload: OrderPreviewRequest,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.preview_order(store_id, payload, db)


@router.get("/{store_id}/orders", response_model=PaginatedResponse[OrderRead])
async def list_orders(
    store_id: uuid.UUID,
    status: OrderStatus | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    operator_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_service.list_orders(
        store_id, db, status, payment_method, date_from, date_to, operator_id, limit, offset
    )
    return PaginatedResponse(items=orders, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/orders/my", response_model=list[OrderRead])
async def my_orders(
    store_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    orders, _ = await order_service.list_orders(
        store_id, db, operator_id=current_user.id, limit=100, offset=0
    )
    return orders


@router.get("/{store_id}/orders/{order_id}", response_model=OrderRead)
async def get_order(
    store_id: uuid.UUID,
    order_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.get_order(order_id, store_id, db)


@router.patch("/{store_id}/orders/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    store_id: uuid.UUID,
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.update_order_status(order_id, store_id, payload.status, db)
