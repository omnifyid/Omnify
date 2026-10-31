"""Demo data: one business ("Kopi Senja") with three stores set up differently.

- Kemang  (parent): every feature on: kitchen, QR self-order, dine-in tables, service charge + PB1,
  three online platforms, recipes and ingredient stock, discounts, packages, shifts, expenses,
  platform payouts, refunds.
- Senopati (branch): kitchen and two platforms, no service charge, self-order closed, own prices,
  some products not sold, a smaller ingredient list.
- BSD      (branch): minimal: take-away only, no kitchen, no online, no inventory, no tax, own prices,
  several products not sold; its shift is closed.

Orders, shifts and stock are written in bulk (no per-order service calls) so a reset is fast even on a
remote database. Totals use the same helpers as `order_service`.
"""

import random
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    AddonChoice,
    AddonGroup,
    Business,
    CashMovement,
    ChannelSetting,
    Discount,
    Expense,
    Ingredient,
    Item,
    ItemCategory,
    ItemChannelPrice,
    ItemStoreSetting,
    OptionChoice,
    OptionGroup,
    Order,
    OrderItem,
    OrderRefund,
    Package,
    PackageItem,
    PlatformSettlement,
    RecipeLine,
    Shift,
    StockMovement,
    Store,
    StoreMembership,
    User,
)
from app.models.discount import DiscountScope, DiscountTarget, DiscountType
from app.models.finance import EXPENSE_CATEGORIES
from app.models.membership import StoreRole
from app.models.order import KitchenStatus, OrderStatus, PaymentMethod
from app.services import seed_data as D
from app.services.channel_service import ceil_markup, included_tax
from app.services.discount_service import calc_line_discount, line_matches_discount
from app.services.order_service import direct_order_fees

DEMO_PASSWORD = "demo1234"
JKT = timezone(timedelta(hours=7))
DAYS = 14  # history length

USERS = [
    ("owner@demo.com", "Budi Santoso"),
    ("manager@demo.com", "Sari Dewi"),
    ("operator@demo.com", "Andi Pratama"),
    ("kasir.senopati@demo.com", "Rina Lestari"),
    ("manager.bsd@demo.com", "Wulan Sari"),
    ("kasir.bsd@demo.com", "Dimas Putra"),
]
DEMO_EMAILS = [e for e, _ in USERS]

# store key -> definition. `members` maps email -> role.
STORES = [
    {
        "key": "kemang",
        "name": "Kopi Senja Kemang",
        "slug": "kopi-senja-kemang",
        "description": "Kedai kopi modern dengan suasana cozy. Toko pusat, semua fitur aktif.",
        "age_days": 40,
        "settings": dict(
            self_order_enabled=True, selforder_is_open=True, pos_dine_in_enabled=True,
            pos_table_enabled=True, pos_table_count=12, pos_customer_name_enabled=True,
            kitchen_enabled=True, service_bp=500, pb1_bp=1000, tax_bp=1100,
            shift_variance_threshold=20000, default_float=500000,
            receipt_header="KOPI SENJA KEMANG\nJl. Kemang Raya No. 18, Jakarta Selatan",
            receipt_footer="Terima kasih! IG @kopisenja",
        ),
        "channels": {
            "GOFOOD": (2000, 1500, 2), "GRABFOOD": (2000, 1500, 3), "SHOPEEFOOD": (1500, 1000, 4),
        },
        "members": {
            "owner@demo.com": StoreRole.OWNER, "manager@demo.com": StoreRole.MANAGER,
            "operator@demo.com": StoreRole.OPERATOR,
        },
        "cashiers": ["operator@demo.com", "operator@demo.com", "manager@demo.com", "owner@demo.com"],
        "reviewer": "manager@demo.com",
        "orders_per_day": (9, 15), "online_share": 0.22, "dine_share": 0.55,
        "hours": (8, 21), "hidden": [], "prices": {},
    },
    {
        "key": "senopati",
        "name": "Kopi Senja Senopati",
        "slug": "kopi-senja-senopati",
        "description": "Cabang Senopati: dapur dan 2 platform online, tanpa service charge.",
        "age_days": 25,
        "settings": dict(
            self_order_enabled=True, selforder_is_open=False, pos_dine_in_enabled=True,
            pos_table_enabled=False, pos_table_count=10, pos_customer_name_enabled=False,
            kitchen_enabled=True, service_bp=0, pb1_bp=1000, tax_bp=1100,
            shift_variance_threshold=10000, default_float=300000,
            receipt_header="KOPI SENJA SENOPATI\nJl. Senopati No. 62, Jakarta Selatan",
            receipt_footer="Terima kasih sudah mampir!",
        ),
        "channels": {"GOFOOD": (2000, 1500, 2), "GRABFOOD": (2200, 1500, 3)},
        "members": {
            "owner@demo.com": StoreRole.OWNER, "manager@demo.com": StoreRole.MANAGER,
            "kasir.senopati@demo.com": StoreRole.OPERATOR,
        },
        "cashiers": ["kasir.senopati@demo.com", "kasir.senopati@demo.com", "manager@demo.com"],
        "reviewer": "manager@demo.com",
        "orders_per_day": (4, 8), "online_share": 0.15, "dine_share": 0.4,
        "hours": (8, 22), "hidden": ["Pasta Carbonara", "Waffle Butter Maple", "Strawberry Smoothie"],
        "prices": {"Latte": 29000, "Cappuccino": 27000, "Es Kopi Susu": 27000, "Kopi Gula Aren": 29000,
                   "Croissant Mentega": 20000},
    },
    {
        "key": "bsd",
        "name": "Kopi Senja BSD",
        "slug": "kopi-senja-bsd",
        "description": "Cabang BSD: sederhana, bawa pulang saja, tanpa dapur dan online.",
        "age_days": 12,
        "settings": dict(
            self_order_enabled=False, selforder_is_open=False, pos_dine_in_enabled=False,
            pos_table_enabled=False, pos_table_count=10, pos_customer_name_enabled=False,
            kitchen_enabled=False, service_bp=0, pb1_bp=0, tax_bp=0,
            shift_variance_threshold=20000, default_float=200000,
            receipt_header="KOPI SENJA BSD", receipt_footer="",
        ),
        "channels": {},
        "members": {
            "owner@demo.com": StoreRole.OWNER, "manager.bsd@demo.com": StoreRole.MANAGER,
            "kasir.bsd@demo.com": StoreRole.OPERATOR,
        },
        "cashiers": ["kasir.bsd@demo.com", "kasir.bsd@demo.com", "manager.bsd@demo.com"],
        "reviewer": "manager.bsd@demo.com",
        "orders_per_day": (2, 5), "online_share": 0.0, "dine_share": 0.0,
        "hours": (9, 20),
        "hidden": ["Nasi Goreng Spesial", "Pasta Carbonara", "Cold Brew", "Pisang Goreng Keju", "Kue Lapis Legit"],
        "prices": {"Espresso": 17000, "Americano": 19000, "Iced Latte": 27000},
    },
]

