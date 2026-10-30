import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OwnerOrManager
from app.database import get_db
from app.models import ExpenseSource, OrderChannel, StoreMembership
from app.schemas.common import PaginatedResponse
from app.schemas.finance import (
    BatchRead,
    ChannelOverview,
    ExpenseCreate,
    ExpenseRead,
    ExpenseSummary,
    ReceivableRead,
    ReceivableSelection,
    SettlementCreate,
    SettlementRead,
)
from app.services import finance_service

router = APIRouter()


@router.get("/{store_id}/expenses", response_model=PaginatedResponse[ExpenseRead])
async def list_expenses(
    store_id: uuid.UUID,
    category: str | None = None,
    source: ExpenseSource | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    src = source.value if source else None
    rows, total = await finance_service.list_expenses(
        store_id, db, category, src, date_from, date_to, limit, offset
    )
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/expenses/summary", response_model=ExpenseSummary)
async def expense_summary(
    store_id: uuid.UUID,
    category: str | None = None,
    source: ExpenseSource | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    src = source.value if source else None
    return await finance_service.expense_summary(store_id, db, category, src, date_from, date_to)


@router.post("/{store_id}/expenses", response_model=ExpenseRead, status_code=201)
async def create_expense(
    store_id: uuid.UUID,
    payload: ExpenseCreate,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await finance_service.create_expense(store_id, m.user_id, payload, db)


@router.post("/{store_id}/expenses/{expense_id}/confirm", response_model=ExpenseRead)
async def confirm_expense(
    store_id: uuid.UUID,
    expense_id: uuid.UUID,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await finance_service.confirm_expense(store_id, expense_id, m.user_id, db)


@router.delete("/{store_id}/expenses/{expense_id}", status_code=204)
async def delete_expense(
    store_id: uuid.UUID,
    expense_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    await finance_service.delete_expense(store_id, expense_id, db)


@router.get("/{store_id}/settlements/overview", response_model=list[ChannelOverview])
async def settlements_overview(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await finance_service.channel_overview(store_id, db)


@router.get("/{store_id}/settlements/batches", response_model=PaginatedResponse[BatchRead])
async def settlement_batches(
    store_id: uuid.UUID,
    channel: OrderChannel,
    limit: int = Query(10, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await finance_service.list_batches(store_id, channel, db, limit, offset)
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/settlements/receivables", response_model=PaginatedResponse[ReceivableRead])
async def settlement_receivables(
    store_id: uuid.UUID,
    channel: OrderChannel,
    up_to: date | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await finance_service.list_receivables(store_id, channel, up_to, db, limit, offset)
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{store_id}/settlements/receivables/selection", response_model=ReceivableSelection)
async def settlement_selection(
    store_id: uuid.UUID,
    channel: OrderChannel,
    up_to: date | None = None,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await finance_service.receivable_selection(store_id, channel, up_to, db)


@router.get("/{store_id}/settlements", response_model=PaginatedResponse[SettlementRead])
async def list_settlements(
    store_id: uuid.UUID,
    channel: OrderChannel | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await finance_service.list_settlements(store_id, channel, db, limit, offset)
    return PaginatedResponse(items=rows, total=total, limit=limit, offset=offset)


@router.post("/{store_id}/settlements", response_model=SettlementRead, status_code=201)
async def create_settlement(
    store_id: uuid.UUID,
    payload: SettlementCreate,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await finance_service.create_settlement(store_id, m.user_id, payload, db)
