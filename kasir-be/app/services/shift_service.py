import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models import CashMovement, Expense, Order, OrderRefund, Shift, Store, User
from app.models.finance import EXPENSE_CATEGORIES, ExpenseSource, ExpenseStatus
from app.models.order import OrderStatus, PaymentMethod
from app.models.shift import CashMovementType, ShiftStatus
from app.schemas.shift import (
    CashMovementCreate,
    CashMovementRead,
    MethodTotal,
    ShiftClose,
    ShiftCurrent,
    ShiftDetail,
    ShiftRead,
    ShiftSummary,
)

COUNTED = (OrderStatus.CONFIRMED, OrderStatus.COMPLETED)


async def _cash_sales(store_id, start: datetime, end: datetime | None, db) -> int:
    q = select(func.coalesce(func.sum(Order.total_amount), 0)).where(
        Order.store_id == store_id,
        Order.payment_method == PaymentMethod.CASH,
        Order.status.in_(COUNTED),
        Order.confirmed_at >= start,
    )
    if end:
        q = q.where(Order.confirmed_at < end)
    return int((await db.execute(q)).scalar_one())


async def _movement_totals(shift_id, db) -> tuple[int, int]:
    rows = dict(
        (
            await db.execute(
                select(CashMovement.type, func.sum(CashMovement.amount))
                .where(CashMovement.shift_id == shift_id)
                .group_by(CashMovement.type)
            )
        ).all()
    )
    return int(rows.get(CashMovementType.IN.value) or 0), int(rows.get(CashMovementType.OUT.value) or 0)


async def _cash_refunds(shift: Shift, db) -> int:
    q = select(func.coalesce(func.sum(OrderRefund.amount), 0)).where(
        OrderRefund.store_id == shift.store_id,
        OrderRefund.method == "CASH",
        OrderRefund.refunded_at >= shift.opened_at,
    )
    if shift.closed_at:
        q = q.where(OrderRefund.refunded_at < shift.closed_at)
    return int((await db.execute(q)).scalar_one())


async def _shift_cash(shift: Shift, db) -> tuple[int, int, int, int, int]:
    """(cash_sales, cash_in, cash_out, expected, cash_refunds) for a shift's own window."""
    sales = await _cash_sales(shift.store_id, shift.opened_at, shift.closed_at, db)
    cin, cout = await _movement_totals(shift.id, db)
    refunds = await _cash_refunds(shift, db)
    return sales, cin, cout, shift.opening_cash + sales - refunds + cin - cout, refunds


async def _names(ids, db) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))
    return dict(rows.all())


async def _read(shift: Shift, db, names=None, expected: int | None = None) -> ShiftRead:
    names = names if names is not None else await _names([shift.opened_by, shift.closed_by], db)
    if shift.status == ShiftStatus.OPEN.value and expected is None:
        expected = (await _shift_cash(shift, db))[3]
    return ShiftRead(
        id=shift.id,
        status=shift.status,
        opened_by_name=names.get(shift.opened_by),
        opened_at=shift.opened_at,
        opening_cash=shift.opening_cash,
        carry_expected=shift.carry_expected,
        closed_by_name=names.get(shift.closed_by),
        closed_at=shift.closed_at,
        counted_cash=shift.counted_cash,
        expected_cash=shift.expected_cash if shift.status != ShiftStatus.OPEN.value else expected,
        variance=shift.variance,
        note=shift.note,
        review_note=shift.review_note,
    )


async def open_shift_of(store_id, db, lock: bool = False) -> Shift | None:
    q = select(Shift).where(Shift.store_id == store_id, Shift.status == ShiftStatus.OPEN.value)
    if lock:
        q = q.with_for_update()
    return (await db.execute(q)).scalars().first()


async def _last_closed(store_id, db) -> Shift | None:
    return (
        await db.execute(
            select(Shift)
            .where(Shift.store_id == store_id, Shift.closed_at.is_not(None))
            .order_by(Shift.closed_at.desc())
            .limit(1)
        )
    ).scalars().first()