# manual platform prices (shared by item; replaces the base price on that platform)
MANUAL_CHANNEL_PRICES = {
    "Espresso": {"GOFOOD": 26000, "GRABFOOD": 26000},
    "Es Kopi Susu": {"GOFOOD": 33000},
    "Nasi Goreng Spesial": {"GOFOOD": 45000},
}

# (name, unit, category, cost per unit, min_stock)
INGREDIENTS = [
    ("Biji Kopi Arabica", "g", "Kopi", 450, 2000), ("Biji Kopi Robusta", "g", "Kopi", 300, 1500),
    ("Susu Segar", "ml", "Susu", 18, 6000), ("Susu Oat", "ml", "Susu", 45, 2000),
    ("Gula Aren Cair", "ml", "Pemanis", 25, 1500), ("Sirup Vanilla", "ml", "Pemanis", 40, 800),
    ("Matcha Powder", "g", "Non-Kopi", 900, 300), ("Cokelat Bubuk", "g", "Non-Kopi", 200, 500),
    ("Teh Hitam", "g", "Non-Kopi", 150, 300), ("Es Batu", "g", "Lainnya", 5, 8000),
    ("Cup Kertas 8oz", "pcs", "Kemasan", 600, 100), ("Cup Plastik 12oz", "pcs", "Kemasan", 700, 150),
    ("Tepung Terigu", "g", "Bakery", 12, 3000), ("Mentega", "g", "Bakery", 130, 1000),
    ("Telur", "pcs", "Bakery", 2200, 40), ("Keju Cheddar", "g", "Bakery", 150, 800),
    ("Ayam Fillet", "g", "Protein", 45, 3000), ("Kentang Beku", "g", "Bakery", 40, 3000),
    ("Roti Tawar", "pcs", "Bakery", 1500, 40), ("Nasi Putih", "g", "Makanan", 15, 4000),
    ("Pasta Spaghetti", "g", "Makanan", 35, 2000), ("Pisang", "pcs", "Bakery", 1500, 30),
]
# senopati keeps a smaller list; bsd has none
SENOPATI_SKIP = {"Pasta Spaghetti", "Nasi Putih", "Ayam Fillet", "Pisang", "Teh Hitam"}
LOW_STOCK = {"Susu Segar", "Matcha Powder", "Telur"}  # left under min_stock so the low-stock KPI shows

HOT, ICED = "Cup Kertas 8oz", "Cup Plastik 12oz"
RECIPES = {
    "Espresso": [("Biji Kopi Arabica", 18), (HOT, 1)],
    "Americano": [("Biji Kopi Arabica", 18), (HOT, 1)],
    "Cappuccino": [("Biji Kopi Arabica", 18), ("Susu Segar", 120), (HOT, 1)],
    "Latte": [("Biji Kopi Arabica", 18), ("Susu Segar", 180), (HOT, 1)],
    "Flat White": [("Biji Kopi Arabica", 18), ("Susu Segar", 140), (HOT, 1)],
    "Macchiato": [("Biji Kopi Arabica", 18), ("Susu Segar", 40), (HOT, 1)],
    "Iced Americano": [("Biji Kopi Arabica", 18), ("Es Batu", 120), (ICED, 1)],
    "Iced Latte": [("Biji Kopi Arabica", 18), ("Susu Segar", 150), ("Es Batu", 100), (ICED, 1)],
    "Iced Cappuccino": [("Biji Kopi Arabica", 18), ("Susu Segar", 110), ("Es Batu", 100), (ICED, 1)],
    "Cold Brew": [("Biji Kopi Arabica", 30), ("Es Batu", 120), (ICED, 1)],
    "Es Kopi Susu": [("Biji Kopi Robusta", 18), ("Susu Segar", 100), ("Gula Aren Cair", 20), ("Es Batu", 100), (ICED, 1)],
    "Kopi Gula Aren": [("Biji Kopi Robusta", 18), ("Susu Segar", 80), ("Gula Aren Cair", 30), ("Es Batu", 100), (ICED, 1)],
    "Teh Tarik": [("Teh Hitam", 6), ("Susu Segar", 100), (HOT, 1)],
    "Matcha Latte": [("Matcha Powder", 8), ("Susu Segar", 180), (HOT, 1)],
    "Coklat Panas": [("Cokelat Bubuk", 25), ("Susu Segar", 180), (HOT, 1)],
    "Iced Matcha": [("Matcha Powder", 8), ("Susu Segar", 150), ("Es Batu", 100), (ICED, 1)],
    "Yuzu Tea": [("Teh Hitam", 5), ("Sirup Vanilla", 15), ("Es Batu", 100), (ICED, 1)],
    "Nasi Goreng Spesial": [("Nasi Putih", 220), ("Telur", 1), ("Ayam Fillet", 60)],
    "Sandwich Ayam Crispy": [("Roti Tawar", 2), ("Ayam Fillet", 80), ("Keju Cheddar", 20)],
    "Pasta Carbonara": [("Pasta Spaghetti", 120), ("Keju Cheddar", 30), ("Telur", 1), ("Susu Segar", 50)],
    "Waffle Butter Maple": [("Tepung Terigu", 120), ("Mentega", 25), ("Telur", 1), ("Susu Segar", 60)],
    "Roti Bakar Keju": [("Roti Tawar", 3), ("Mentega", 10), ("Keju Cheddar", 25)],
    "Kentang Goreng": [("Kentang Beku", 180)],
    "Croissant Mentega": [("Tepung Terigu", 70), ("Mentega", 35)],
    "Donat Glazed": [("Tepung Terigu", 60), ("Telur", 1)],
    "Pisang Goreng Keju": [("Pisang", 3), ("Tepung Terigu", 40), ("Keju Cheddar", 20)],
}

PAYMENT_WEIGHTS = [("CASH", 45), ("QRIS", 33), ("CARD", 14), ("TRANSFER", 8)]
CUSTOMERS = ["Rina", "Bayu", "Dewi", "Arif", "Sinta", "Yoga", "Maya", "Fajar", "Nadia", "Rizky"]
DRIVERS = ["Pak Joko", "Mas Eko", "Bang Ucup", "Mbak Tari"]
REFUND_REASONS = ["Pesanan salah", "Pelanggan komplain rasa", "Menu habis setelah dibayar", "Double input kasir"]
CASH_OUTS = [
    ("Bahan non-stok", "Beli es batu & plastik", 35000), ("Transport", "Ongkos kirim bahan", 25000),
    ("Perbaikan & perawatan", "Servis mesin kopi", 150000), ("Lain-lain", "Beli galon air", 20000),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _utc(d: date, hour: int, minute: int = 0) -> datetime:
    """Wall-clock time in Jakarta as an aware UTC datetime."""
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=JKT).astimezone(UTC)


