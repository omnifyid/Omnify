from calendar import monthrange
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models import (
    CashMovement,
    Expense,
    ExpenseStatus,
    Order,
    OrderChannel,
    PlatformSettlement,
)
from app.models.finance import ExpenseSource
from app.models.order import OrderStatus
from app.models.shift import CashMovementType
from app.schemas.finance import (
    BatchRead,
    ReceivableSelection,
    CategoryTotal,
    ChannelOverview,
    ExpenseCreate,
    ExpenseSummary,
    SettlementCreate,
)

COUNTED_STATUSES = (OrderStatus.CONFIRMED, OrderStatus.COMPLETED)


# ── Expenses ────────────────────────────────────────────────────────────────


def _same_day_next_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def _expense_filters(q, store_id, category, source, date_from, date_to):
    q = q.where(Expense.store_id == store_id)
    if category:
        q = q.where(Expense.category == category)
    if source:
        q = q.where(Expense.source == source)
    if date_from:
        q = q.where((Expense.status == ExpenseStatus.DRAFT.value) | (Expense.date >= date_from))
    if date_to:
        q = q.where(Expense.date <= date_to)
    return q


async def list_expenses(store_id, db, category, source, date_from, date_to, limit, offset):
    base = _expense_filters(select(Expense), store_id, category, source, date_from, date_to)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(
                (Expense.status == ExpenseStatus.POSTED.value), Expense.date.desc(), Expense.created_at.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def expense_summary(store_id, db, category, source, date_from, date_to) -> ExpenseSummary:
    base = _expense_filters(select(Expense), store_id, category, source, date_from, date_to).subquery()
    posted = base.c.status == ExpenseStatus.POSTED.value
    by_cat = (
        await db.execute(
            select(base.c.category, func.sum(base.c.amount))
            .where(posted)
            .group_by(base.c.category)
            .order_by(func.sum(base.c.amount).desc())
        )
    ).all()
    counts = (
        await db.execute(
            select(
                func.count().filter(posted),
                func.count().filter(~posted),
            ).select_from(base)
        )
    ).one()
    return ExpenseSummary(
        total=sum(int(t) for _, t in by_cat),
        posted_count=counts[0],
        draft_count=counts[1],
        by_category=[CategoryTotal(category=c, total=int(t)) for c, t in by_cat],
    )


async def _drawer_out(store_id, exp: Expense, user_id, db) -> None:
    """Paying from the drawer takes cash out of the open shift."""
    from app.services import shift_service

    shift = await shift_service.open_shift_of(store_id, db, lock=True)
    if not shift:
        raise BadRequestError("Paying from the cash drawer needs an open shift")
    if exp.date != date.today():
        raise BadRequestError("Drawer expenses must be dated today")
    await db.flush()
    db.add(
        CashMovement(
            shift_id=shift.id,
            user_id=user_id,
            type=CashMovementType.OUT.value,
            amount=exp.amount,
            category=exp.category,
            reason=exp.description,
            expense_id=exp.id,
        )
    )


async def create_expense(store_id, user_id, payload: ExpenseCreate, db) -> Expense:
    exp = Expense(
        store_id=store_id,
        user_id=user_id,
        date=payload.date,
        category=payload.category.strip(),
        description=payload.description.strip(),
        amount=payload.amount,
        source=payload.source.value,
        recurring=payload.recurring,
        status=ExpenseStatus.POSTED.value,
    )
    db.add(exp)
    if payload.source == ExpenseSource.DRAWER:
        await _drawer_out(store_id, exp, user_id, db)
    if payload.recurring:
        db.add(_next_draft(exp))
    await db.commit()
    await db.refresh(exp)
    return exp


def _next_draft(e: Expense) -> Expense:
    return Expense(
        store_id=e.store_id,
        user_id=e.user_id,
        date=_same_day_next_month(e.date),
        category=e.category,
        description=e.description,
        amount=e.amount,
        source=e.source,
        recurring=True,
        status=ExpenseStatus.DRAFT.value,
    )


async def _get_expense(store_id, expense_id, db) -> Expense:
    exp = (
        await db.execute(
            select(Expense).where(Expense.id == expense_id, Expense.store_id == store_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not exp:
        raise NotFoundError("Expense not found")
    return exp


async def confirm_expense(store_id, expense_id, user_id, db) -> Expense:
    exp = await _get_expense(store_id, expense_id, db)
    if exp.status != ExpenseStatus.DRAFT.value:
        raise BadRequestError("Only draft expenses can be confirmed")
    exp.status = ExpenseStatus.POSTED.value
    exp.user_id = user_id
    if exp.source == ExpenseSource.DRAWER.value:
        exp.date = date.today()
        await _drawer_out(store_id, exp, user_id, db)
    if exp.recurring:
        db.add(_next_draft(exp))
    await db.commit()
    await db.refresh(exp)
    return exp


async def delete_expense(store_id, expense_id, db) -> None:
    exp = await _get_expense(store_id, expense_id, db)
    if exp.status != ExpenseStatus.DRAFT.value:
        raise BadRequestError("Only draft expenses can be deleted")
    await db.delete(exp)
    await db.commit()


# ── Platform settlements ────────────────────────────────────────────────────


def _receivable_filter(store_id, channel: str | None = None):
    conds = [
        Order.store_id == store_id,
        Order.channel.is_not(None),
        Order.status.in_(COUNTED_STATUSES),
        Order.settlement_id.is_(None),
        Order.expected_payout.is_not(None),
    ]
    if channel:
        conds.append(Order.channel == channel)
    return conds


async def channel_overview(store_id, db) -> list[ChannelOverview]:
    today = date.today()
    month_start = today.replace(day=1)
    pending = (
        await db.execute(
            select(
                Order.channel,
                func.count(),
                func.coalesce(func.sum(Order.expected_payout), 0),
                func.coalesce(
                    func.sum(Order.expected_payout).filter(Order.expected_payout_date < today), 0
                ),
            )
            .where(*_receivable_filter(store_id))
            .group_by(Order.channel)
        )
    ).all()
    received = dict(
        (
            await db.execute(
                select(PlatformSettlement.channel, func.sum(PlatformSettlement.amount))
                .where(
                    PlatformSettlement.store_id == store_id,
                    PlatformSettlement.received_date >= month_start,
                )
                .group_by(PlatformSettlement.channel)
            )
        ).all()
    )
    commission = dict(
        (
            await db.execute(
                select(Order.channel, func.sum(Order.commission_amount))
                .where(
                    Order.store_id == store_id,
                    Order.channel.is_not(None),
                    Order.status.in_(COUNTED_STATUSES),
                    func.date(Order.created_at) >= month_start,
                )
                .group_by(Order.channel)
            )
        ).all()
    )
    by_ch = {r[0]: r for r in pending}
    out = []
    for ch in OrderChannel:
        p = by_ch.get(ch.value)
        out.append(
            ChannelOverview(
                channel=ch.value,
                outstanding=int(p[2]) if p else 0,
                outstanding_count=p[1] if p else 0,
                overdue=int(p[3]) if p else 0,
                received_month=int(received.get(ch.value) or 0),
                commission_month=int(commission.get(ch.value) or 0),
            )
        )
    return out


def _receivable_conds(store_id, channel: OrderChannel, up_to: date | None):
    conds = _receivable_filter(store_id, channel.value)
    if up_to:
        conds.append(Order.expected_payout_date <= up_to)
    return conds


async def list_batches(store_id, channel: OrderChannel, db, limit, offset):
    """Unsettled orders grouped by expected payout date, oldest first."""
    grouped = (
        select(
            Order.expected_payout_date.label("date"),
            func.count().label("order_count"),
            func.sum(Order.total_amount).label("gross"),
            func.sum(Order.expected_payout).label("expected"),
        )
        .where(*_receivable_conds(store_id, channel, None))
        .group_by(Order.expected_payout_date)
    )
    total = (await db.execute(select(func.count()).select_from(grouped.subquery()))).scalar_one()
    rows = (await db.execute(grouped.order_by("date").limit(limit).offset(offset))).all()
    return (
        [
            BatchRead(date=r.date, order_count=r.order_count, gross=int(r.gross), expected=int(r.expected))
            for r in rows
        ],
        total,
    )


async def list_receivables(store_id, channel: OrderChannel, up_to: date | None, db, limit, offset):
    conds = _receivable_conds(store_id, channel, up_to)
    total = (await db.execute(select(func.count()).select_from(Order).where(*conds))).scalar_one()
    rows = (
        await db.execute(
            select(Order)
            .where(*conds)
            .order_by(Order.expected_payout_date, Order.created_at)
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def receivable_selection(store_id, channel: OrderChannel, up_to: date | None, db) -> ReceivableSelection:
    conds = _receivable_conds(store_id, channel, up_to)
    ids = (await db.execute(select(Order.id).where(*conds))).scalars().all()
    expected = (
        await db.execute(select(func.coalesce(func.sum(Order.expected_payout), 0)).where(*conds))
    ).scalar_one()
    return ReceivableSelection(ids=list(ids), count=len(ids), expected=int(expected))


async def list_settlements(store_id, channel: OrderChannel | None, db, limit, offset):
    base = select(PlatformSettlement).where(PlatformSettlement.store_id == store_id)
    if channel:
        base = base.where(PlatformSettlement.channel == channel.value)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(PlatformSettlement.received_date.desc(), PlatformSettlement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def create_settlement(store_id, user_id, payload: SettlementCreate, db) -> PlatformSettlement:
    ids = list(dict.fromkeys(payload.order_ids))
    orders = (
        await db.execute(
            select(Order)
            .where(Order.id.in_(ids), *_receivable_filter(store_id, payload.channel.value))
            .order_by(Order.id)
            .with_for_update()
        )
    ).scalars().all()
    if len(orders) != len(ids):
        raise BadRequestError("Some orders are not awaiting payout from this platform")
    expected = sum(o.expected_payout for o in orders)
    diff = payload.amount - expected
    reason = (payload.reason or "").strip() or None
    if diff != 0 and not reason:
        raise BadRequestError("A reason is required when the amount differs from the expected payout")
    st = PlatformSettlement(
        store_id=store_id,
        user_id=user_id,
        channel=payload.channel.value,
        received_date=payload.received_date,
        amount=payload.amount,
        expected=expected,
        diff=diff,
        order_count=len(orders),
        reason=reason if diff else None,
    )
    db.add(st)
    await db.flush()
    for o in orders:
        o.settlement_id = st.id
    await db.commit()
    await db.refresh(st)
    return st
