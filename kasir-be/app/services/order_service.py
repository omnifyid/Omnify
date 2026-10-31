import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models import (
    AddonChoice,
    Discount,
    Item,
    OptionChoice,
    Order,
    OrderItem,
    Package,
    Store,
)
from app.models.discount import DiscountScope, DiscountType
from app.models.order import KitchenStatus, OrderStatus, PaymentMethod
from app.models.refund import OrderRefund, RefundMethod, RefundType
from app.schemas.order import (
    CartItemIn,
    OrderCreate,
    OrderPreviewRequest,
    RefundCreate,
    VoidCreate,
)
from app.services import channel_service, discount_service, inventory_service, item_service


def direct_order_fees(net: int, dine_in: bool, service_bp: int, pb1_bp: int) -> tuple[int, int]:
    """Service charge (dine-in only) on the net amount, then PB1 on net + service; both rounded half up."""
    service = (net * service_bp + 5000) // 10000 if dine_in else 0
    pb1 = ((net + service) * pb1_bp + 5000) // 10000
    return service, pb1


async def _load_order(order_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Order:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.store_id == store_id)
        .execution_options(populate_existing=True)  # refunds/status changed in this session must show
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")
    return order


async def get_order(order_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Order:
    return await _load_order(order_id, store_id, db)


def _state_cond(state: str):
    """Display state of an order (pending / kitchen stage / completed ...) as a SQL condition."""
    in_kitchen = Order.kitchen_status.in_([KitchenStatus.NEW, KitchenStatus.COOKING])
    return {
        "verify": Order.status == OrderStatus.PENDING,
        "kitchen": (Order.status == OrderStatus.CONFIRMED) & in_kitchen,
        "ready": (Order.status == OrderStatus.CONFIRMED) & (Order.kitchen_status == KitchenStatus.READY),
        "confirmed": (Order.status == OrderStatus.CONFIRMED)
        & (Order.kitchen_status.is_(None) | (Order.kitchen_status == KitchenStatus.SERVED)),
        "done": Order.status == OrderStatus.COMPLETED,
        "cancelled": Order.status == OrderStatus.CANCELLED,
    }[state]


def _order_conds(
    store_id: uuid.UUID,
    status: OrderStatus | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    operator_id: uuid.UUID | None = None,
    search: str | None = None,
    kind: str | None = None,
    state: str | None = None,
) -> list:
    conds = [Order.store_id == store_id]
    if status:
        conds.append(Order.status == status)
    if payment_method:
        conds.append(Order.payment_method == payment_method)
    if date_from:
        conds.append(Order.created_at >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to:
        conds.append(
            Order.created_at
            < datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1)
        )
    if operator_id:
        conds.append(Order.operator_id == operator_id)
    if search and search.strip():
        like = f"%{search.strip()}%"
        conds.append(
            Order.order_number.ilike(like)
            | Order.channel_order_id.ilike(like)
            | Order.customer_name.ilike(like)
            | Order.notes.ilike(like)
        )
    if kind == "online":
        conds.append(Order.channel.is_not(None))
    elif kind == "dine":
        conds.append(Order.channel.is_(None) & (Order.order_type == "DINE_IN"))
    elif kind == "take":
        conds.append(Order.channel.is_(None) & (Order.order_type.is_(None) | (Order.order_type != "DINE_IN")))
    if state:
        conds.append(_state_cond(state))
    return conds


async def list_orders(
    store_id: uuid.UUID,
    db: AsyncSession,
    status: OrderStatus | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    operator_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    kind: str | None = None,
    state: str | None = None,
) -> tuple[list[Order], int]:
    conds = _order_conds(
        store_id, status, payment_method, date_from, date_to, operator_id, search, kind, state
    )
    total = (await db.execute(select(func.count()).select_from(Order).where(*conds))).scalar_one()
    q = (
        select(Order)
        .options(selectinload(Order.items))
        .where(*conds)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(q)).scalars().all()), total