def _naive(dt: datetime) -> datetime:
    """created_at / updated_at columns are timezone-naive UTC."""
    return dt.astimezone(UTC).replace(tzinfo=None)


def _pick(rng: random.Random, weighted: list[tuple[str, int]]) -> str:
    return rng.choices([w[0] for w in weighted], weights=[w[1] for w in weighted])[0]


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

async def reset_demo(db: AsyncSession) -> int:
    """Remove demo stores (the demo slugs and any store only demo accounts belong to), then demo users.

    Super admins are never removed or created here. Returns the number of stores removed.
    """
    demo_user_ids = list((await db.execute(select(User.id).where(User.email.in_(DEMO_EMAILS)))).scalars())
    slugs = [s["slug"] for s in STORES] + ["kopi-senja"]  # "kopi-senja" = the earlier single-store demo
    store_ids = set((await db.execute(select(Store.id).where(Store.slug.in_(slugs)))).scalars())
    if demo_user_ids:
        rows = await db.execute(
            select(StoreMembership.store_id)
            .group_by(StoreMembership.store_id)
            .having(func.bool_and(StoreMembership.user_id.in_(demo_user_ids)))
        )
        store_ids |= set(rows.scalars())
    if store_ids:
        # orders do not cascade from stores; their items, refunds and stock movements do from orders
        await db.execute(delete(Order).where(Order.store_id.in_(store_ids)))
        # package lines restrict deleting their items, so packages go before the stores cascade to items
        await db.execute(delete(Package).where(Package.store_id.in_(store_ids)))
        await db.execute(delete(Store).where(Store.id.in_(store_ids)))
        await db.execute(
            delete(Business).where(~select(Store.id).where(Store.business_id == Business.id).exists())
        )
    if demo_user_ids:
        await db.execute(update(Order).where(Order.operator_id.in_(demo_user_ids)).values(operator_id=None))
    await db.execute(delete(User).where(User.email.in_(DEMO_EMAILS), User.is_superadmin.is_(False)))
    await db.commit()
    return len(store_ids)


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

async def reseed(db: AsyncSession) -> dict:
    """Reset demo data and write it again. Returns row counts."""
    removed = await reset_demo(db)
    summary = await seed_demo(db)
    summary["removed_stores"] = removed
    return summary


