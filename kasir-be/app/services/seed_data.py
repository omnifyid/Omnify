"""Menu catalog used by the demo seed (categories, items, options, add-ons)."""

# (name, sort_order)
CATEGORIES = [
    ("Kopi Panas", 1),
    ("Kopi Dingin", 2),
    ("Non-Kopi", 3),
    ("Makanan", 4),
    ("Snack", 5),
]

# (name, base_price_rupiah, category_index, sort_order)
ITEMS = [
    # Kopi Panas
    ("Espresso", 18_000, 0, 1),
    ("Americano", 20_000, 0, 2),
    ("Cappuccino", 25_000, 0, 3),
    ("Latte", 27_000, 0, 4),
    ("Flat White", 28_000, 0, 5),
    ("Macchiato", 26_000, 0, 6),
    # Kopi Dingin
    ("Iced Americano", 22_000, 1, 1),
    ("Iced Latte", 29_000, 1, 2),
    ("Iced Cappuccino", 27_000, 1, 3),
    ("Cold Brew", 30_000, 1, 4),
    ("Es Kopi Susu", 25_000, 1, 5),
    ("Kopi Gula Aren", 27_000, 1, 6),
    # Non-Kopi
    ("Teh Tarik", 18_000, 2, 1),
    ("Matcha Latte", 28_000, 2, 2),
    ("Coklat Panas", 22_000, 2, 3),
    ("Iced Matcha", 30_000, 2, 4),
    ("Yuzu Tea", 25_000, 2, 5),
    ("Strawberry Smoothie", 32_000, 2, 6),
    # Makanan
    ("Nasi Goreng Spesial", 35_000, 3, 1),
    ("Sandwich Ayam Crispy", 30_000, 3, 2),
    ("Pasta Carbonara", 45_000, 3, 3),
    ("Waffle Butter Maple", 28_000, 3, 4),
    ("Roti Bakar Keju", 22_000, 3, 5),
    # Snack
    ("Kentang Goreng", 20_000, 4, 1),
    ("Croissant Mentega", 18_000, 4, 2),
    ("Donat Glazed", 12_000, 4, 3),
    ("Kue Lapis Legit", 15_000, 4, 4),
    ("Pisang Goreng Keju", 18_000, 4, 5),
]