async def create_order(
    store_id: uuid.UUID,
    operator_id: uuid.UUID | None,
    payload: OrderCreate,
    db: AsyncSession,
    initial_status: OrderStatus = OrderStatus.CONFIRMED,
) -> Order:
    """
    Atomic order creation.
    1. Validate all IDs and constraints
    2. Re-fetch all prices server-side
    3. Validate and lock discount (SELECT FOR UPDATE)
    4. Calculate totals with integer arithmetic
    5. Write Order + OrderItems in one transaction
    """
    async with db.begin_nested():  # savepoint; outer session commits
        line_results = []

        # Online platform orders: platform price markup, no discounts, commission + included tax
        channel = payload.channel.value if payload.channel else None
        markup_bp = 0
        commission_bp = 0
        payout_lag_days = 0
        channel_order_id = (payload.channel_order_id or "").strip().upper() or None
        if channel:
            setting = await channel_service.get_setting(store_id, channel, db)
            if not setting.enabled:
                raise BadRequestError(f"{channel} is not enabled for this store")
            markup_bp, commission_bp = setting.markup_bp, setting.commission_bp
            payout_lag_days = setting.payout_lag_days
            dup = (
                await db.execute(
                    select(Order.order_number).where(
                        Order.store_id == store_id,
                        Order.channel == channel,
                        func.upper(Order.channel_order_id) == channel_order_id,
                        Order.status != OrderStatus.CANCELLED,
                    )
                )
            ).first()
            if dup:
                raise ConflictError(f"Platform order ID already used by {dup[0]}")

        # Batch-fetch all option/addon choices upfront to avoid N+1 queries
        all_option_ids = [cid for ci in payload.items for cid in ci.selected_option_choice_ids]
        all_addon_ids = [cid for ci in payload.items for cid in ci.selected_addon_choice_ids]
        option_map: dict[uuid.UUID, OptionChoice] = {}
        addon_map: dict[uuid.UUID, AddonChoice] = {}
        if all_option_ids:
            oc_rows = (
                await db.execute(select(OptionChoice).where(OptionChoice.id.in_(all_option_ids)))
            ).scalars()
            option_map = {r.id: r for r in oc_rows}
        if all_addon_ids:
            ac_rows = (
                await db.execute(
                    select(AddonChoice).where(
                        AddonChoice.id.in_(all_addon_ids),
                        AddonChoice.is_available.is_(True),
                    )
                )
            ).scalars()
            addon_map = {r.id: r for r in ac_rows}

        for cart_item in payload.items:
            if cart_item.item_id:
                line = await _process_item_line(
                    store_id, cart_item, db, option_map, addon_map, markup_bp, channel
                )
            else:
                line = await _process_package_line(store_id, cart_item, db, addon_map, markup_bp)
            line_results.append(line)

        # --- Apply automatic ITEM-scope discounts ---
        # Lock each automatic discount to prevent race on used_count
        auto_discounts = (
            [] if channel else await discount_service.list_automatic_item_discounts(store_id, db)
        )
        applied_auto: list[Discount] = []
        for auto_d in auto_discounts:
            locked = (
                await db.execute(
                    select(Discount)
                    .where(Discount.id == auto_d.id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not locked:
                continue
            matched = False
            for line in line_results:
                item_id = line.get("item_id")
                category_id = line.get("category_id")
                if not discount_service.line_matches_discount(locked, item_id, category_id):
                    continue
                d_amount = discount_service.calc_line_discount(locked, line["line_total"])
                if d_amount > 0:
                    line["item_discount_amount"] += d_amount
                    line["line_total"] -= d_amount
                    matched = True
            if matched:
                applied_auto.append(locked)

        subtotal = sum(r["line_total"] for r in line_results)

        # --- Validate and lock code-based discount ---
        discount_obj: Discount | None = None
        discount_amount = 0
        discount_code_snapshot: str | None = None

        if payload.discount_code and not channel:
            result = await db.execute(
                select(Discount)
                .where(
                    Discount.store_id == store_id,
                    Discount.code == payload.discount_code,
                    Discount.is_active.is_(True),
                )
                .with_for_update()  # prevents race on used_count
            )
            discount_obj = result.scalar_one_or_none()
            if not discount_obj:
                raise BadRequestError("Invalid promo code")
            now = datetime.now(UTC)
            if discount_obj.expires_at and discount_obj.expires_at.replace(tzinfo=UTC) < now:
                raise BadRequestError("Promo code has expired")
            if (
                discount_obj.max_uses is not None
                and discount_obj.used_count >= discount_obj.max_uses
            ):
                raise BadRequestError("Promo code usage limit reached")
            if discount_obj.min_order_amount and subtotal < discount_obj.min_order_amount:
                raise BadRequestError(f"Minimum order amount is {discount_obj.min_order_amount}")

            if discount_obj.scope == DiscountScope.ITEM:
                # Apply item-level discount per matching line
                for line in line_results:
                    if not discount_service.line_matches_discount(
                        discount_obj, line.get("item_id"), line.get("category_id")
                    ):
                        continue
                    d_amount = discount_service.calc_line_discount(discount_obj, line["line_total"])
                    if d_amount > 0:
                        line["item_discount_amount"] += d_amount
                        line["line_total"] -= d_amount
                        discount_amount += d_amount
                subtotal = sum(r["line_total"] for r in line_results)
            else:
                # ORDER scope — apply to full subtotal
                if discount_obj.discount_type == DiscountType.PERCENTAGE:
                    discount_amount = (subtotal * discount_obj.value) // 10000
                    if discount_obj.max_discount_amount is not None:
                        discount_amount = min(discount_amount, discount_obj.max_discount_amount)
                else:
                    discount_amount = min(discount_obj.value, subtotal)

            discount_code_snapshot = discount_obj.code

        total_amount = subtotal - discount_amount

        # Generate order number
        today = date.today()
        today_str = today.strftime("%Y%m%d")
        day_start = datetime(today.year, today.month, today.day)
        count_result = await db.execute(
            select(func.count())
            .select_from(Order)
            .where(
                Order.store_id == store_id,
                Order.created_at >= day_start,
                Order.created_at < day_start + timedelta(days=1),
            )
        )
        daily_count = count_result.scalar_one() + 1
        order_number = f"ORD-{today_str}-{daily_count:05d}"

        kitchen_enabled, tax_bp, service_bp, pb1_bp = (
            await db.execute(
                select(Store.kitchen_enabled, Store.tax_bp, Store.service_bp, Store.pb1_bp).where(
                    Store.id == store_id
                )
            )
        ).one()

        service_amount = pb1_amount = 0
        if not channel:
            service_amount, pb1_amount = direct_order_fees(
                total_amount, getattr(payload, "order_type", None) == "DINE_IN", service_bp, pb1_bp
            )
            total_amount += service_amount + pb1_amount

        commission_amount = expected_payout = tax_amount = None
        if channel:
            commission_amount = (total_amount * commission_bp + 5000) // 10000
            expected_payout = total_amount - commission_amount
            tax_amount = channel_service.included_tax(total_amount, tax_bp)

        # Write Order
        order = Order(
            store_id=store_id,
            operator_id=operator_id,
            order_number=order_number,
            payment_method=payload.payment_method,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total_amount=total_amount,
            service_amount=service_amount,
            pb1_amount=pb1_amount,
            discount_id=discount_obj.id if discount_obj else None,
            discount_code_snapshot=discount_code_snapshot,
            notes=payload.notes,
            order_type=getattr(payload, "order_type", None),
            table_number=getattr(payload, "table_number", None),
            customer_name=getattr(payload, "customer_name", None),
            status=initial_status,
            channel=channel,
            channel_order_id=channel_order_id,
            app_total=payload.app_total if channel else None,
            commission_amount=commission_amount,
            expected_payout=expected_payout,
            tax_amount=tax_amount,
            driver_name=(payload.driver_name or "").strip() or None if channel else None,
            confirmed_at=(
                datetime.now(UTC) if initial_status == OrderStatus.CONFIRMED else None
            ),
            expected_payout_date=(
                date.today() + timedelta(days=payout_lag_days) if channel else None
            ),
            kitchen_status=(
                KitchenStatus.NEW
                if kitchen_enabled and initial_status == OrderStatus.CONFIRMED
                else None
            ),
        )
        db.add(order)
        await db.flush()

        order_items: list[OrderItem] = []
        for line in line_results:
            order_items.append(
                OrderItem(
                    order_id=order.id,
                    item_id=line.get("item_id"),
                    package_id=line.get("package_id"),
                    item_name_snapshot=line["name"],
                    unit_price_snapshot=line["unit_price"],
                    quantity=line["quantity"],
                    addon_total_snapshot=line["addon_total"],
                    item_discount_amount=line.get("item_discount_amount", 0),
                    line_total=line["line_total"],
                    options_snapshot=line.get("options_snapshot"),
                    addons_snapshot=line.get("addons_snapshot"),
                )
            )
        db.add_all(order_items)
        await db.flush()
        await inventory_service.deduct_for_order(
            store_id, order.id, order.order_number, order_items, db
        )

        for line in line_results:
            if line.get("_stock_item") is not None:
                line["_stock_item"].stock -= line["quantity"]

        if discount_obj:
            discount_obj.used_count += 1
        for auto_d in applied_auto:
            auto_d.used_count += 1

    await db.commit()
    return await _load_order(order.id, store_id, db)


async def _process_item_line(
    store_id: uuid.UUID,
    cart_item: CartItemIn,
    db: AsyncSession,
    option_map: dict[uuid.UUID, OptionChoice],
    addon_map: dict[uuid.UUID, AddonChoice],
    markup_bp: int = 0,
    channel: str | None = None,
) -> dict:
    result = await db.execute(
        select(Item)
        .where(
            Item.id == cart_item.item_id,
            Item.business_id == item_service.business_of(store_id),
            item_service.not_hidden_in(store_id),
            Item.is_available.is_(True),
        )
        .with_for_update()
    )
    item = result.scalar_one_or_none()
    if not item:
        raise BadRequestError(f"Item {cart_item.item_id} not found or unavailable")

    if item.stock is not None:
        if item.stock == 0:
            raise BadRequestError(f"Item '{item.name}' is out of stock")
        if item.stock < cart_item.quantity:
            raise BadRequestError(
                f"Item '{item.name}' only has {item.stock} unit(s) in stock"
            )

    options_snapshot = []
    addons_snapshot = []
    addon_total = 0

    for choice_id in cart_item.selected_option_choice_ids:
        oc = option_map.get(choice_id)
        if not oc:
            raise BadRequestError(f"Option choice {choice_id} not found")
        options_snapshot.append({"label": oc.label, "group_id": str(oc.group_id)})

    for choice_id in cart_item.selected_addon_choice_ids:
        ac = addon_map.get(choice_id)
        if not ac:
            raise BadRequestError(f"Addon choice {choice_id} not found or unavailable")
        extra = channel_service.ceil_markup(ac.extra_price, markup_bp)
        addon_total += extra
        addons_snapshot.append({"label": ac.label, "extra_price": extra, "group_id": str(ac.group_id)})

    # a manual platform price replaces the base price; markup then only applies to add-ons
    manual = next((p.price for p in item.channel_prices if p.channel == channel), None) if channel else None
    unit_price = manual or channel_service.ceil_markup(await item_service.effective_price(item, store_id, db), markup_bp)
    line_total = (unit_price + addon_total) * cart_item.quantity

    return {
        "item_id": item.id,
        "category_id": item.category_id,
        "package_id": None,
        "name": item.name,
        "unit_price": unit_price,
        "quantity": cart_item.quantity,
        "addon_total": addon_total,
        "line_total": line_total,
        "item_discount_amount": 0,
        "options_snapshot": options_snapshot or None,
        "addons_snapshot": addons_snapshot or None,
        "_stock_item": item if item.stock is not None else None,
    }


async def _process_package_line(
    store_id: uuid.UUID,
    cart_item: CartItemIn,
    db: AsyncSession,
    addon_map: dict[uuid.UUID, AddonChoice],
    markup_bp: int = 0,
) -> dict:
    result = await db.execute(
        select(Package).where(
            Package.id == cart_item.package_id,
            Package.store_id == store_id,
            Package.is_available.is_(True),
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise BadRequestError(f"Package {cart_item.package_id} not found or unavailable")

    # Packages don't support option groups — only addons if specified
    addons_snapshot = []
    addon_total = 0
    for choice_id in cart_item.selected_addon_choice_ids:
        ac = addon_map.get(choice_id)
        if not ac:
            raise BadRequestError(f"Addon choice {choice_id} not found or unavailable")
        extra = channel_service.ceil_markup(ac.extra_price, markup_bp)
        addon_total += extra
        addons_snapshot.append({"label": ac.label, "extra_price": extra})

    unit_price = channel_service.ceil_markup(pkg.flat_price, markup_bp)
    line_total = (unit_price + addon_total) * cart_item.quantity

    return {
        "item_id": None,
        "category_id": None,
        "package_id": pkg.id,
        "name": pkg.name,
        "unit_price": unit_price,
        "quantity": cart_item.quantity,
        "addon_total": addon_total,
        "line_total": line_total,
        "item_discount_amount": 0,
        "options_snapshot": None,
        "addons_snapshot": addons_snapshot or None,
    }


# CANCELLED and COMPLETED are final; paid orders are corrected with void/refund, never reopened.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}


async def update_order_status(
    order_id: uuid.UUID, store_id: uuid.UUID, status: OrderStatus, db: AsyncSession
) -> Order:
    await db.execute(
        select(Order.id).where(Order.id == order_id, Order.store_id == store_id).with_for_update()
    )
    order = await _load_order(order_id, store_id, db)
    if status not in ALLOWED_TRANSITIONS[order.status]:
        raise BadRequestError(f"An order that is {order.status.value} cannot become {status.value}")
    if status == OrderStatus.CANCELLED and (order.refunded_amount > 0 or order.settlement_id):
        raise BadRequestError("An order with refunds or a recorded platform payout cannot be cancelled")
    if status == OrderStatus.CANCELLED and order.status != OrderStatus.CANCELLED:
        await inventory_service.restore_for_order(store_id, order.id, order.order_number, db)
    order.status = status
    if status in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED) and order.confirmed_at is None:
        order.confirmed_at = datetime.now(UTC)
    if status == OrderStatus.CONFIRMED and order.kitchen_status is None:
        kitchen_enabled = (
            await db.execute(select(Store.kitchen_enabled).where(Store.id == store_id))
        ).scalar_one_or_none()
        if kitchen_enabled:
            order.kitchen_status = KitchenStatus.NEW
    if status == OrderStatus.COMPLETED:
        order.completed_at = datetime.now(UTC)
    await db.commit()
    return await _load_order(order_id, store_id, db)


async def _refundable_order(order_id, store_id, db) -> Order:
    """Locks the order row, then loads it; only paid direct orders can be refunded."""
    await db.execute(select(Order.id).where(Order.id == order_id, Order.store_id == store_id).with_for_update())
    order = await _load_order(order_id, store_id, db)
    if order.channel:
        raise BadRequestError("Online platform orders are refunded by the platform")
    if order.status not in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED):
        raise BadRequestError("Only paid orders can be refunded")
    return order


async def _record_refund(
    order: Order, store_id, user_id, rtype: RefundType, method: RefundMethod, amount: int,
    reason: str, db, item=None, qty: int | None = None,
) -> None:
    if amount <= 0 or amount > order.total_amount - order.refunded_amount:
        raise BadRequestError("Refund amount exceeds what is left on the order")
    if method == RefundMethod.CASH:
        from app.services import shift_service

        if not await shift_service.open_shift_of(store_id, db):
            raise BadRequestError("A cash refund needs an open shift")
    db.add(
        OrderRefund(
            order_id=order.id,
            store_id=store_id,
            user_id=user_id,
            type=rtype.value,
            method=method.value,
            amount=amount,
            reason=reason.strip(),
            order_item_id=item.id if item else None,
            quantity=qty,
            refunded_at=datetime.now(UTC),
        )
    )
    order.refunded_amount += amount


async def refund_order(order_id, store_id, user_id, payload: RefundCreate, db) -> Order:
    order = await _refundable_order(order_id, store_id, db)
    await _record_refund(order, store_id, user_id, RefundType.REFUND, payload.method, payload.amount, payload.reason, db)
    await db.commit()
    return await _load_order(order_id, store_id, db)


async def void_item(order_id, store_id, item_id, user_id, payload: VoidCreate, db) -> Order:
    order = await _refundable_order(order_id, store_id, db)
    item = next((i for i in order.items if i.id == item_id), None)
    if not item:
        raise NotFoundError("Order item not found")
    if payload.quantity > item.quantity - item.void_qty:
        raise BadRequestError("Quantity exceeds what is left on this line")
    remaining = sum(i.quantity - i.void_qty for i in order.items) - payload.quantity
    if remaining <= 0:
        raise BadRequestError("Every item would be voided; cancel the order instead")
    # proportional share of the line, so the last unit absorbs rounding
    before = item.line_total * item.void_qty // item.quantity
    after = item.line_total * (item.void_qty + payload.quantity) // item.quantity
    await _record_refund(
        order, store_id, user_id, RefundType.VOID, payload.method, after - before, payload.reason, db,
        item=item, qty=payload.quantity,
    )
    item.void_qty += payload.quantity
    await db.commit()
    return await _load_order(order_id, store_id, db)


async def list_kitchen_orders(
    store_id: uuid.UUID, db: AsyncSession, limit: int = 100, offset: int = 0
) -> tuple[list[Order], int]:
    """Confirmed orders still in the kitchen flow, oldest first."""
    cond = (
        Order.store_id == store_id,
        Order.status == OrderStatus.CONFIRMED,
        Order.kitchen_status.in_(
            [KitchenStatus.NEW, KitchenStatus.COOKING, KitchenStatus.READY]
        ),
    )
    total = (await db.execute(select(func.count()).select_from(Order).where(*cond))).scalar_one()
    q = (
        select(Order)
        .options(selectinload(Order.items))
        .where(*cond)
        .order_by(Order.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(q)).scalars().all()), total


async def _require_kitchen_order(order_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Order:
    kitchen_enabled = (
        await db.execute(select(Store.kitchen_enabled).where(Store.id == store_id))
    ).scalar_one_or_none()
    if not kitchen_enabled:
        raise BadRequestError("Kitchen management is not enabled for this store")
    order = await _load_order(order_id, store_id, db)
    if order.kitchen_status is None:
        raise BadRequestError("Order is not in the kitchen flow")
    return order


async def update_kitchen_status(
    order_id: uuid.UUID, store_id: uuid.UUID, kitchen_status: KitchenStatus, db: AsyncSession
) -> Order:
    order = await _require_kitchen_order(order_id, store_id, db)
    order.kitchen_status = kitchen_status
    await db.commit()
    return await _load_order(order_id, store_id, db)


async def update_kitchen_item(
    order_id: uuid.UUID, store_id: uuid.UUID, order_item_id: uuid.UUID, is_done: bool, db: AsyncSession
) -> Order:
    order = await _require_kitchen_order(order_id, store_id, db)
    line = next((i for i in order.items if i.id == order_item_id), None)
    if not line:
        raise NotFoundError("Order item not found")
    line.is_done = is_done
    await db.commit()
    return await _load_order(order_id, store_id, db)


async def _preview_item_line(
    store_id: uuid.UUID,
    cart_item: CartItemIn,
    db: AsyncSession,
    addon_map: dict[uuid.UUID, AddonChoice],
) -> dict:
    result = await db.execute(
        select(Item).where(
            Item.id == cart_item.item_id,
            Item.business_id == item_service.business_of(store_id),
            item_service.not_hidden_in(store_id),
            Item.is_available.is_(True),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise BadRequestError(f"Item {cart_item.item_id} not found or unavailable")

    addon_total = 0
    for choice_id in cart_item.selected_addon_choice_ids:
        ac = addon_map.get(choice_id)
        if not ac:
            raise BadRequestError(f"Addon choice {choice_id} not found or unavailable")
        addon_total += ac.extra_price

    return {
        "item_id": item.id,
        "category_id": item.category_id,
        "line_total": (await item_service.effective_price(item, store_id, db) + addon_total) * cart_item.quantity,
        "item_discount_amount": 0,
    }


async def _preview_package_line(
    store_id: uuid.UUID,
    cart_item: CartItemIn,
    db: AsyncSession,
    addon_map: dict[uuid.UUID, AddonChoice],
) -> dict:
    result = await db.execute(
        select(Package).where(
            Package.id == cart_item.package_id,
            Package.store_id == store_id,
            Package.is_available.is_(True),
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise BadRequestError(f"Package {cart_item.package_id} not found or unavailable")

    addon_total = 0
    for choice_id in cart_item.selected_addon_choice_ids:
        ac = addon_map.get(choice_id)
        if not ac:
            raise BadRequestError(f"Addon choice {choice_id} not found or unavailable")
        addon_total += ac.extra_price

    return {
        "item_id": None,
        "category_id": None,
        "line_total": (pkg.flat_price + addon_total) * cart_item.quantity,
        "item_discount_amount": 0,
    }


async def preview_order(
    store_id: uuid.UUID, payload: OrderPreviewRequest, db: AsyncSession
) -> dict:
    """Compute order totals and validate a promo code without writing to DB."""
    all_addon_ids = [cid for ci in payload.items for cid in ci.selected_addon_choice_ids]
    addon_map: dict[uuid.UUID, AddonChoice] = {}
    if all_addon_ids:
        ac_rows = (
            await db.execute(
                select(AddonChoice).where(
                    AddonChoice.id.in_(all_addon_ids),
                    AddonChoice.is_available.is_(True),
                )
            )
        ).scalars()
        addon_map = {r.id: r for r in ac_rows}

    line_results = []
    for cart_item in payload.items:
        if cart_item.item_id:
            line = await _preview_item_line(store_id, cart_item, db, addon_map)
        else:
            line = await _preview_package_line(store_id, cart_item, db, addon_map)
        line_results.append(line)

    # Apply automatic ITEM-scope discounts (read-only, no locking)
    auto_discounts = await discount_service.list_automatic_item_discounts(store_id, db)
    for auto_d in auto_discounts:
        for line in line_results:
            if not discount_service.line_matches_discount(
                auto_d, line.get("item_id"), line.get("category_id")
            ):
                continue
            d_amount = discount_service.calc_line_discount(auto_d, line["line_total"])
            if d_amount > 0:
                line["item_discount_amount"] += d_amount
                line["line_total"] -= d_amount

    subtotal = sum(r["line_total"] for r in line_results)

    discount_amount = 0
    is_valid = True
    message = ""

    if payload.discount_code:
        cart_items_for_validate = [
            {
                "item_id": r.get("item_id"),
                "category_id": r.get("category_id"),
                "line_subtotal": r["line_total"],
            }
            for r in line_results
        ]
        is_valid, discount_amount, _, message = await discount_service.validate(
            payload.discount_code, store_id, subtotal, db, cart_items_for_validate
        )

    net = subtotal - discount_amount if is_valid else subtotal
    service_bp, pb1_bp = (
        await db.execute(select(Store.service_bp, Store.pb1_bp).where(Store.id == store_id))
    ).one()
    service_amount, pb1_amount = direct_order_fees(net, payload.order_type == "DINE_IN", service_bp, pb1_bp)
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount if is_valid else 0,
        "service_amount": service_amount,
        "pb1_amount": pb1_amount,
        "total_amount": net + service_amount + pb1_amount,
        "valid": is_valid,
        "message": message,
    }