async def seed_demo(db: AsyncSession) -> dict:
    rng = random.Random(20251031)
    now = datetime.now(UTC)
    today = now.astimezone(JKT).date()
    counts: dict[str, int] = defaultdict(int)

    # ── accounts ────────────────────────────────────────────────────────────
    users: dict[str, User] = {}
    pw = hash_password(DEMO_PASSWORD)
    for email, name in USERS:
        u = User(id=uuid.uuid4(), email=email, full_name=name, hashed_password=pw)
        users[email] = u
        db.add(u)
    counts["users"] = len(users)

    # ── business + stores (parent = oldest) ─────────────────────────────────
    business = Business(id=uuid.uuid4(), name="Kopi Senja", created_at=_naive(now - timedelta(days=45)),
                        updated_at=_naive(now))
    db.add(business)
    await db.flush()
    stores: dict[str, Store] = {}
    for sd in STORES:
        created = _naive(now - timedelta(days=sd["age_days"]))
        st = Store(
            id=uuid.uuid4(), business_id=business.id, name=sd["name"], slug=sd["slug"],
            description=sd["description"], created_at=created, updated_at=created, **sd["settings"],
        )
        stores[sd["key"]] = st
        db.add(st)
    await db.flush()
    for sd in STORES:
        st = stores[sd["key"]]
        for email, role in sd["members"].items():
            db.add(StoreMembership(id=uuid.uuid4(), user_id=users[email].id, store_id=st.id, role=role))
        for ch, (commission, markup, lag) in sd["channels"].items():
            db.add(ChannelSetting(id=uuid.uuid4(), store_id=st.id, channel=ch, enabled=True,
                                  commission_bp=commission, markup_bp=markup, payout_lag_days=lag))
        if "SHOPEEFOOD" not in sd["channels"] and sd["channels"]:
            db.add(ChannelSetting(id=uuid.uuid4(), store_id=st.id, channel="SHOPEEFOOD", enabled=False,
                                  commission_bp=1500, markup_bp=1000, payout_lag_days=4))
    await db.flush()
    counts["stores"] = len(stores)

    # ── catalog (shared by the business) ────────────────────────────────────
    cats: list[ItemCategory] = []
    for name, sort in D.CATEGORIES:
        c = ItemCategory(id=uuid.uuid4(), store_id=stores["kemang"].id, business_id=business.id,
                         name=name, sort_order=sort)
        cats.append(c)
        db.add(c)
    await db.flush()

    catalog: dict[str, dict] = {}
    for name, price, cat_idx, sort in D.ITEMS:
        item = Item(id=uuid.uuid4(), store_id=stores["kemang"].id, business_id=business.id,
                    category_id=cats[cat_idx].id, name=name, base_price=price, sort_order=sort)
        db.add(item)
        catalog[name] = {"item": item, "id": item.id, "name": name, "cat_id": cats[cat_idx].id,
                         "cat_name": cats[cat_idx].name, "base": price, "options": [], "addons": []}
    await db.flush()

    pending_choices: list = []  # choices are added after their groups are flushed
    for item_name, groups in D.ITEM_OPTIONS.items():
        info = catalog.get(item_name)
        if not info:
            continue
        for g_idx, (g_name, required, choices) in enumerate(groups, start=1):
            g = OptionGroup(id=uuid.uuid4(), item_id=info["id"], name=g_name, is_required=required, sort_order=g_idx)
            db.add(g)
            entry = {"id": g.id, "name": g_name, "required": required, "choices": []}
            for c_idx, (label, is_default) in enumerate(choices, start=1):
                ch = OptionChoice(id=uuid.uuid4(), group_id=g.id, label=label, is_default=is_default, sort_order=c_idx)
                pending_choices.append(ch)
                entry["choices"].append({"id": ch.id, "label": label, "default": is_default})
            info["options"].append(entry)
            counts["option_groups"] += 1
    for item_name, groups in D.ITEM_ADDONS.items():
        info = catalog.get(item_name)
        if not info:
            continue
        for g_idx, (g_name, required, min_s, max_s, choices) in enumerate(groups, start=1):
            g = AddonGroup(id=uuid.uuid4(), item_id=info["id"], name=g_name, is_required=required,
                           min_select=min_s, max_select=max_s, sort_order=g_idx)
            db.add(g)
            entry = {"id": g.id, "name": g_name, "choices": []}
            for c_idx, (label, extra) in enumerate(choices, start=1):
                ch = AddonChoice(id=uuid.uuid4(), group_id=g.id, label=label, extra_price=extra, sort_order=c_idx)
                pending_choices.append(ch)
                entry["choices"].append({"id": ch.id, "label": label, "extra": extra})
            info["addons"].append(entry)
            counts["addon_groups"] += 1
    await db.flush()
    db.add_all(pending_choices)
    counts["items"] = len(catalog)
    counts["categories"] = len(cats)

    # per-store sold toggle / price (the Dijual di cabang settings)
    sold: dict[str, list[str]] = {}
    price_of: dict[str, dict[str, int]] = {}
    for sd in STORES:
        st = stores[sd["key"]]
        price_of[sd["key"]] = {n: sd["prices"].get(n, i["base"]) for n, i in catalog.items()}
        sold[sd["key"]] = [n for n in catalog if n not in sd["hidden"]]
        for name in sd["hidden"]:
            db.add(ItemStoreSetting(id=uuid.uuid4(), item_id=catalog[name]["id"], store_id=st.id, is_sold=False))
        for name, price in sd["prices"].items():
            db.add(ItemStoreSetting(id=uuid.uuid4(), item_id=catalog[name]["id"], store_id=st.id,
                                    is_sold=True, price=price))
    manual_prices: dict[str, dict[str, int]] = {}
    for name, per in MANUAL_CHANNEL_PRICES.items():
        for ch, price in per.items():
            db.add(ItemChannelPrice(id=uuid.uuid4(), item_id=catalog[name]["id"], channel=ch, price=price))
            manual_prices.setdefault(name, {})[ch] = price
    await db.flush()

    # ── packages ────────────────────────────────────────────────────────────
    packages: dict[str, list[dict]] = {k: [] for k in stores}
    package_lines: list = []

    def add_package(store_key: str, name: str, flat: int, lines: list[tuple[str, int]], desc: str) -> None:
        pkg = Package(id=uuid.uuid4(), store_id=stores[store_key].id, name=name, description=desc, flat_price=flat)
        db.add(pkg)
        for item_name, qty in lines:
            package_lines.append(PackageItem(id=uuid.uuid4(), package_id=pkg.id, item_id=catalog[item_name]["id"], quantity=qty))
        packages[store_key].append({"id": pkg.id, "name": name, "flat": flat})
        counts["packages"] += 1

    add_package("kemang", "Paket Ngopi Pagi", 38000, [("Latte", 1), ("Croissant Mentega", 1)], "Latte + croissant")
    add_package("kemang", "Paket Berdua", 62000, [("Es Kopi Susu", 2), ("Kentang Goreng", 1)], "2 es kopi susu + kentang")
    add_package("senopati", "Paket Senopati", 36000, [("Cappuccino", 1), ("Donat Glazed", 1)], "Cappuccino + donat")
    await db.flush()
    db.add_all(package_lines)

    # ── discounts ───────────────────────────────────────────────────────────
    discounts: dict[str, list[Discount]] = {k: [] for k in stores}

    def add_discount(store_key: str, **kw) -> Discount:
        d = Discount(id=uuid.uuid4(), store_id=stores[store_key].id, **kw)
        db.add(d)
        discounts[store_key].append(d)
        counts["discounts"] += 1
        return d

    snack = next(c for c in cats if c.name == "Snack")
    makanan = next(c for c in cats if c.name == "Makanan")
    P, F, O, I = DiscountType.PERCENTAGE, DiscountType.FIXED, DiscountScope.ORDER, DiscountScope.ITEM
    add_discount("kemang", name="Hemat 10%", code="HEMAT10", discount_type=P, value=1000, scope=O,
                 min_order_amount=50000, max_discount_amount=20000, max_uses=300)
    add_discount("kemang", name="Diskon Rp5.000", code="DISKON5K", discount_type=F, value=5000, scope=O,
                 min_order_amount=30000)
    add_discount("kemang", name="Happy Hour Snack 15%", code=None, discount_type=P, value=1500, scope=I,
                 target_type=DiscountTarget.CATEGORY, target_category_id=snack.id, is_automatic=True)
    add_discount("kemang", name="Promo Kopi Gula Aren", code="GULAREN", discount_type=F, value=3000, scope=I,
                 target_type=DiscountTarget.ITEM, target_item_id=catalog["Kopi Gula Aren"]["id"])
    add_discount("kemang", name="Ramadan Berkah (kedaluwarsa)", code="RAMADAN20", discount_type=P, value=2000,
                 scope=O, expires_at=now - timedelta(days=30))
    add_discount("kemang", name="Diskon Staff (nonaktif)", code="STAFF30", discount_type=P, value=3000, scope=O,
                 is_active=False)
    add_discount("kemang", name="Grand Opening (habis)", code="BUKA10K", discount_type=F, value=10000, scope=O,
                 max_uses=50, used_count=50)
    add_discount("senopati", name="Promo Senopati 15%", code="SENOPATI15", discount_type=P, value=1500, scope=O,
                 min_order_amount=40000, max_discount_amount=15000)
    add_discount("senopati", name="Diskon Makanan 10%", code=None, discount_type=P, value=1000, scope=I,
                 target_type=DiscountTarget.CATEGORY, target_category_id=makanan.id, is_automatic=True)
    add_discount("bsd", name="Diskon BSD Rp5.000", code="BSD5K", discount_type=F, value=5000, scope=O,
                 min_order_amount=25000)
    await db.flush()

    # ── ingredients + recipes ───────────────────────────────────────────────
    ingredients: dict[str, dict[str, Ingredient]] = {k: {} for k in stores}
    for key in ("kemang", "senopati"):
        for name, unit, category, cost, min_stock in INGREDIENTS:
            if key == "senopati" and name in SENOPATI_SKIP:
                continue
            ing = Ingredient(id=uuid.uuid4(), store_id=stores[key].id, name=name, unit=unit, category=category,
                             cost_price=cost, min_stock=Decimal(min_stock), stock=Decimal(0))
            ingredients[key][name] = ing
            db.add(ing)
            counts["ingredients"] += 1
    await db.flush()
    cost_of = {name: cost for name, _, _, cost, _ in INGREDIENTS}
    for item_name, lines in RECIPES.items():
        info = catalog[item_name]
        for ing_name, qty in lines:
            db.add(RecipeLine(id=uuid.uuid4(), item_id=info["id"], ingredient_id=ingredients["kemang"][ing_name].id,
                              quantity=Decimal(qty)))
            counts["recipe_lines"] += 1
        info["item"].cost_price = int(sum(cost_of[n] * q for n, q in lines))  # HPP from the recipe
    await db.flush()

    # ── orders ──────────────────────────────────────────────────────────────
    ctx = _Ctx(rng=rng, now=now, today=today, users=users, stores=stores, catalog=catalog, sold=sold,
               price_of=price_of, manual_prices=manual_prices, packages=packages, discounts=discounts,
               ingredients=ingredients)
    orders: list[dict] = []
    for sd in STORES:
        orders += _gen_orders(ctx, sd)
    for o in orders:
        db.add(o["order"])
        db.add_all(o["lines"])
        counts["orders"] += 1
    counts["order_lines"] = sum(len(o["lines"]) for o in orders)
    await db.flush()

    refunds = _gen_refunds(ctx, orders)
    db.add_all(refunds)
    counts["refunds"] = len(refunds)

    settlements, links = _gen_settlements(ctx, orders)
    db.add_all(settlements)
    counts["settlements"] = len(settlements)
    await db.flush()
    for order, settlement_id in links:  # orders link to settlements only after those exist
        order.settlement_id = settlement_id
    await db.flush()

    # ── ingredient ledger (initial, restocks, sales, returns, one opname) ───
    movements = _gen_stock(ctx, orders)
    db.add_all(movements)
    counts["stock_movements"] = len(movements)

    # ── shifts, cash movements, expenses ────────────────────────────────────
    extra = _gen_shifts_and_expenses(ctx, orders, refunds)
    db.add_all(extra["objects"])
    await db.flush()
    db.add_all(extra["movements"])  # cash movements reference shifts and expenses
    counts["shifts"] = extra["shifts"]
    counts["expenses"] = extra["expenses"]
    counts["cash_movements"] = extra["cash_movements"]

    # discount usage mirrors the generated orders
    for key, lst in discounts.items():
        for d in lst:
            d.used_count = max(d.used_count, ctx.used.get(d.id, 0))

    await db.commit()
    return dict(counts)