# Option groups per item name.
# Each entry: (group_name, is_required, [(label, is_default), ...])
ITEM_OPTIONS: dict[str, list[tuple[str, bool, list[tuple[str, bool]]]]] = {
    # ── Kopi Panas ──────────────────────────────────────────────────────────
    "Espresso": [
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Americano": [
        ("Temperature", True, [("Hot", True), ("Warm", False), ("Extra Hot", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Cappuccino": [
        ("Temperature", True, [("Hot", True), ("Warm", False), ("Extra Hot", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Latte": [
        ("Temperature", True, [("Hot", True), ("Warm", False), ("Extra Hot", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Flat White": [
        ("Temperature", True, [("Hot", True), ("Warm", False), ("Extra Hot", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Macchiato": [
        ("Temperature", True, [("Hot", True), ("Warm", False), ("Extra Hot", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    # ── Kopi Dingin ─────────────────────────────────────────────────────────
    "Iced Americano": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Iced Latte": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Iced Cappuccino": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Cold Brew": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", False, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Es Kopi Susu": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Kopi Gula Aren": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    # ── Non-Kopi ────────────────────────────────────────────────────────────
    "Teh Tarik": [
        ("Temperature", True, [("Hot", True), ("Iced", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Matcha Latte": [
        ("Temperature", True, [("Hot", True), ("Iced", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Coklat Panas": [
        ("Temperature", True, [("Hot", True), ("Warm", False), ("Extra Hot", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Iced Matcha": [
        ("Ice Level", True, [("Normal Ice", True), ("Less Ice", False), ("No Ice", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
        ("Milk Type", False, [("Full Cream", True), ("Oat Milk", False), ("Almond Milk", False)]),
    ],
    "Yuzu Tea": [
        ("Temperature", True, [("Hot", True), ("Iced", False)]),
        ("Sugar Level", True, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    "Strawberry Smoothie": [
        ("Sugar Level", False, [("Normal", True), ("Less Sugar", False), ("No Sugar", False)]),
    ],
    # ── Makanan ─────────────────────────────────────────────────────────────
    "Nasi Goreng Spesial": [
        ("Spice Level", True, [("Normal", True), ("Pedas", False), ("Extra Pedas", False)]),
        ("Egg Style", True, [("Telur Ceplok", True), ("Telur Dadar", False), ("No Egg", False)]),
    ],
    "Sandwich Ayam Crispy": [
        ("Bread Type", True, [("White Bread", True), ("Whole Wheat", False)]),
        ("Spice Level", False, [("Original", True), ("Spicy", False)]),
    ],
    "Pasta Carbonara": [
        ("Pasta Type", True, [("Spaghetti", True), ("Fettuccine", False), ("Penne", False)]),
    ],
    "Waffle Butter Maple": [
        ("Topping", True, [("Maple Syrup", True), ("Chocolate", False), ("Strawberry Jam", False)]),
    ],
    "Roti Bakar Keju": [
        ("Topping", True, [("Keju", True), ("Coklat Keju", False), ("Srikaya", False)]),
        ("Thickness", False, [("Normal", True), ("Tebal", False)]),
    ],
    # ── Snack ───────────────────────────────────────────────────────────────
    "Kentang Goreng": [
        ("Size", True, [("Regular", True), ("Large", False)]),
        ("Seasoning", True, [("Original", True), ("BBQ", False), ("Balado", False), ("Keju", False)]),
    ],
    "Pisang Goreng Keju": [
        ("Topping", True, [("Keju", True), ("Coklat", False), ("Keju + Coklat", False)]),
    ],
}


# Addon groups per item name.
# Each entry: (group_name, is_required, min_select, max_select, [(label, extra_price), ...])
ITEM_ADDONS: dict[str, list[tuple[str, bool, int, int | None, list[tuple[str, int]]]]] = {
    # ── Kopi Panas ──────────────────────────────────────────────────────────
    "Espresso": [
        ("Extra Shot", False, 0, 2, [("Single Shot", 0), ("Double Shot", 8_000)]),
    ],
    "Americano": [
        ("Extra Shot", False, 0, 2, [("Single Shot", 0), ("Double Shot", 8_000)]),
        ("Milk Add-on", False, 0, 1, [("Susu Full Cream", 5_000), ("Oat Milk", 10_000)]),
    ],
    "Cappuccino": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000), ("Hazelnut", 5_000), ("Caramel", 5_000)]),
    ],
    "Latte": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000), ("Hazelnut", 5_000), ("Caramel", 5_000)]),
    ],
    "Flat White": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
    ],
    "Macchiato": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000), ("Caramel", 5_000)]),
    ],
    # ── Kopi Dingin ─────────────────────────────────────────────────────────
    "Iced Americano": [
        ("Extra Shot", False, 0, 2, [("Single Shot", 0), ("Double Shot", 8_000)]),
        ("Milk Add-on", False, 0, 1, [("Susu Full Cream", 5_000), ("Oat Milk", 10_000)]),
    ],
    "Iced Latte": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000), ("Hazelnut", 5_000), ("Caramel", 5_000)]),
    ],
    "Iced Cappuccino": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
    ],
    "Cold Brew": [
        ("Milk Add-on", False, 0, 1, [("Susu Full Cream", 5_000), ("Oat Milk", 10_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000), ("Caramel", 5_000)]),
    ],
    "Es Kopi Susu": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000)]),
    ],
    "Kopi Gula Aren": [
        ("Extra Shot", False, 0, 1, [("Double Shot", 8_000)]),
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000)]),
    ],
    # ── Non-Kopi ────────────────────────────────────────────────────────────
    "Matcha Latte": [
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000), ("Hazelnut", 5_000)]),
    ],
    "Iced Matcha": [
        ("Milk Upgrade", False, 0, 1, [("Oat Milk", 10_000), ("Almond Milk", 12_000)]),
        ("Syrup", False, 0, 1, [("Vanilla", 5_000)]),
    ],
    "Coklat Panas": [
        ("Topping", False, 0, 2, [("Whipped Cream", 5_000), ("Marshmallow", 5_000), ("Coklat Chips", 3_000)]),
    ],
    "Strawberry Smoothie": [
        ("Topping", False, 0, 2, [("Whipped Cream", 5_000), ("Granola", 8_000), ("Chia Seeds", 5_000)]),
    ],
    # ── Makanan ─────────────────────────────────────────────────────────────
    "Nasi Goreng Spesial": [
        ("Extras", False, 0, 3, [("Tambah Kerupuk", 2_000), ("Tambah Acar", 2_000), ("Tambah Sate Ayam", 15_000)]),
        ("Protein Tambahan", False, 0, 1, [("Ayam Goreng", 12_000), ("Udang", 15_000), ("Bakso", 8_000)]),
    ],
    "Sandwich Ayam Crispy": [
        ("Extras", False, 0, 3, [("Extra Keju", 5_000), ("Extra Saus", 3_000), ("Extra Selada", 3_000)]),
    ],
    "Pasta Carbonara": [
        ("Extra Topping", False, 0, 2, [("Extra Bacon", 12_000), ("Extra Parmesan", 8_000), ("Extra Mushroom", 8_000)]),
        ("Portion", False, 0, 1, [("Extra Large", 10_000)]),
    ],
    "Waffle Butter Maple": [
        ("Extra Topping", False, 0, 3, [("Whipped Cream", 5_000), ("Ice Cream", 12_000), ("Fresh Strawberry", 10_000), ("Banana", 8_000)]),
    ],
    "Roti Bakar Keju": [
        ("Extra Topping", False, 0, 2, [("Extra Keju", 5_000), ("Extra Butter", 3_000), ("Meses", 3_000)]),
    ],
    # ── Snack ───────────────────────────────────────────────────────────────
    "Kentang Goreng": [
        ("Saus", False, 0, 3, [("Saus Tomat", 2_000), ("Mayonaise", 3_000), ("BBQ Sauce", 3_000), ("Cheese Sauce", 5_000)]),
    ],
    "Croissant Mentega": [
        ("Filling", False, 0, 2, [("Keju", 5_000), ("Ham", 8_000), ("Coklat", 5_000), ("Selai Stroberi", 5_000)]),
    ],
    "Pisang Goreng Keju": [
        ("Extra Topping", False, 0, 2, [("Extra Keju", 5_000), ("Extra Coklat", 5_000), ("Meses", 3_000)]),
    ],
}
