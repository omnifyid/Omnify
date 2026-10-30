import uuid
from datetime import date

from sqlalchemy import Date, Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, ItemCategory, Order, OrderItem, User
from app.models.order import OrderStatus
from app.schemas.report import (
    DashboardReport,
    DashboardSales,
    MenuCategorySummary,
    MenuDashboardReport,
    MenuItemSummary,
    PaymentBreakdownItem,
    PaymentReport,
    SalesByDay,
    SalesReport,
    StaffReport,
    StaffStat,
    TopItem,
    TopItemsReport,
)

# Revenue per order: the total without PB1 (tax collected for the government), scaled down by refunds.
NET_SALE = cast(
    func.round(
        (Order.total_amount - Order.pb1_amount)
        * 1.0  # numeric first: the int4 product overflows for large orders
        * (Order.total_amount - Order.refunded_amount)
        / func.nullif(Order.total_amount, 0)
    ),
    Integer,
)

REPORTABLE_ORDER_STATUSES = (OrderStatus.CONFIRMED, OrderStatus.COMPLETED)


async def dashboard_report(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 10,
    from_date: date | None = None,
    to_date: date | None = None,
) -> DashboardReport:
    sales_q = select(
        func.count(Order.id).label("order_count"),
        func.sum(NET_SALE).label("total_revenue"),
    ).where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
    if from_date:
        sales_q = sales_q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        sales_q = sales_q.where(cast(Order.created_at, Date) <= to_date)

    sales_row = (await db.execute(sales_q)).one()
    order_count = sales_row.order_count or 0
    total_revenue = sales_row.total_revenue or 0

    top_items_q = (
        select(
            OrderItem.item_name_snapshot,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.line_total).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
        .group_by(OrderItem.item_name_snapshot)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    if from_date:
        top_items_q = top_items_q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        top_items_q = top_items_q.where(cast(Order.created_at, Date) <= to_date)

    payment_q = (
        select(
            Order.payment_method,
            func.count(Order.id).label("order_count"),
            func.sum(NET_SALE).label("total_revenue"),
        )
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
        .group_by(Order.payment_method)
        .order_by(func.sum(NET_SALE).desc())
    )
    if from_date:
        payment_q = payment_q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        payment_q = payment_q.where(cast(Order.created_at, Date) <= to_date)

    top_items_rows = (await db.execute(top_items_q)).all()
    payment_rows = (await db.execute(payment_q)).all()

    item_counts_row = (
        await db.execute(
            select(
                func.count(Item.id).label("total"),
                func.count(Item.id).filter(Item.is_available.is_(True)).label("available"),
            ).where(Item.store_id == store_id)
        )
    ).one()
    total_items = item_counts_row.total or 0
    available_items = item_counts_row.available or 0
    total_categories = (
        await db.execute(
            select(func.count(ItemCategory.id)).where(ItemCategory.store_id == store_id)
        )
    ).scalar_one()

    item_sales_base = (
        select(
            OrderItem.item_id,
            func.sum(OrderItem.quantity).label("quantity_sold"),
            func.sum(OrderItem.line_total).label("total_revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
    )
    if from_date:
        item_sales_base = item_sales_base.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        item_sales_base = item_sales_base.where(cast(Order.created_at, Date) <= to_date)
    item_sales_subq = item_sales_base.group_by(OrderItem.item_id).subquery()

    category_sales_base = (
        select(
            Item.category_id,
            func.sum(OrderItem.quantity).label("quantity_sold"),
            func.sum(OrderItem.line_total).label("total_revenue"),
        )
        .join(OrderItem, OrderItem.item_id == Item.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
    )
    if from_date:
        category_sales_base = category_sales_base.where(
            cast(Order.created_at, Date) >= from_date
        )
    if to_date:
        category_sales_base = category_sales_base.where(
            cast(Order.created_at, Date) <= to_date
        )
    category_sales_subq = category_sales_base.group_by(Item.category_id).subquery()

    menu_categories_q = (
        select(
            ItemCategory.name.label("category_name"),
            func.count(Item.id).label("item_count"),
            func.coalesce(category_sales_subq.c.quantity_sold, 0).label("quantity_sold"),
            func.coalesce(category_sales_subq.c.total_revenue, 0).label("total_revenue"),
        )
        .outerjoin(Item, Item.category_id == ItemCategory.id)
        .outerjoin(category_sales_subq, category_sales_subq.c.category_id == ItemCategory.id)
        .where(ItemCategory.store_id == store_id)
        .group_by(
            ItemCategory.id,
            ItemCategory.name,
            ItemCategory.sort_order,
            category_sales_subq.c.quantity_sold,
            category_sales_subq.c.total_revenue,
        )
        .order_by(ItemCategory.sort_order, ItemCategory.name)
    )
    menu_category_rows = (await db.execute(menu_categories_q)).all()

    menu_items_q = (
        select(
            Item.name.label("item_name"),
            Item.base_price,
            func.coalesce(item_sales_subq.c.quantity_sold, 0).label("quantity_sold"),
            func.coalesce(item_sales_subq.c.total_revenue, 0).label("total_revenue"),
        )
        .outerjoin(item_sales_subq, item_sales_subq.c.item_id == Item.id)
        .where(Item.store_id == store_id, Item.is_available.is_(True))
        .order_by(Item.sort_order, Item.name)
        .limit(limit)
    )
    menu_item_rows = (await db.execute(menu_items_q)).all()

    return DashboardReport(
        sales=DashboardSales(
            order_count=order_count,
            total_revenue=total_revenue,
            avg_order_value=round(total_revenue / order_count) if order_count else 0,
        ),
        top_items=[
            TopItem(
                item_name=r.item_name_snapshot,
                quantity_sold=r.qty or 0,
                total_revenue=r.revenue or 0,
            )
            for r in top_items_rows
        ],
        payments=[
            PaymentBreakdownItem(
                payment_method=r.payment_method.value,
                order_count=r.order_count,
                total_revenue=r.total_revenue or 0,
            )
            for r in payment_rows
        ],
        menu=MenuDashboardReport(
            total_items=total_items or 0,
            available_items=available_items or 0,
            total_categories=total_categories or 0,
            categories=[
                MenuCategorySummary(
                    category_name=r.category_name,
                    item_count=r.item_count or 0,
                    quantity_sold=r.quantity_sold or 0,
                    total_revenue=r.total_revenue or 0,
                )
                for r in menu_category_rows
            ],
            items=[
                MenuItemSummary(
                    item_name=r.item_name,
                    base_price=r.base_price,
                    quantity_sold=r.quantity_sold or 0,
                    total_revenue=r.total_revenue or 0,
                )
                for r in menu_item_rows
            ],
        ),
    )


async def sales_report(
    store_id: uuid.UUID,
    db: AsyncSession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> SalesReport:
    q = (
        select(
            cast(Order.created_at, Date).label("day"),
            func.count(Order.id).label("order_count"),
            func.sum(NET_SALE).label("total_revenue"),
        )
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
        .group_by(cast(Order.created_at, Date))
        .order_by(cast(Order.created_at, Date))
    )
    if from_date:
        q = q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        q = q.where(cast(Order.created_at, Date) <= to_date)

    rows = (await db.execute(q)).all()
    days = [
        SalesByDay(day=r.day, order_count=r.order_count, total_revenue=r.total_revenue or 0)
        for r in rows
    ]
    return SalesReport(
        days=days,
        total_orders=sum(d.order_count for d in days),
        total_revenue=sum(d.total_revenue for d in days),
    )


async def top_items_report(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 10,
    from_date: date | None = None,
    to_date: date | None = None,
) -> TopItemsReport:
    q = (
        select(
            OrderItem.item_name_snapshot,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.line_total).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
        .group_by(OrderItem.item_name_snapshot)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    if from_date:
        q = q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        q = q.where(cast(Order.created_at, Date) <= to_date)

    rows = (await db.execute(q)).all()
    items = [
        TopItem(
            item_name=r.item_name_snapshot,
            quantity_sold=r.qty or 0,
            total_revenue=r.revenue or 0,
        )
        for r in rows
    ]
    return TopItemsReport(items=items)


async def staff_report(
    store_id: uuid.UUID,
    db: AsyncSession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> StaffReport:
    q = (
        select(
            Order.operator_id,
            User.full_name,
            func.count(Order.id).label("order_count"),
            func.sum(NET_SALE).label("total_revenue"),
        )
        .join(User, User.id == Order.operator_id)
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
        .group_by(Order.operator_id, User.full_name)
        .order_by(func.sum(NET_SALE).desc())
    )
    if from_date:
        q = q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        q = q.where(cast(Order.created_at, Date) <= to_date)

    rows = (await db.execute(q)).all()
    staff = [
        StaffStat(
            operator_id=str(r.operator_id),
            full_name=r.full_name,
            order_count=r.order_count,
            total_revenue=r.total_revenue or 0,
        )
        for r in rows
    ]
    return StaffReport(staff=staff)


async def payment_report(
    store_id: uuid.UUID,
    db: AsyncSession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> PaymentReport:
    q = (
        select(
            Order.payment_method,
            func.count(Order.id).label("order_count"),
            func.sum(NET_SALE).label("total_revenue"),
        )
        .where(Order.store_id == store_id, Order.status.in_(REPORTABLE_ORDER_STATUSES))
        .group_by(Order.payment_method)
        .order_by(func.sum(NET_SALE).desc())
    )
    if from_date:
        q = q.where(cast(Order.created_at, Date) >= from_date)
    if to_date:
        q = q.where(cast(Order.created_at, Date) <= to_date)

    rows = (await db.execute(q)).all()
    breakdown = [
        PaymentBreakdownItem(
            payment_method=r.payment_method.value,
            order_count=r.order_count,
            total_revenue=r.total_revenue or 0,
        )
        for r in rows
    ]
    return PaymentReport(breakdown=breakdown)