class _Ctx:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.used: dict[uuid.UUID, int] = defaultdict(int)
        self.stock_events: dict[uuid.UUID, list] = defaultdict(list)  # ingredient id -> events
        self.store_defs = {s["key"]: s for s in STORES}


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------

def _build_lines(ctx: _Ctx, key: str, online: str | None, setting: tuple[int, int, int] | None, n_lines: int):
    """Returns line dicts (name, ids, prices, snapshots) for one order."""
    rng = ctx.rng
    markup = setting[1] if online and setting else 0
    lines = []
    names = rng.sample(ctx.sold[key], k=min(n_lines, len(ctx.sold[key])))
    for name in names:
        info = ctx.catalog[name]
        base = ctx.price_of[key][name]
        opt_snap, add_snap, addon_total = [], [], 0
        for g in info["options"]:
            if g["required"] or rng.random() < 0.35:
                ch = next((c for c in g["choices"] if c["default"]), None) if rng.random() < 0.6 else rng.choice(g["choices"])
                ch = ch or rng.choice(g["choices"])
                opt_snap.append({"label": ch["label"], "group_id": str(g["id"])})
        for g in info["addons"]:
            if rng.random() < 0.28:
                ch = rng.choice(g["choices"])
                extra = ceil_markup(ch["extra"], markup)
                addon_total += extra
                add_snap.append({"label": ch["label"], "extra_price": extra, "group_id": str(g["id"])})
        manual_price = ctx.manual_prices.get(name, {}).get(online) if online else None
        unit = manual_price or ceil_markup(base, markup)
        qty = rng.choices([1, 2, 3], weights=[70, 24, 6])[0]
        lines.append({
            "item_id": info["id"], "category_id": info["cat_id"], "package_id": None, "name": name,
            "unit": unit, "qty": qty, "addon_total": addon_total, "disc": 0,
            "total": (unit + addon_total) * qty,
            "options": opt_snap or None, "addons": add_snap or None,
        })
    if not online and ctx.packages[key] and rng.random() < 0.1:
        pkg = rng.choice(ctx.packages[key])
        lines.append({
            "item_id": None, "category_id": None, "package_id": pkg["id"], "name": pkg["name"],
            "unit": pkg["flat"], "qty": 1, "addon_total": 0, "disc": 0, "total": pkg["flat"],
            "options": None, "addons": None,
        })
    return lines