async def _estimate(store_id, db) -> tuple[Shift | None, int | None]:
    last = await _last_closed(store_id, db)
    if not last:
        return None, None
    return last, last.counted_cash + await _cash_sales(store_id, last.closed_at, None, db)


async def current(store_id, db) -> ShiftCurrent:
    store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one()
    shift = await open_shift_of(store_id, db)
    last, estimate = await _estimate(store_id, db)
    base = dict(
        last_counted_cash=last.counted_cash if last else None,
        last_closed_at=last.closed_at if last else None,
        default_float=store.default_float,
        variance_threshold=store.shift_variance_threshold,
    )
    if not shift:
        return ShiftCurrent(shift=None, cash_sales=0, cash_refunds=0, cash_in=0, cash_out=0, cash_on_hand=estimate, **base)
    sales, cin, cout, expected, refunds = await _shift_cash(shift, db)
    return ShiftCurrent(
        shift=await _read(shift, db, expected=expected),
        cash_sales=sales,
        cash_refunds=refunds,
        cash_in=cin,
        cash_out=cout,
        cash_on_hand=expected,
        **base,
    )


async def open_shift(store_id, user_id, opening_cash: int, db) -> Shift:
    if await open_shift_of(store_id, db, lock=True):
        raise ConflictError("A shift is already open")
    _, estimate = await _estimate(store_id, db)
    shift = Shift(
        store_id=store_id,
        opened_by=user_id,
        opened_at=datetime.now(UTC),
        opening_cash=opening_cash,
        carry_expected=estimate,
        status=ShiftStatus.OPEN.value,
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    return shift


async def _get(store_id, shift_id, db, lock=False) -> Shift:
    q = select(Shift).where(Shift.id == shift_id, Shift.store_id == store_id)
    if lock:
        q = q.with_for_update()
    shift = (await db.execute(q)).scalar_one_or_none()
    if not shift:
        raise NotFoundError("Shift not found")
    return shift


async def close_shift(store_id, shift_id, user_id, payload: ShiftClose, db) -> Shift:
    shift = await _get(store_id, shift_id, db, lock=True)
    if shift.status != ShiftStatus.OPEN.value:
        raise BadRequestError("Shift is already closed")
    threshold = (
        await db.execute(select(Store.shift_variance_threshold).where(Store.id == store_id))
    ).scalar_one()
    now = datetime.now(UTC)
    shift.closed_at = now  # fix the window end before totalling
    expected = (await _shift_cash(shift, db))[3]
    variance = payload.counted - expected
    note = (payload.note or "").strip() or None
    if abs(variance) > threshold and not note:
        await db.rollback()
        raise BadRequestError("A note is required when the cash difference exceeds the limit")
    shift.closed_by = user_id
    shift.counted_cash = payload.counted
    shift.expected_cash = expected
    shift.variance = variance
    shift.note = note
    shift.status = ShiftStatus.CLOSED.value
    await db.commit()
    await db.refresh(shift)
    return shift


async def review_shift(store_id, shift_id, user_id, note: str | None, db) -> Shift:
    shift = await _get(store_id, shift_id, db, lock=True)
    if shift.status != ShiftStatus.CLOSED.value:
        raise BadRequestError("Only closed shifts awaiting review can be reviewed")
    shift.status = ShiftStatus.REVIEWED.value
    shift.reviewed_by = user_id
    shift.review_note = (note or "").strip() or None
    await db.commit()
    await db.refresh(shift)
    return shift


async def add_movement(store_id, shift_id, user_id, payload: CashMovementCreate, db) -> CashMovement:
    shift = await _get(store_id, shift_id, db, lock=True)
    if shift.status != ShiftStatus.OPEN.value:
        raise BadRequestError("Shift is closed")
    mv = CashMovement(
        shift_id=shift.id,
        user_id=user_id,
        type=payload.type.value,
        amount=payload.amount,
        category=payload.category.strip(),
        reason=payload.reason.strip(),
    )
    db.add(mv)
    if payload.type == CashMovementType.OUT and mv.category in EXPENSE_CATEGORIES:
        exp = Expense(
            store_id=store_id,
            user_id=user_id,
            date=date.today(),
            category=mv.category,
            description=mv.reason,
            amount=mv.amount,
            source=ExpenseSource.DRAWER.value,
            status=ExpenseStatus.POSTED.value,
        )
        db.add(exp)
        await db.flush()
        mv.expense_id = exp.id
    await db.commit()
    await db.refresh(mv)
    return mv


def _shift_conds(store_id, status, date_from, big_variance, threshold):
    conds = [Shift.store_id == store_id]
    if status:
        conds.append(Shift.status == status)
    if date_from:
        conds.append(func.date(Shift.opened_at) >= date_from)
    if big_variance:
        conds.append(Shift.status != ShiftStatus.OPEN.value)
        conds.append(func.abs(Shift.variance) > threshold)
    return conds


async def _threshold(store_id, db) -> int:
    return (await db.execute(select(Store.shift_variance_threshold).where(Store.id == store_id))).scalar_one()


async def list_shifts(store_id, db, status, date_from, big_variance, limit, offset):
    conds = _shift_conds(store_id, status, date_from, big_variance, await _threshold(store_id, db))
    total = (await db.execute(select(func.count()).select_from(Shift).where(*conds))).scalar_one()
    rows = (
        await db.execute(
            select(Shift).where(*conds).order_by(Shift.opened_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    names = await _names([x for s in rows for x in (s.opened_by, s.closed_by)], db)
    return [await _read(s, db, names) for s in rows], total


async def shift_summary(store_id, db, date_from) -> ShiftSummary:
    threshold = await _threshold(store_id, db)
    not_open = Shift.status != ShiftStatus.OPEN.value
    row = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(Shift.status == ShiftStatus.OPEN.value),
                func.count().filter(Shift.status == ShiftStatus.CLOSED.value),
                func.count().filter(not_open & (func.abs(Shift.variance) > threshold)),
                func.coalesce(func.sum(Shift.variance).filter(not_open), 0),
            )
            .select_from(Shift)
            .where(*_shift_conds(store_id, None, date_from, False, threshold))
        )
    ).one()
    return ShiftSummary(
        count=row[0], open_count=row[1], review_count=row[2], big_count=row[3], total_variance=int(row[4])
    )


async def detail(store_id, shift_id, db) -> ShiftDetail:
    shift = await _get(store_id, shift_id, db)
    sales, cin, cout, expected, refunds = await _shift_cash(shift, db)
    base = await _read(shift, db, expected=expected)
    non_cash_q = (
        select(Order.payment_method, func.sum(Order.total_amount), func.count())
        .where(
            Order.store_id == store_id,
            Order.payment_method != PaymentMethod.CASH,
            Order.status.in_(COUNTED),
            Order.confirmed_at >= shift.opened_at,
        )
        .group_by(Order.payment_method)
    )
    if shift.closed_at:
        non_cash_q = non_cash_q.where(Order.confirmed_at < shift.closed_at)
    non_cash = [
        MethodTotal(method=m.value if hasattr(m, "value") else m, total=int(t), count=c)
        for m, t, c in (await db.execute(non_cash_q)).all()
    ]
    mvs = (
        await db.execute(
            select(CashMovement).where(CashMovement.shift_id == shift.id).order_by(CashMovement.created_at)
        )
    ).scalars().all()
    names = await _names([m.user_id for m in mvs], db)
    return ShiftDetail(
        **base.model_dump(),
        cash_sales=sales,
        cash_refunds=refunds,
        cash_in=cin,
        cash_out=cout,
        non_cash=non_cash,
        movements=[
            CashMovementRead(
                id=m.id, type=m.type, amount=m.amount, category=m.category, reason=m.reason,
                created_at=m.created_at, user_name=names.get(m.user_id),
            )
            for m in mvs
        ],
    )
