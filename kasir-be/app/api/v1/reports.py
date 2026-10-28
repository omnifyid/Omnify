import uuid
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember
from app.database import get_db
from app.models import StoreMembership
from app.schemas.report import (
    DashboardReport,
    PaymentReport,
    SalesReport,
    StaffReport,
    TopItemsReport,
)
from app.services import report_service

router = APIRouter()


@router.get("/{store_id}/reports/dashboard", response_model=DashboardReport)
async def dashboard_report(
    store_id: uuid.UUID,
    limit: int = 10,
    from_date: date | None = None,
    to_date: date | None = None,
    month: int | None = None,
    year: int | None = None,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    if month is not None or year is not None:
        if month is None or year is None:
            raise HTTPException(status_code=422, detail="Both month and year are required together")
        if not (1 <= month <= 12):
            raise HTTPException(status_code=422, detail="month must be between 1 and 12")
        from_date = date(year, month, 1)
        to_date = date(year, month, monthrange(year, month)[1])
    return await report_service.dashboard_report(store_id, db, limit, from_date, to_date)


@router.get("/{store_id}/reports/sales", response_model=SalesReport)
async def sales_report(
    store_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.sales_report(store_id, db, from_date, to_date)


@router.get("/{store_id}/reports/top-items", response_model=TopItemsReport)
async def top_items(
    store_id: uuid.UUID,
    limit: int = 10,
    from_date: date | None = None,
    to_date: date | None = None,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.top_items_report(store_id, db, limit, from_date, to_date)


@router.get("/{store_id}/reports/by-staff", response_model=StaffReport)
async def staff_report(
    store_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.staff_report(store_id, db, from_date, to_date)


@router.get("/{store_id}/reports/by-payment", response_model=PaymentReport)
async def payment_report(
    store_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.payment_report(store_id, db, from_date, to_date)