def _gen_orders(ctx: _Ctx, sd: dict) -> list[dict]:
    rng, key = ctx.rng, sd["key"]
    store: Store = ctx.stores[key]
    out: list[dict] = []
    open_h, close_h = sd["hours"]
    seq: dict[date, int] = defaultdict(int)
    channel_ids: set[str] = set()
    cashiers = sd["cashiers"]
    auto_discounts = [d for d in ctx.discounts[key]
                      if d.is_automatic and d.scope == DiscountScope.ITEM and d.is_active]
    code_discounts = [d for d in ctx.discounts[key]
                      if d.code and d.is_active and not d.expires_at and (d.max_uses is None or d.used_count < d.max_uses)]

    for back in range(DAYS - 1, -1, -1):
        day = ctx.today - timedelta(days=back)
        count = rng.randint(*sd["orders_per_day"])
        if day.weekday() >= 5:  # busier weekends
            count = int(count * 1.35)
        times = sorted(
            _utc(day, rng.randint(open_h, close_h - 1), rng.randint(0, 59)) for _ in range(count)
        )
        times = [t for t in times if t <= ctx.now - timedelta(minutes=3)]
        for idx, ts in enumerate(times):
            is_today = back == 0
            online = None
            if sd["online_share"] and rng.random() < sd["online_share"]:
                online = rng.choice(list(sd["channels"]))
            setting = sd["channels"].get(online) if online else None
            lines = _build_lines(ctx, key, online, setting, rng.choices([1, 2, 3, 4], weights=[38, 36, 18, 8])[0])

            dine = (not online) and rng.random() < sd["dine_share"]
            payment = "PLATFORM" if online else _pick(rng, PAYMENT_WEIGHTS)
            discount: Discount | None = None
            code_snapshot = None

            # automatic item discounts (direct orders only)
            if not online:
                for d in auto_discounts:
                    for ln in lines:
                        if line_matches_discount(d, ln["item_id"], ln["category_id"]):
                            amt = calc_line_discount(d, ln["total"])
                            if amt > 0:
                                ln["disc"] += amt
                                ln["total"] -= amt
                                ctx.used[d.id] += 1
            subtotal = sum(ln["total"] for ln in lines)

            order_discount = 0
            if not online and code_discounts and rng.random() < 0.14:
                d = rng.choice(code_discounts)
                if not (d.min_order_amount and subtotal < d.min_order_amount):
                    if d.scope == DiscountScope.ITEM:
                        hit = False
                        for ln in lines:
                            if line_matches_discount(d, ln["item_id"], ln["category_id"]):
                                amt = calc_line_discount(d, ln["total"])
                                if amt > 0:
                                    ln["disc"] += amt
                                    ln["total"] -= amt
                                    order_discount += amt
                                    hit = True
                        subtotal = sum(ln["total"] for ln in lines)
                        discount = d if hit else None
                    else:
                        order_discount = (subtotal * d.value) // 10000 if d.discount_type == DiscountType.PERCENTAGE else min(d.value, subtotal)
                        if d.max_discount_amount is not None and d.discount_type == DiscountType.PERCENTAGE:
                            order_discount = min(order_discount, d.max_discount_amount)
                        discount = d
                    if discount:
                        code_snapshot = discount.code
                        ctx.used[discount.id] += 1

            total = subtotal - order_discount
            service = pb1 = 0
            commission = payout = tax = None
            if online:
                commission = (total * setting[0] + 5000) // 10000
                payout = total - commission
                tax = included_tax(total, store.tax_bp)
            else:
                service, pb1 = direct_order_fees(total, dine, store.service_bp, store.pb1_bp)
                total += service + pb1

            # status by age
            kitchen = None
            if back >= 1:
                status = OrderStatus.CANCELLED if rng.random() < 0.04 else OrderStatus.COMPLETED
                if store.kitchen_enabled and status == OrderStatus.COMPLETED:
                    kitchen = KitchenStatus.SERVED
            else:
                recent = idx >= len(times) - 4
                if recent:
                    status = OrderStatus.CONFIRMED
                    if store.kitchen_enabled:
                        kitchen = rng.choice([KitchenStatus.NEW, KitchenStatus.COOKING, KitchenStatus.READY])
                else:
                    status = OrderStatus.COMPLETED
                    if store.kitchen_enabled:
                        kitchen = KitchenStatus.SERVED
            day_key = ts.astimezone(JKT).date()
            seq[day_key] += 1
            num = f"ORD-{day_key:%Y%m%d}-{seq[day_key]:05d}"
            oid = uuid.uuid4()
            cid = None
            if online:
                prefix = {"GOFOOD": "GF", "GRABFOOD": "GR", "SHOPEEFOOD": "SF"}[online]
                while True:
                    cid = f"{prefix}-{rng.randint(100000, 999999)}"
                    if cid not in channel_ids:
                        channel_ids.add(cid)
                        break
            operator = ctx.users[rng.choice(cashiers)].id
            table = None
            if dine and store.pos_table_enabled:
                table = str(rng.randint(1, store.pos_table_count))
            order = Order(
                id=oid, store_id=store.id, operator_id=operator, discount_id=discount.id if discount else None,
                order_number=num, status=status, payment_method=PaymentMethod(payment), subtotal=subtotal,
                discount_amount=order_discount, total_amount=total, discount_code_snapshot=code_snapshot,
                order_type=None if online else ("DINE_IN" if dine else "TAKE_AWAY"),
                table_number=table,
                customer_name=rng.choice(CUSTOMERS) if (store.pos_customer_name_enabled and not online and rng.random() < 0.3) else None,
                notes=rng.choice(["Tanpa sedotan", "Pisahkan es", "Kurang manis", "Bungkus rapi"]) if rng.random() < 0.08 else None,
                kitchen_status=kitchen, channel=online, channel_order_id=cid,
                app_total=(total if rng.random() > 0.05 else total + 2000) if online else None,
                commission_amount=commission, expected_payout=payout, tax_amount=tax,
                driver_name=rng.choice(DRIVERS) if online else None,
                service_amount=service, pb1_amount=pb1,
                expected_payout_date=(day_key + timedelta(days=setting[2])) if online else None,
                confirmed_at=ts + timedelta(minutes=1), completed_at=(ts + timedelta(minutes=rng.randint(15, 45))) if status == OrderStatus.COMPLETED else None,
                created_at=_naive(ts), updated_at=_naive(ts + timedelta(minutes=20)),
            )
            order_lines = [
                OrderItem(
                    id=uuid.uuid4(), order_id=oid, item_id=ln["item_id"], package_id=ln["package_id"],
                    item_name_snapshot=ln["name"], unit_price_snapshot=ln["unit"], quantity=ln["qty"],
                    addon_total_snapshot=ln["addon_total"], item_discount_amount=ln["disc"], line_total=ln["total"],
                    options_snapshot=ln["options"], addons_snapshot=ln["addons"],
                    is_done=kitchen in (KitchenStatus.SERVED, KitchenStatus.READY) if kitchen else False,
                )
                for ln in lines
            ]
            _record_sale_events(ctx, key, order, lines, ts, status == OrderStatus.CANCELLED)
            out.append({"order": order, "lines": order_lines, "key": key, "ts": ts, "online": online})

    # today's self-orders waiting for the cashier to confirm (stores with self-order on)
    if store.self_order_enabled:
        pend = 3 if key == "kemang" else 0
        for n in range(pend):
            ts = ctx.now - timedelta(minutes=rng.randint(2, 18))
            lines = _build_lines(ctx, key, None, None, rng.choice([1, 2, 3]))
            subtotal = sum(ln["total"] for ln in lines)
            service, pb1 = direct_order_fees(subtotal, True, store.service_bp, store.pb1_bp)
            day_key = ts.astimezone(JKT).date()
            seq[day_key] += 1
            oid = uuid.uuid4()
            table = str(rng.randint(1, store.pos_table_count))
            order = Order(
                id=oid, store_id=store.id, operator_id=None, order_number=f"ORD-{day_key:%Y%m%d}-{seq[day_key]:05d}",
                status=OrderStatus.PENDING, payment_method=PaymentMethod.CASH, subtotal=subtotal, discount_amount=0,
                total_amount=subtotal + service + pb1, service_amount=service, pb1_amount=pb1,
                order_type="DINE_IN", table_number=table, notes=f"Meja {table}",
                created_at=_naive(ts), updated_at=_naive(ts),
            )
            order_lines = [
                OrderItem(id=uuid.uuid4(), order_id=oid, item_id=ln["item_id"], package_id=ln["package_id"],
                          item_name_snapshot=ln["name"], unit_price_snapshot=ln["unit"], quantity=ln["qty"],
                          addon_total_snapshot=ln["addon_total"], item_discount_amount=0, line_total=ln["total"],
                          options_snapshot=ln["options"], addons_snapshot=ln["addons"])
                for ln in lines
            ]
            out.append({"order": order, "lines": order_lines, "key": key, "ts": ts, "online": None})
    return out


def _record_sale_events(ctx: _Ctx, key: str, order: Order, lines: list[dict], ts: datetime, cancelled: bool) -> None:
    """Recipe deductions (matched by ingredient name in this store) and the return when cancelled."""
    store_ings = ctx.ingredients.get(key) or {}
    if not store_ings:
        return
    for ln in lines:
        recipe = RECIPES.get(ln["name"]) if ln["item_id"] else None
        for ing_name, qty in recipe or []:
            ing = store_ings.get(ing_name)
            if not ing:
                continue
            delta = Decimal(qty) * ln["qty"]
            ctx.stock_events[ing.id].append((ts, "SALE", -delta, order.id, f"Order {order.order_number}"))
            if cancelled:
                ctx.stock_events[ing.id].append(
                    (ts + timedelta(minutes=8), "RETURN", delta, order.id, f"Cancelled {order.order_number}")
                )


