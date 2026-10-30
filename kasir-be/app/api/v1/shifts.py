import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember, OwnerOrManager
from app.database import get_db
from app.models import StoreMembership
from app.models.shift import ShiftStatus
from app.schemas.common import PaginatedResponse
from app.schemas.shift import (
    CashMovementCreate,
    CashMovementRead,
    ShiftClose,
    ShiftCurrent,
    ShiftDetail,
    ShiftOpen,
    ShiftRead,
    ShiftReview,
    ShiftSummary,
)
from app.services import shift_service

router = APIRouter()


@router.get("/{store_id}/shifts/current", response_model=ShiftCurrent)
async def current_shift(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await shift_service.current(store_id, db)


@router.post("/{store_id}/shifts", response_model=ShiftRead, status_code=201)
async def open_shift(
    store_id: uuid.UUID,
    payload: ShiftOpen,
    m: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    shift = await shift_service.open_shift(store_id, m.user_id, payload.opening_cash, db)
    return await shift_service._read(shift, db)


@router.get("/{store_id}/shifts", response_model=PaginatedResponse[ShiftRead])
async def list_shifts(
    store_id: uuid.UUID,
    status: ShiftStatus | None = None,
    date_from: date | None = None,
    big_variance: bool = False,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await shift_service.list_shifts(
        store_id, db, status.value if status else None, date_from, big_variance, limit, offset
    )
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/shifts/summary", response_model=ShiftSummary)
async def shifts_summary(
    store_id: uuid.UUID,
    date_from: date | None = None,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await shift_service.shift_summary(store_id, db, date_from)


@router.get("/{store_id}/shifts/{shift_id}", response_model=ShiftDetail)
async def shift_detail(
    store_id: uuid.UUID,
    shift_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await shift_service.detail(store_id, shift_id, db)


@router.post("/{store_id}/shifts/{shift_id}/close", response_model=ShiftRead)
async def close_shift(
    store_id: uuid.UUID,
    shift_id: uuid.UUID,
    payload: ShiftClose,
    m: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    shift = await shift_service.close_shift(store_id, shift_id, m.user_id, payload, db)
    return await shift_service._read(shift, db)


@router.post("/{store_id}/shifts/{shift_id}/review", response_model=ShiftRead)
async def review_shift(
    store_id: uuid.UUID,
    shift_id: uuid.UUID,
    payload: ShiftReview,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    shift = await shift_service.review_shift(store_id, shift_id, m.user_id, payload.note, db)
    return await shift_service._read(shift, db)


@router.post("/{store_id}/shifts/{shift_id}/cash-movements", response_model=CashMovementRead, status_code=201)
async def add_cash_movement(
    store_id: uuid.UUID,
    shift_id: uuid.UUID,
    payload: CashMovementCreate,
    m: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    mv = await shift_service.add_movement(store_id, shift_id, m.user_id, payload, db)
    return CashMovementRead(
        id=mv.id, type=mv.type, amount=mv.amount, category=mv.category, reason=mv.reason,
        created_at=mv.created_at, user_name=None,
    )
