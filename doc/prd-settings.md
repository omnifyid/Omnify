# PRD: Settings

Page `/settings` (Owner and Manager).  The save button floats at the bottom of the form and stays visible while scrolling. Tabs; the active tab is `?tab=` (default Modul).

| Tab | Content | Who |
|-----|---------|-----|
| **Modul** | Feature cards with an on/off switch; each switch saves immediately | Owner, Manager (Self order: Owner) |
| **Outlet** | One card per outlet with an Induk (parent) or Cabang (branch) badge, the parent it follows, address, phone, PB1 and service charge; "Ubah" expands the card to edit name, address, phone and (Owner) service charge and PB1, each a switch that reveals the percentage; an open/closed switch on every card (Owner, Manager); "Tambah cabang" opens a dialog | Owner, Manager (branches: Owner) |
| **Nota** | Paper width, what the customer receipt and kitchen ticket print, a Nota pelanggan / Tiket dapur switch that shows only that output's settings (paper width appears in both) next to its live preview | Owner, Manager |
| **Kasir** | Dine-in option, table count, customer name | Owner, Manager |
| **Pembayaran** | Switch per method (Tunai, EDC, QRIS, Transfer); EDC banks and QRIS providers (banks and e-wallets) picked from presets or added by name | Owner, Manager |
| **Kanal penjualan** | Online platforms (commission, markup, payout lag) and included tax | Owner |
| **Kebijakan** | Expense categories (chips: add by name, remove, reset to default), cash-difference limit and default opening cash | Owner |

The Nota, Kasir, Outlet, Kanal and Kebijakan tabs share one Save button. The Modul tab has none; the Outlet tab has its own Simpan and Batal inside the expanded card.

## Modules

| Card | Field | Off means |
|------|-------|-----------|
| Self order QR | `stores.selforder_is_open` | The public menu stops taking orders. Needs `self_order_enabled`, which the super admin sets; otherwise the card shows "Diaktifkan oleh admin" |
| Nomor meja | `pos_table_enabled` | No table picker in the POS |
| Manajemen Dapur | `kitchen_enabled` | No kitchen board or kitchen status, see [prd-kitchen.md](prd-kitchen.md) |
| Inventaris | `inventory_enabled` (default on) | Menu hidden and sales stop deducting ingredient stock; existing stock data is kept |
| Keuangan | `finance_enabled` (default on) | Keuangan menu and the shift chip are hidden; data is kept |

`PATCH /stores/{id}` accepts `inventory_enabled` and `finance_enabled` (Owner or Manager). A page of a switched-off module sends the user back to the dashboard.

## Receipt options (tab Nota)

`stores.receipt_options` (JSON, schema `ReceiptOptions`; missing keys use the defaults, all on):

| Option | Meaning |
|--------|---------|
| `paper` | `58` (32 characters per line) or `80` (48). Sets the preview width, the browser print page size and the ESC/POS line width |
| `show_addr`, `show_phone` | Store address and phone (fields `stores.address`, `stores.phone`, set in the Toko tab) |
| `show_cashier`, `show_cust`, `show_no`, `show_mods`, `show_tax`, `show_pay` | Cashier name, customer name, order number, item options and notes, service and PB1 lines, payment method with cash and change |
| `k_title`, `k_outlet`, `k_server`, `k_cust` | Kitchen ticket title (default "Pesanan Baru"), store name, "Dilayani oleh", customer name. Item options and notes always print |

The change line comes from `orders.cash_received`, sent by the POS cash payment (`cash_received` must cover the total; ignored for other methods). `OrderRead` returns `operator_name` for the cashier lines.

All outputs render one document from `$lib/utils/receipt.ts` (`customerReceipt`, `kitchenTicket`): the settings preview, the receipt and ticket modals (`ReceiptView.svelte`, browser print) and the ESC/POS bytes (`escpos.ts`). Guest count is not recorded.

## Outlet open / closed

`stores.is_open` (default true) is a temporary switch, separate from `is_active` (removed) and `selforder_is_open` (QR menu only). While closed, `order_service.create_order` returns 400 "Outlet is closed" for POS, online and QR orders. The outlet stays in every list and can be reopened from the Outlet tab; reads and reports are unaffected.

## Payment methods (tab Pembayaran)

`stores.payment_options` (JSON, schema `PaymentOptions`; null = everything on, no variants): `cash`, `transfer` (bool), `edc` and `qris` (`{enabled, options[]}`).

- The POS lists only enabled methods. When EDC or QRIS has options, the cashier picks one (first preselected) and it is stored in `orders.payment_provider`; with no options nothing is asked.
- `order_service` rejects a switched-off method and a provider outside the list (400) for staff orders. QR self-orders (always cash) and online platform orders skip the check.
- Receipts and the transaction views show `QRIS · GoPay` style text (`paymentText`). Reports still group by `payment_method`.