# ---------------------------------------------------------------------------
# refunds, settlements, stock
# ---------------------------------------------------------------------------

def _gen_refunds(ctx: _Ctx, orders: list[dict]) -> list[OrderRefund]:
    rng = ctx.rng
    refunds: list[OrderRefund] = []
    candidates = [o for o in orders if o["order"].status == OrderStatus.COMPLETED and not o["online"]
                  and o["key"] in ("kemang", "senopati") and ctx.today - o["ts"].astimezone(JKT).date() >= timedelta(days=1)]
    rng.shuffle(candidates)
    for o in candidates[:8]:
        order: Order = o["order"]
        when = o["ts"] + timedelta(hours=1)
        method = "CASH" if order.payment_method == PaymentMethod.CASH else "TRANSFER"
        multi = [ln for ln in o["lines"] if ln.package_id is None and ln.quantity >= 1]
        if len(o["lines"]) >= 2 and multi and rng.random() < 0.6:
            ln = multi[0]
            amount = ln.line_total // ln.quantity if ln.quantity else ln.line_total
            if amount <= 0 or amount >= order.total_amount:
                continue
            ln.void_qty = 1
            refunds.append(OrderRefund(id=uuid.uuid4(), order_id=order.id, store_id=order.store_id,
                                       user_id=order.operator_id, type="VOID", method=method, amount=amount,
                                       reason=rng.choice(REFUND_REASONS), order_item_id=ln.id, quantity=1,
                                       refunded_at=when))
        else:
            amount = max(5000, (order.total_amount // 4 // 1000) * 1000)
            if amount >= order.total_amount:
                continue
            refunds.append(OrderRefund(id=uuid.uuid4(), order_id=order.id, store_id=order.store_id,
                                       user_id=order.operator_id, type="REFUND", method=method, amount=amount,
                                       reason=rng.choice(REFUND_REASONS), refunded_at=when))
        order.refunded_amount += amount
    return refunds


def _gen_settlements(ctx: _Ctx, orders: list[dict]) -> tuple[list[PlatformSettlement], list[tuple[Order, uuid.UUID]]]:
    """Platform payouts for older online orders; recent ones stay outstanding (some overdue)."""
    rng = ctx.rng
    result: list[PlatformSettlement] = []
    links: list[tuple[Order, uuid.UUID]] = []
    by_group: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for o in orders:
        order: Order = o["order"]
        if o["online"] and order.status in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED):
            if order.expected_payout_date and order.expected_payout_date <= ctx.today - timedelta(days=4):
                by_group[(o["key"], o["online"])].append(o)
    for n, ((key, channel), group) in enumerate(sorted(by_group.items())):
        group.sort(key=lambda o: o["order"].expected_payout_date)
        mid = max(1, len(group) // 2)
        for batch_no, batch in enumerate([group[:mid], group[mid:]]):
            if not batch:
                continue
            expected = sum(o["order"].expected_payout for o in batch)
            diff, reason = 0, None
            if batch_no == 0 and n % 2 == 0:
                diff, reason = -12000, "Biaya promo merchant"
            received = batch[-1]["order"].expected_payout_date + timedelta(days=1)
            st = PlatformSettlement(
                id=uuid.uuid4(), store_id=ctx.stores[key].id, user_id=ctx.users[ctx.store_defs[key]["reviewer"]].id,
                channel=channel, received_date=received, amount=expected + diff, expected=expected, diff=diff,
                order_count=len(batch), reason=reason,
            )
            links += [(o["order"], st.id) for o in batch]
            result.append(st)
            if batch_no == 1 and rng.random() < 0.5:
                break
    return result, links


def _gen_stock(ctx: _Ctx, orders: list[dict]) -> list[StockMovement]:
    """Initial stock, restocks sized to the demand ahead, sales/returns from orders, one opname."""
    rng = ctx.rng
    movements: list[StockMovement] = []
    start = _utc(ctx.today - timedelta(days=DAYS), 6)
    for key, ings in ctx.ingredients.items():
        if not ings:
            continue
        owner = ctx.users["owner@demo.com"].id
        for name, ing in ings.items():
            events = sorted(ctx.stock_events.get(ing.id, []), key=lambda e: e[0])
            by_day: dict[int, Decimal] = defaultdict(Decimal)
            for ts, kind, delta, *_ in events:
                if kind == "SALE":
                    by_day[(ctx.today - ts.astimezone(JKT).date()).days] += -delta
            def demand(a: int, b: int) -> Decimal:  # days-ago window [b..a]
                return sum((by_day.get(d, Decimal(0)) for d in range(b, a + 1)), Decimal(0))
            plan = [(DAYS, Decimal(ing.min_stock) + demand(DAYS, 11) * Decimal("1.2"), "INITIAL")]
            for day_ago, lo, hi in ((10, 7, 10), (6, 3, 6), (2, 0, 2)):
                if day_ago == 2 and name in LOW_STOCK:
                    continue  # leave it under min_stock
                plan.append((day_ago, demand(hi, lo) * Decimal("1.2"), "RESTOCK"))
            for day_ago, qty, kind in plan:
                qty = max(qty.quantize(Decimal("1")), Decimal(1))
                ts = _utc(ctx.today - timedelta(days=day_ago), 6 if kind == "INITIAL" else 7, 30)
                events.append((ts, kind, qty, None, "Stok awal" if kind == "INITIAL" else "Terima barang supplier"))
            if name == "Biji Kopi Arabica":  # one stock-count correction
                events.append((_utc(ctx.today - timedelta(days=5), 22), "OPNAME", Decimal(-120), None, "Stock opname"))
            events.sort(key=lambda e: e[0])
            if name in LOW_STOCK:  # spoilage found at the last count leaves it under min_stock
                final = sum((e[2] for e in events), Decimal(0))
                target = (Decimal(ing.min_stock) * Decimal("0.4")).quantize(Decimal("1"))
                if final > target:
                    events.append((ctx.now - timedelta(minutes=30), "OPNAME", target - final, None, "Stock opname: barang rusak"))
                    events.sort(key=lambda e: e[0])
            balance = Decimal(0)
            for ts, kind, delta, order_id, note in events:
                balance += delta
                movements.append(StockMovement(
                    id=uuid.uuid4(), store_id=ing.store_id, ingredient_id=ing.id, order_id=order_id,
                    user_id=owner if order_id is None else None, type=kind, quantity=delta,
                    balance_after=balance, note=note, created_at=_naive(ts), updated_at=_naive(ts),
                ))
            ing.stock = balance
    return movements


# ---------------------------------------------------------------------------
# shifts, cash movements, expenses
# ---------------------------------------------------------------------------

def _gen_shifts_and_expenses(ctx: _Ctx, orders: list[dict], refunds: list[OrderRefund]) -> dict:
    rng = ctx.rng
    objects: list = []
    movements: list = []
    n_shifts = n_exp = n_mv = 0
    for sd in STORES:
        key = sd["key"]
        store: Store = ctx.stores[key]
        cashiers = sd["cashiers"]
        reviewer = ctx.users[sd["reviewer"]].id
        threshold = store.shift_variance_threshold
        store_orders = [o["order"] for o in orders if o["key"] == key]
        store_refunds = [r for r in refunds if r.store_id == store.id]
        prev_counted = store.default_float
        big_days = {5, 9} if key == "kemang" else ({7} if key == "senopati" else set())
        for back in range(DAYS - 1, -1, -1):
            day = ctx.today - timedelta(days=back)
            opened = _utc(day, 7, 45)
            if opened > ctx.now - timedelta(minutes=5):
                opened = ctx.now - timedelta(minutes=5)
            is_today = back == 0
            if is_today and key == "bsd":
                continue  # BSD has no open shift today
            closed = None if is_today else _utc(day, sd["hours"][1] + 1, 10)
            email = cashiers[(back + len(key)) % len(cashiers)]
            cashier = ctx.users[email].id
            opening = prev_counted if rng.random() < 0.8 else prev_counted + rng.choice([-5000, 5000])
            shift = Shift(
                id=uuid.uuid4(), store_id=store.id, opened_by=cashier, opened_at=opened, opening_cash=opening,
                carry_expected=prev_counted, status="OPEN",
                created_at=_naive(opened), updated_at=_naive(opened),
            )
            n_shifts += 1
            window_end = closed or ctx.now
            cin = cout = 0
            if rng.random() < 0.55 or is_today:
                cat, reason, amt = rng.choice(CASH_OUTS)
                at = opened + timedelta(hours=rng.randint(2, 6))
                if at < window_end:
                    exp = None
                    if cat in EXPENSE_CATEGORIES:
                        exp = Expense(id=uuid.uuid4(), store_id=store.id, user_id=cashier, date=day, category=cat,
                                      description=reason, amount=amt, source="DRAWER", status="POSTED",
                                      created_at=_naive(at), updated_at=_naive(at))
                        objects.append(exp)
                        n_exp += 1
                    movements.append(CashMovement(id=uuid.uuid4(), shift_id=shift.id, user_id=cashier, type="OUT",
                                                amount=amt, category=cat, reason=reason,
                                                expense_id=exp.id if exp else None,
                                                created_at=_naive(at), updated_at=_naive(at)))
                    cout += amt
                    n_mv += 1
            if rng.random() < 0.25:
                at = opened + timedelta(hours=1)
                movements.append(CashMovement(id=uuid.uuid4(), shift_id=shift.id, user_id=cashier, type="IN", amount=100000,
                                            category="Tambah kembalian", reason="Pecahan Rp5.000 dari kas kecil",
                                            created_at=_naive(at), updated_at=_naive(at)))
                cin += 100000
                n_mv += 1
            sales = sum(o.total_amount for o in store_orders
                        if o.payment_method == PaymentMethod.CASH and o.status in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED)
                        and o.confirmed_at and opened <= o.confirmed_at < window_end)
            cash_refunds = sum(r.amount for r in store_refunds if r.method == "CASH" and opened <= r.refunded_at < window_end)
            expected = opening + sales - cash_refunds + cin - cout
            if not is_today:
                variance = 0 if rng.random() < 0.65 else rng.choice([-3000, 2000, -6000, 4000, 1000])
                note = None
                if back in big_days:
                    variance = rng.choice([-45000, -38000])
                    note = "Uang kembalian salah hitung"
                    if abs(variance) <= threshold:
                        variance = -(threshold + 20000)
                counted = expected + variance
                shift.closed_by = cashier
                shift.closed_at = closed
                shift.counted_cash = counted
                shift.expected_cash = expected
                shift.variance = variance
                shift.note = note
                waiting = back <= 2 or back in big_days and back <= 5  # recent days still await review
                shift.status = "CLOSED" if waiting else "REVIEWED"
                if shift.status == "REVIEWED":
                    shift.reviewed_by = reviewer
                    shift.review_note = "Sudah dicek, sesuai catatan kasir" if note else None
                prev_counted = counted
            objects.append(shift)

        # operating expenses (bank / e-wallet / petty) + recurring drafts
        scale = {"kemang": 1.0, "senopati": 0.7, "bsd": 0.45}[key]
        month_start = ctx.today.replace(day=1)
        last_month = (month_start - timedelta(days=1)).replace(day=1)
        monthly = [
            ("Sewa", "Sewa tempat", int(15_000_000 * scale), "BANK", True),
            ("Listrik & air", "Tagihan listrik & air", int(2_350_000 * scale), "BANK", False),
            ("Gaji & upah", "Gaji karyawan", int(12_500_000 * scale), "BANK", True),
            ("Internet & software", "Internet & langganan POS", int(450_000 * scale), "EWALLET", True),
        ]
        for base in (last_month, month_start):
            for cat, desc, amt, source, recurring in monthly:
                d = min(base + timedelta(days=rng.randint(0, 3)), ctx.today)
                if d > ctx.today:
                    continue
                objects.append(Expense(id=uuid.uuid4(), store_id=store.id, user_id=ctx.users["owner@demo.com"].id,
                                       date=d, category=cat, description=desc, amount=amt, source=source,
                                       recurring=recurring, status="POSTED"))
                n_exp += 1
        for cat, desc, amt, source in (
            ("Marketing", "Iklan Instagram", int(750_000 * scale), "EWALLET"),
            ("Perbaikan & perawatan", "Servis AC", int(300_000 * scale), "PETTY"),
            ("Transport", "Bensin kurir bahan", int(180_000 * scale), "PETTY"),
        ):
            objects.append(Expense(id=uuid.uuid4(), store_id=store.id, user_id=ctx.users[cashiers[0]].id,
                                   date=ctx.today - timedelta(days=rng.randint(2, 12)), category=cat, description=desc,
                                   amount=amt, source=source, status="POSTED"))
            n_exp += 1
        # drafts generated by the recurring expenses
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        for cat, desc, amt, source, recurring in monthly:
            if recurring:
                objects.append(Expense(id=uuid.uuid4(), store_id=store.id, user_id=ctx.users["owner@demo.com"].id,
                                       date=next_month + timedelta(days=1), category=cat, description=desc, amount=amt,
                                       source=source, recurring=True, status="DRAFT"))
                n_exp += 1
    return {"objects": objects, "movements": movements, "shifts": n_shifts, "expenses": n_exp, "cash_movements": n_mv}
