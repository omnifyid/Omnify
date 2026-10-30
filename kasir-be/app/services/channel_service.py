import uuid
from datetime import date

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelSetting, Order, OrderChannel
from app.models.order import OrderStatus
from app.schemas.channel import (
    ChannelReport,
    ChannelReportRow,
    ChannelSettingRead,
    ChannelSettingUpdate,
)

COUNTED_STATUSES = (OrderStatus.CONFIRMED, OrderStatus.COMPLETED)


def ceil_markup(amount: int, markup_bp: int) -> int:
    """Online price: amount * (1 + markup), rounded up to the next Rp500."""
    if amount <= 0 or markup_bp <= 0:
        return amount
    return -(-(amount * (10000 + markup_bp)) // (10000 * 500)) * 500


def included_tax(total: int, tax_bp: int) -> int:
    """Tax portion of a tax-inclusive total."""
    if tax_bp <= 0:
        return 0
    return total - (total * 10000 + (10000 + tax_bp) // 2) // (10000 + tax_bp)


async def list_settings(store_id: uuid.UUID, db: AsyncSession) -> list[ChannelSettingRead]:
    rows = (
        await db.execute(select(ChannelSetting).where(ChannelSetting.store_id == store_id))
    ).scalars().all()
    by_ch = {r.channel: r for r in rows}
    out = []
    for ch in OrderChannel:
        r = by_ch.get(ch.value)
        out.append(
            ChannelSettingRead(
                channel=ch.value,
                enabled=r.enabled if r else False,
                commission_bp=r.commission_bp if r else 0,
                markup_bp=r.markup_bp if r else 0,
                payout_lag_days=r.payout_lag_days if r else 2,
            )
        )
    return out


async def get_setting(store_id: uuid.UUID, channel: str, db: AsyncSession) -> ChannelSettingRead:
    return next(s for s in await list_settings(store_id, db) if s.channel == channel)


async def update_setting(
    store_id: uuid.UUID, channel: OrderChannel, payload: ChannelSettingUpdate, db: AsyncSession
) -> ChannelSettingRead:
    row = (
        await db.execute(
            select(ChannelSetting).where(
                ChannelSetting.store_id == store_id, ChannelSetting.channel == channel.value
            )
        )
    ).scalar_one_or_none()
    if not row:
        row = ChannelSetting(store_id=store_id, channel=channel.value)
        db.add(row)
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(row, k, v)
    await db.commit()
    return await get_setting(store_id, channel.value, db)


async def channel_report(
    store_id: uuid.UUID, db: AsyncSession, from_date: date | None, to_date: date | None
) -> ChannelReport:
    q = (
        select(
            Order.channel,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.commission_amount), 0),
            func.coalesce(func.sum(Order.expected_payout), 0),
            func.coalesce(func.sum(Order.tax_amount), 0),
        )
        .where(
            Order.store_id == store_id,
            Order.channel.is_not(None),
            Order.status.in_(COUNTED_STATUSES),
        )
        .group_by(Order.channel)
    )
    if from_date:
        q = q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        q = q.where(cast(Order.created_at, Date) <= to_date)
    found = {r[0]: r for r in (await db.execute(q)).all()}
    rows = []
    for ch in OrderChannel:
        r = found.get(ch.value)
        rows.append(
            ChannelReportRow(
                channel=ch.value,
                order_count=r[1] if r else 0,
                gross=int(r[2]) if r else 0,
                commission=int(r[3]) if r else 0,
                net=int(r[4]) if r else 0,
                tax=int(r[5]) if r else 0,
            )
        )
    return ChannelReport(
        rows=rows,
        total_orders=sum(r.order_count for r in rows),
        total_gross=sum(r.gross for r in rows),
        total_commission=sum(r.commission for r in rows),
        total_net=sum(r.net for r in rows),
    )
