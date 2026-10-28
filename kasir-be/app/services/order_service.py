import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, NotFoundError
from app.models import (
    AddonChoice,
    Discount,
    Item,
    OptionChoice,
    Order,
    OrderItem,
    Package,
)
from app.models.discount import DiscountScope, DiscountType
from app.models.order import OrderStatus, PaymentMethod
from app.schemas.order import CartItemIn, OrderCreate, OrderPreviewRequest
from app.services import discount_service


async def _load_order(order_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Order:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.store_id == store_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")
    return order


async def get_order(order_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Order:
    return await _load_order(order_id, store_id, db)


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
) -> tuple[list[Order], int]:
    q = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.store_id == store_id)
        .order_by(Order.created_at.desc())
    )
    count_q = select(func.count()).select_from(Order).where(Order.store_id == store_id)
    if status:
        q = q.where(Order.status == status)
        count_q = count_q.where(Order.status == status)
    if payment_method:
        q = q.where(Order.payment_method == payment_method)
        count_q = count_q.where(Order.payment_method == payment_method)
    if date_from:
        dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
        q = q.where(Order.created_at >= dt_from)
        count_q = count_q.where(Order.created_at >= dt_from)
    if date_to:
        dt_to = datetime(date_to.year, date_to.month, date_to.day, tzinfo=UTC) + timedelta(days=1)
        q = q.where(Order.created_at < dt_to)
        count_q = count_q.where(Order.created_at < dt_to)
    if operator_id:
        q = q.where(Order.operator_id == operator_id)
        count_q = count_q.where(Order.operator_id == operator_id)

    total = (await db.execute(count_q)).scalar_one()
    orders = list((await db.execute(q.limit(limit).offset(offset))).scalars().all())
    return orders, total


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
                line = await _process_item_line(store_id, cart_item, db, option_map, addon_map)
            else:
                line = await _process_package_line(store_id, cart_item, db, addon_map)
            line_results.append(line)

        # --- Apply automatic ITEM-scope discounts ---
        # Lock each automatic discount to prevent race on used_count
        auto_discounts = await discount_service.list_automatic_item_discounts(store_id, db)
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

        if payload.discount_code:
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

        # Write Order
        order = Order(
            store_id=store_id,
            operator_id=operator_id,
            order_number=order_number,
            payment_method=payload.payment_method,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total_amount=total_amount,
            discount_id=discount_obj.id if discount_obj else None,
            discount_code_snapshot=discount_code_snapshot,
            notes=payload.notes,
            order_type=getattr(payload, "order_type", None),
            table_number=getattr(payload, "table_number", None),
            customer_name=getattr(payload, "customer_name", None),
            status=initial_status,
        )
        db.add(order)
        await db.flush()

        for line in line_results:
            db.add(
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
) -> dict:
    result = await db.execute(
        select(Item)
        .where(
            Item.id == cart_item.item_id,
            Item.store_id == store_id,
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
        addon_total += ac.extra_price
        addons_snapshot.append(
            {"label": ac.label, "extra_price": ac.extra_price, "group_id": str(ac.group_id)}
        )

    line_total = (item.base_price + addon_total) * cart_item.quantity

    return {
        "item_id": item.id,
        "category_id": item.category_id,
        "package_id": None,
        "name": item.name,
        "unit_price": item.base_price,
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
        addon_total += ac.extra_price
        addons_snapshot.append({"label": ac.label, "extra_price": ac.extra_price})

    line_total = (pkg.flat_price + addon_total) * cart_item.quantity

    return {
        "item_id": None,
        "category_id": None,
        "package_id": pkg.id,
        "name": pkg.name,
        "unit_price": pkg.flat_price,
        "quantity": cart_item.quantity,
        "addon_total": addon_total,
        "line_total": line_total,
        "item_discount_amount": 0,
        "options_snapshot": None,
        "addons_snapshot": addons_snapshot or None,
    }


async def update_order_status(
    order_id: uuid.UUID, store_id: uuid.UUID, status: OrderStatus, db: AsyncSession
) -> Order:
    order = await _load_order(order_id, store_id, db)
    order.status = status
    if status == OrderStatus.COMPLETED:
        order.completed_at = datetime.now(UTC)
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
            Item.store_id == store_id,
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
        "line_total": (item.base_price + addon_total) * cart_item.quantity,
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

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount if is_valid else 0,
        "total_amount": subtotal - discount_amount if is_valid else subtotal,
        "valid": is_valid,
        "message": message,
    }
