import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.order import OrderStatus, PaymentMethod
from app.models.store import Store
from app.schemas.category import CategoryRead
from app.schemas.item import PublicItemRead
from app.schemas.order import (
    OrderCreate,
    OrderPreviewRequest,
    OrderPreviewResponse,
    OrderRead,
    SelfOrderCreate,
)
from app.services import item_service, order_service

router = APIRouter()


class StorePublicInfo(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    logo_url: str | None
    selforder_is_open: bool = True
    service_bp: int = 0
    pb1_bp: int = 0

    model_config = {"from_attributes": True}


class PublicMenuResponse(BaseModel):
    store: StorePublicInfo
    categories: list[CategoryRead]
    items: list[PublicItemRead]


async def _get_active_store(store_id: uuid.UUID, db: AsyncSession) -> Store:
    result = await db.execute(
        select(Store).where(Store.id == store_id, Store.is_active.is_(True))
    )
    store = result.scalar_one_or_none()
    if not store:
        raise NotFoundError("Store not found")
    if not store.self_order_enabled:
        raise NotFoundError("Self-order is not available for this store")
    return store


@router.get("/stores/{store_id}/menu", response_model=PublicMenuResponse)
async def get_public_menu(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    key = cache.menu_key(str(store_id))
    cached = await cache.get(key)
    if cached is not None:
        return cached

    store = await _get_active_store(store_id, db)
    categories, _ = await item_service.list_categories(store_id, db, limit=200)
    items, _ = await item_service.list_items(
        store_id, db, available_only=True, limit=500
    )
    response = PublicMenuResponse(
        store=StorePublicInfo.model_validate(store),
        categories=[CategoryRead.model_validate(c) for c in categories],
        items=[PublicItemRead.model_validate(i) for i in items],
    )
    await cache.set(key, response.model_dump(mode="json"), cache.MENU_TTL)
    return response


@router.post("/stores/{store_id}/orders/preview", response_model=OrderPreviewResponse)
async def preview_self_order(
    store_id: uuid.UUID,
    payload: OrderPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Totals (automatic discounts, service, PB1) for the customer's cart; promo codes are not accepted."""
    await _get_active_store(store_id, db)
    payload.discount_code = None
    return await order_service.preview_order(store_id, payload, db)


@router.post("/stores/{store_id}/orders", response_model=OrderRead, status_code=201)
async def create_self_order(
    store_id: uuid.UUID,
    payload: SelfOrderCreate,
    db: AsyncSession = Depends(get_db),
):
    store = await _get_active_store(store_id, db)
    if not store.selforder_is_open:
        raise HTTPException(status_code=503, detail="Store is not accepting self-orders right now")

    parts = []
    if payload.table_number:
        parts.append(f"Meja {payload.table_number}")
    if payload.notes:
        parts.append(payload.notes)
    combined_notes = " — ".join(parts) if parts else None

    order_payload = OrderCreate(
        payment_method=PaymentMethod.CASH,
        items=payload.items,
        notes=combined_notes,
        order_type="DINE_IN" if payload.table_number else None,
        table_number=payload.table_number,
    )
    order = await order_service.create_order(
        store_id=store_id,
        operator_id=None,
        payload=order_payload,
        db=db,
        initial_status=OrderStatus.PENDING,
    )
    return OrderRead.model_validate(order)
