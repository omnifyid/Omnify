# Handoff: Omnify — POS & Back-office for cafés (multi-outlet)

## Overview
Omnify is a POS and back-office suite for a multi-outlet café brand (demo tenant: **Kopi Senja**, outlets Kemang, Senopati, BSD). One responsive web app covers: PIN lock screen, dashboard, cashier (POS) with payment, order list, QR self-order, table map, kitchen display (KDS) and recipes, products, discounts, inventory, purchasing, finance (shifts/cash, expenses, payables, platform payouts), staff, audit log, reports and settings. All UI copy is **Bahasa Indonesia** and money is **Rupiah**.

## About the design files
The files in this bundle are **design references built in HTML**: prototypes that show the intended look and behaviour. They are not production code to copy. Rebuild the UI in your target stack (recommended: React + TypeScript, Next.js or Vite, Tailwind or CSS variables, a real backend/DB) using that stack's patterns. The prototype keeps all data in `localStorage` and computes everything client-side; production needs a server, auth and a database.

`Omnify.dc.html` opens directly in a browser (keep `support.js`, `omnify-data.js`, `omnify-store.js` beside it). Its markup is the source of truth for exact spacing and colour; this README summarises it.

## Fidelity
**High-fidelity.** Colours, type, spacing, radii, states and copy are final. Recreate pixel-accurately. Copy text is final; keep it verbatim.

---

## 1. Design tokens

A ready-to-use CSS variable file is in `tokens.css`.

### Colour — neutrals
| Token | Hex | Use |
|---|---|---|
| `ink` | `#10140F` | Primary text, dark surfaces, primary-dark buttons, focus of selection borders |
| `ink-2` | `#3B3F38` | Body text in dense rows, non-active nav labels |
| `text-secondary` | `#4A4E47` | Secondary text, labels, icons (≥7:1 on bg) |
| `bg` | `#F6F5F1` | App background, header |
| `surface` | `#FFFFFF` | Cards, panels, inputs, modals |
| `surface-sunk` | `#FBFAF7` | Sidebar, table header rows, totals rows, bottom tab bar |
| `fill-muted` | `#F1F0EC` | Segmented-control track, icon tiles, inactive pill |
| `fill-hover` | `#EFEEE9` | Nav hover, pressed KPI |
| `fill-image` | `#EEF0EA` | Image placeholder bg, progress track |
| `border` | `#E7E5DF` | Default 1px border on cards, inputs, buttons |
| `divider` | `#F0EEE9` | Row separators inside cards |
| `border-strong` | `#D7D5CE` | Input border, off toggle track |
| `grey-tint` | `#EDECE7` | Grey status pill bg |

### Colour — brand & status (text colours are AAA on white)
| Role | Text / solid | Tint bg | Notes |
|---|---|---|---|
| Brand / success | `#1F5C12` | `#E6F4DF` (hover `#DCEFD3`) | Primary buttons bg, links, active nav icon, focus ring |
| Brand bright | `#45A02E` | `#EEF7EA` / border `#CFE7C4` | Live dots, chart bars, toggle on, logo on light bg |
| Brand on dark | `#7ED76A` | — | Accent on `#10140F` (logo, badges in dark chips) |
| Warning | `#6A4400` | `#FBF1DC` | Amber pills, "low stock" |
| Warning solid | `#E0A526` | — | KDS "Diproses" dot only |
| Danger | `#8E1A14` | `#FCE9E6` | Destructive text, errors, "Habis" badge |
| Danger solid | `#D64535` | — | Notification count badges (white text) |
| Info | `#1F4A8F` | `#EAF0FB` | "Berjalan", "Dalam perjalanan" pills |
| On dark | `#EAF3E6` primary, `#A9B3A5` secondary | on `#10140F` | Lock-screen left panel |

Delivery channel marks (32px circle, white 12px/800 text): GoFood `#9E1B2F` "GF" (tint `#FBEFF1`), GrabFood `#14633A` "GR" (`#EAF5EE`), ShopeeFood `#9A3412` "SF" (`#FCF0E8`).

Scrim: `rgba(16,20,15,.42)`. Shift-gate overlay: `rgba(246,245,241,.92)` + `backdrop-filter: blur(3px)`.

### Typography
- **UI font:** Geist (Google Fonts) 400/500/600/700. Fallback `system-ui, sans-serif`.
- **Logo font:** JetBrains Mono 800, letter-spacing −0.03em. Only for the `>omnify▌` wordmark.
- **Icons:** Material Symbols Rounded (variable; `FILL` 0 default, 1 for active nav/tab).
- All numbers, money, times, IDs: `font-variant-numeric: tabular-nums`.

| Style | Size / weight | Use |
|---|---|---|
| Display | 44px / 600, lh 1.08, ls −0.02em | Lock screen headline |
| KPI | 24px / 700, ls −0.02em (20px mobile) | Dashboard numbers |
| Page title | 20px / 600, ls −0.01em | Header title |
| H-modal | 20px / 600 | Dialog titles, big money inputs (700) |
| Section | 16px / 600 | Card titles, group headers |
| Body | 16px / 400–500 | Default text, list rows, form inputs |
| Control | 14px / 500–600 | Buttons, chips, segmented controls, header chips (date, shift, outlet, user name) |
| Meta | 12px / 400–600 | Labels, captions, pills, table headers |

**Type scale is fixed:** 12 · 14 · 16 · 20 · 24 · 28 · 32 · 36 · 40 · 44 · 48 · 56 px. Do not use any other size. Browsers default buttons to 13.33px, so set the global reset `button { font-size: 14px }` and `input, select, textarea { font-size: 16px }` (16px also prevents iOS zoom), then override per element only to another size on the scale. Body line-height 1.4; paragraphs 1.45–1.55; controls 1.3.

### Radius
`6px` small badges · `8px` small row buttons · `10px` buttons, nav items, header controls · `11–12px` inputs, primary buttons, icon tiles · `14px` **cards (default)**, menu tiles, popovers · `18px` dialogs (desktop) · `20px` pills/chips · `22px 22px 0 0` mobile bottom sheets · `50%` avatars, dots.

### Shadow
| Name | Value | Use |
|---|---|---|
| hover | `0 4px 14px rgba(16,20,15,.08)` | Clickable KPI hover |
| popover | `0 16px 40px rgba(16,20,15,.14)` | Bell, outlet, shift menus |
| dialog | `0 20px 60px rgba(16,20,15,.25)` | Modals & sheets |
| drawer | `-12px 0 40px rgba(16,20,15,.15)` | Right detail drawers |
| floating | `0 10px 24px rgba(16,20,15,.28)` | Mobile cart bar |
| rail-expand | `8px 0 28px rgba(16,20,15,.12)` | Expanded icon rail on tablet |

Cards use **border, not shadow** (`1px solid #E7E5DF`).

### Spacing
4-based scale used: 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 28. Card padding 20px (KPI 18px / 14px mobile). Grid gaps 12–14px. Page padding 24px desktop → 16px tablet → 12px mobile (`pagePad`).

### Motion
- `omUp`: `opacity 0 → 1, translateY(8px) → 0`, .2–.4s ease. Used for popovers, dialogs, toasts, cart bar.
- `omBlink`: logo cursor block, 1.1s `steps(1)` infinite.
- Rail expand: `width .32s cubic-bezier(.2,.8,.2,1)`; labels fade `opacity .2s ease .12s`.
- Nav hover background `.15s ease`.
- **`prefers-reduced-motion: reduce` disables all animation and transitions.**

---

## 2. Accessibility rules (WCAG 2.2 AAA baseline — non-negotiable)
- Hit targets: **44×44 px desktop (≥1200), 48×48 px tablet/mobile**. In the prototype this is the `tap` variable; every button, chip, nav item, icon button, link-button and row uses `min-height: var(--tap)`. Keep ≥8px between adjacent targets.
- Contrast: body text ≥7:1, large ≥4.5:1, meaningful UI borders/icons ≥3:1. Never mute text with opacity.
- Focus: `:focus-visible { outline: 3px solid #1F5C12; outline-offset: 2px; border-radius: 6px }`.
- Every action reachable via Tab, operable with Enter/Space. Modals trap focus, close on Esc and always have a visible close control. Use `role="dialog" aria-modal="true"`, `role="menu"/"menuitem"`, `aria-haspopup`, `role="alert"` for errors.
- Status is never colour-only: every pill has a text label; alerts have an icon (`warning`/`error`).
- Scrollbars are hidden visually in the prototype; keep scroll areas keyboard-scrollable.

---

## 3. Responsive layout

| Breakpoint | Width | Navigation | Notes |
|---|---|---|---|
| Desktop | ≥1200 | Full sidebar 244px | tap 44px; cart 390px |
| Tablet | 768–1199 | Icon rail 84px; tap expands to 244px overlay (with shadow), auto-collapses | tap 48px; cart 340px; drawers overlay content when <1000 |
| Cards | <1000 | — | Wide tables become stacked cards (labels shown per cell); outlet comparison drops to 3 columns |
| Mobile | <768 | **Bottom tab bar** (max 4 primary + "Lainnya") | Dialogs become bottom sheets; cart becomes full-screen with floating cart bar; KDS shows one column with column tabs |

Fixed bottom UI respects `env(safe-area-inset-bottom)`.

### App shell
```
┌ Sidebar 244 ┬──────────── main (flex:1) ─────────────┐
│ logo        │ Header 64–72px, border-bottom           │
│ outlet card │ [title/sub] [date·clock] [bell] [shift] │
│ nav groups  │ [outlet btn] [user avatar]              │
│ …           ├─────────────────────────────────────────┤
│ Kunci kasir │ Page content (scrolls)                  │
└─────────────┴─────────────────────────────────────────┘
```

**Sidebar** (`#FBFAF7`, right border, padding 20px 12px): wordmark (24px, green `#45A02E` caret + blinking cursor) → outlet switcher card (white, 12px radius, 30px dark logo tile, name 12/600, sub 12 secondary, `unfold_more` icon if switchable) → nav. Group headers 12px secondary (desktop) or 1px dividers (rail). Nav item: min-height tap, padding 9px 10px, radius 10px, gap 11px, 24px icon.
- Default: text `#3B3F38`, icon `#4A4E47`, weight 500, hover bg `#EFEEE9`.
- Active: bg `#E6F4DF`, text `#10140F` 600, icon `#1F5C12` filled, hover `#DCEFD3`.
- Badge: 12/700 pill, red (`#FCE9E6`/`#8E1A14`) or amber (`#FBF1DC`/`#6A4400`); absolute top-right on rail.
- Footer: "Kunci kasir" (lock icon) above a top border.

Nav groups and items (icon in brackets):
- **Operasional:** Ringkasan [space_dashboard], Kasir [point_of_sale], Pesanan [receipt_long, red badge = pending self-orders], Self Order [qr_code_2], Meja [table_restaurant], Dapur & Bar [coffee_maker]
- **Menu:** Produk [local_cafe], Diskon [sell]
- **Gudang:** Inventaris [inventory_2, amber badge = low stock], Pembelian [local_shipping]
- **Keuangan:** Keuangan [account_balance_wallet, red badge = overdue payables]
- **Tim & analitik:** Karyawan [badge], Log aktivitas [history], Laporan [monitoring], Pengaturan [settings]

Items hide when the role lacks access or the module is switched off (see §6).

**Header controls** (all height tap, radius 10, 1px border, white, text 14px/600): date·clock chip with green live dot; bell (red count badge −5px offset); shift chip (green tint `#EEF7EA`, border `#CFE7C4`) only on Kasir; outlet button on tablet; user avatar pill (36px circle `#E6F4DF`/`#1F5C12`, role 12px + name 16/600 on desktop).

**Mobile tab bar:** `#FBFAF7`, top border, grid of N equal cells, cell height 54px, icon inside a 48×30 pill (active `#E6F4DF`, filled icon), label 12px. "Lainnya" opens a sheet of the remaining modules as tiles.

**Toast:** bottom-center (28px from bottom desktop, 88px mobile). Tones `ok` (2.6s) and `warn` (4.2s). Every action shows one.

---

## 4. Screens

Common patterns: page header comes from the shell; content padding `pagePad`; sub-pages use a **segmented control** (track `#F1F0EC`, 4px padding, radius 11; active segment `#E6F4DF` bg + `inset 0 0 0 2px #1F5C12`, text `#10140F`).

### 4.1 Lock screen (PIN)
Desktop/tablet: 2-column grid. Left dark panel (`#10140F`, padding 48/56): wordmark 32px, outlet name 12px green, headline "Pesanan, bar, dan stok dalam satu tempat." 44px, sub "Masuk dengan PIN staf untuk membuka kasir.", footer "Kasir 01 · clock". Right: centered 360px column — "Siapa yang bertugas?" 24/600, staff grid 3-col (white tiles, 42px avatar, name/role, selected border 1.5px ink), 4 PIN dots (14px, ink border, filled when typed), error `role=alert` danger text, 3×4 keypad (height `clamp(44px,7vh,58px)`, radius 14, pressed `#EEF0EA`). Mobile: dark brand bar on top instead of left panel. Wrong PIN → error message, dots reset.

### 4.2 Ringkasan (Dashboard) — Owner/Manajer
1. KPI grid `repeat(auto-fit, minmax(180px,1fr))` (140px mobile): label 12 secondary + icon, value 24/700, note 12 (coloured by tone). Clickable KPIs deep-link (e.g. "Transaksi" → Pesanan today, "Stok menipis" → Inventaris low) with hover border ink + shadow.
2. **Outlet comparison table** (only "Semua outlet" view): columns Outlet / Penjualan bersih / Transaksi / Rata-rata / Online / Selisih kas / Shift sekarang; total row on `#FBFAF7`. Row click switches outlet.
3. Two-up grid `minmax(min(100%,420px),1fr)`: Antrean pesanan (order no, location, items, timer, status pill) · Metode pembayaran table (dot, method, count, amount, share, total) · Stok menipis (with "Terima" button) · Refund & void list.
4. Perkiraan stok habis — forecast from 7-day usage; per-row action and "Buat PO" for all.
5. Penjualan per jam bar chart (200px tall, bars max 34px wide, radius 6 top, `#45A02E`, current hour highlighted) · Menu terlaris (40px thumb, name, count, 5px progress bar).
Each card has an empty state sentence.

### 4.3 Kasir (POS)
Layout: menu (flex:1, padding `posPad`) + cart panel (390 / 340 / full-screen on mobile).
- **Shift gate:** if Finance is on and no open shift, a blocking dialog "Buka shift dulu" asks opening cash (Rp input 20/700 right-aligned, quick chips Rp300.000/500.000/1.000.000) + cashier PIN. Buttons "Kembali" (outline) / "Buka shift" (green, flex 2).
- Toolbar: category chips (Semua, Kopi, Non-kopi, Pastry, Makanan; pill radius 20, 2px border; active `#E6F4DF` + `#1F5C12` border), channel mark when online order, search 220px.
- Menu grouped by category (h2 16/600 + "N menu"), grid `auto-fill minmax(156px,1fr)` (140 mobile). **Menu tile:** white, 1.5px border, radius 14, image 4:3, name 16/600, price 12 tabular, "Pilih opsi" when it has modifiers; qty badge top-right (dark pill, green text); "Habis" badge top-left (danger tint); low-stock warning line. Hover border ink. Sold-out tiles are dimmed and not clickable.
- **Modifier sheet:** image 56px + name; groups Suhu (Es/Panas), Ukuran (Reguler/Besar +Rp6.000), Susu (Segar/Oat +Rp8.000, only milk drinks), Gula (Normal/Kurang/Tanpa). Option buttons 1.5px border, active = green tint. CTA "Tambah · Rp…" full-width green 50px.
- **Cart:** "Pesanan #NNNN", "Hapus semua" (danger link); order type segmented (Makan di sini / Bawa pulang / Online when Delivery module on); table picker for dine-in; online fields (channel, platform order ID, driver) for online; line items with stepper, modifiers, note, price override; discount code / manual discount; totals (Subtotal, Diskon, Layanan, PB1 10%, Total); pay button.
- Mobile: floating green cart bar (58px, radius 16) "Lihat pesanan · qty · total" → full-screen cart with back arrow.
- **Payment dialog** (desktop 2-col: 250px item summary + body; mobile bottom sheet): methods Tunai, EDC (QRIS/Mastercard logos), GoPay, OVO, DANA, ShopeePay. Cash: amount received, quick amounts (exact, round up to 50k, 100k, +100k), change shown; pay disabled while cash < total with message "Uang tunai kurang". Card/QR: confirm states. On success: receipt toast, order goes to KDS, stock is deducted by recipe.

### 4.4 Pesanan (Orders)
Filters: status (Semua, Perlu verifikasi, Di dapur, Selesai, Dibatalkan), channel, period, search. Table on ≥1000, cards below. Columns: No, time, type/table, channel, items, total, method, status pill. Right detail drawer (370/440px, full-screen mobile) shows items, totals, payment, refunds history and actions: Verifikasi (self-order), Void item, Refund (partial/full), Batalkan, Buka ulang tagihan, Cetak struk. All sensitive actions go through the **approval dialog** (§5).

### 4.5 Self Order QR
QR tile grid per table (`auto-fill minmax(190px,1fr)`), print actions, prefix setting ("Meja"), pause toggle ("Pemesanan sedang dijeda"). Includes a phone-frame **customer view** preview (375×780 scaled) of the guest ordering flow: menu → modifiers → cart → submit; the order arrives as "pending" in Pesanan for cashier verification.

### 4.6 Meja (Tables)
2D floor map, 12 tables (Indoor T01–T08, Teras T09–T12, 2/4/6 seats). Status colours with labels: Kosong, Terisi (with timer + order nos), Perlu dibersihkan, Dipesan (reservation note). Tap a table → side panel/bottom sheet with actions (Buat pesanan, Tandai bersih, Reservasi).

### 4.7 Dapur & Bar
Tabs: **Layar dapur (KDS)** · **Resep & ketersediaan**.
- KDS: 3 columns (1 + column tabs on mobile): Baru (dot `#4A4E47`, button "Mulai proses"), Diproses (dot `#E0A526`, "Tandai siap"), Siap diambil (dot `#45A02E`, "Sudah diambil"). Ticket: order no, source/channel mark, table or customer, live timer coloured by age (<8 min `#1F5C12`, <15 `#6A4400`, ≥15 `#8E1A14`), items with modifiers & tappable done checkboxes, note. Header metrics: active tickets, average ticket time.
- Recipes: per menu item, ingredient quantities, cost and margin, "can make N" from stock, availability override (Otomatis / Paksa tersedia / Habis).

### 4.8 Produk & Diskon
Products tab: search, category filter, list with image, name, base price, per-channel prices, per-outlet availability column. Detail/editor drawer: base price, outlet overrides, channel price overrides (auto markup otherwise), photo (camera capture or upload). Categories tab: card per category with count, average price. Diskon: list of codes (name, code, % or Rp, active toggle, usage) + "Promo baru" dialog.

### 4.9 Inventaris
Tabs: Stok · Stock opname · Mutasi · Transfer antar outlet (multi-outlet only).
- Stok: filter (Semua / Menipis), rows: name, category, on-hand vs par with bar, status pill, actions Terima stok / Sesuaikan. "Buat PO otomatis" when low items exist.
- Opname: count form per ingredient + summary side panel (300px) with variance value; submitting logs `stock_adjust`.
- Mutasi: chronological movement log (+/−, reason).
- Transfer: request → send → receive flow with pills Diminta / Dalam perjalanan / Diterima; receive dialog records actual qty (variance logged).

### 4.10 Pembelian
Tabs: Pesanan pembelian · Pemasok. PO list with status (Draf, Dikirim, Diterima), detail with lines, ETA, payment term (Tunai, H+7, H+14, H+30, Lainnya). "Terima barang" dialog adds stock and creates a payable. Supplier cards: name, category, PIC, phone, lead time.

### 4.11 Keuangan
Tabs: Shift & Kas · Pengeluaran · Hutang · Pencairan platform (Delivery module only).
- Shift: list with status (Berjalan, Perlu ditinjau, Ditinjau), expected vs counted cash, variance (red/green). Close-shift dialog: denomination counter (Rp100.000 … Rp1.000 + coins), expected vs counted, note required when |variance| > threshold (default Rp20.000) and needs manager PIN. Cash in/out and "no sale" from the header shift menu.
- Pengeluaran: list + "Catat pengeluaran" dialog (category, amount, source: Laci kasir/Bank/E-wallet/Kas kecil, receipt, recurring).
- Hutang: payables with aging buckets (Lancar, 1–30, 31–60, >60), pills Belum dibayar/Sebagian/Lunas/Jatuh tempo, "Bayar hutang" dialog.
- Pencairan: expected vs received per channel/week, diff reason, "Catat pencairan" dialog.

### 4.12 Karyawan, Log aktivitas, Laporan
- Karyawan tabs: Absensi (clock in/out), Rekap mingguan, Pengguna (role, outlets), Izin (permission matrix — see `PERM_ROWS` in `omnify-store.js`).
- Log aktivitas: read-only, immutable list: time, user + role, type icon & label (see `LOG_TYPES`), object, before → after, approver, reason, device. Filters by type, user, outlet.
- Laporan: range (Hari ini, 7 hari, 30 hari…), sales, products, margin, tax.

### 4.13 Pengaturan
Tabs (visibility by role): Modul (owner; toggle cards with icon, description, dependency "Butuh Inventaris") · Outlet (address, phone, NPWPD, PB1 %, service %, hours, receipt header/footer) · Kanal penjualan (commission %, markup %, tax inclusive, payout lag days) · Kebijakan & kategori (variance threshold, discount approval threshold, default float, expense categories) · Pembayaran (enable methods) · Akun · Data demo (reset).
Toggle: track 44×24-ish, on `#45A02E`, off `#D7D5CE`, inside a ≥44px hit area.

---

## 5. Key shared components

| Component | Spec |
|---|---|
| Button primary | bg `#1F5C12`, text white 600, height 44–50, radius 10–12, no border |
| Button dark | bg `#10140F`, text white / icon `#7ED76A` |
| Button secondary | white, `1px #E7E5DF`, text ink 500–600 |
| Destructive | text `#8E1A14` (link or outline); destructive confirms use red solid only in confirm step |
| Link | `#1F5C12`, hover `#10140F`, no underline, min-height tap |
| Input | height 44–52, radius 11, `1px #D7D5CE` (focused/primary money input `1.5px #10140F`), 16px; money inputs right-aligned tabular with "Rp" prefix |
| Status pill | 12/600, padding 3px 9px, radius 20, tint bg + dark text from status table |
| Card | white, `1px #E7E5DF`, radius 14, padding 20, gap 10; title 16/600 + right-aligned 12px meta/link |
| Table | header row 12px secondary on `#FBFAF7` with top/bottom border; rows padding 12px 18px, divider `#F0EEE9`, hover `#F6F5F1`; numbers right-aligned |
| Popover | white, radius 14, popover shadow, padding 6, items min-height tap, radius 10, hover `#F6F5F1` |
| Modal / sheet | scrim 42%; desktop centered max-width 420–440, radius 18; mobile bottom sheet radius 22 top, padding bottom + safe-area |
| Drawer | right side 370 / 440 px, drawer shadow; full-screen on mobile |
| **Approval dialog** | Used for void, refund, cancel, reopen, manual discount > threshold, price override, no-sale, variance, stock adjust. Fields: reason chips (from `REASONS`), optional note, approver select (eligible Owner/Manajer of that outlet; defaults to self if eligible), approver PIN. Errors inline, e.g. "PIN Dewi salah. Coba lagi." On success writes an audit log entry with approverId. |
| Empty state | single 16px secondary sentence inside the card (e.g. "Semua stok aman.") |

---

## 6. Roles, modules, permissions

Roles (`ROLES`): **owner** (all outlets), **manajer** (assigned outlets, approves PINs), **kasir** (Kasir, Pesanan, own shift), **kasirdapur** (kasir + KDS/recipes), **dapur** (KDS/recipes).
Home page after unlock: owner/manajer → Ringkasan; kasir/kasirdapur → Kasir; dapur → Dapur.
Page access is `PAGE_ROLES` in `omnify-store.js`. Only owner can see **"Semua outlet"** (aggregate); pages that need a single outlet (Kasir, Dapur, Meja, Self Order, Inventaris, Pembelian) show a "pilih outlet" picker in that view.

Modules (Settings → Modul) switch features on/off: pos, selfOrder, tables, kitchen, inventory, purchasing (requires inventory), delivery, finance, audit, multi, staff, reports. Turning a module off hides its nav items, KPIs and fields.

---

## 7. Data model & business rules
Full schema and calculations live in **`omnify-store.js`** (top comment block is the schema). Highlights for the backend:
- Every transactional record has `outletId`. Money is integer Rupiah.
- `orders` statuses — direct: pending → new → cooking → ready → served (+ rejected, cancelled, reopened); online: new → cooking → ready → picked → served (+ pcancel).
- Totals (`calcTot`): direct = sub − discount + service (dine-in only, if outlet `svcOn`) + PB1 tax on (sub − disc + svc). Online = channel price (base × (1 + markup), rounded up to Rp500 unless overridden), tax inclusive or exclusive per channel, commission → `expectedPayout`.
- Modifier prices: Besar +Rp6.000, Susu oat +Rp8.000. Large size uses 1.4× recipe.
- Stock deducts per recipe (`REC` in `omnify-data.js`) on payment; low stock = on-hand < par; critical < 50% par.
- Shift expected cash = opening cash + cash sales − cash refunds + cash in − cash out.
- Audit logs are append-only; no role can edit/delete them.
- Number/date format: `Rp 1.250.000` (id-ID grouping, `−` minus sign U+2212), dates `toLocaleDateString('id-ID')`, times 24h `HH:MM`.

Suggested API surface: auth (PIN per device + user), outlets, users/roles, products & prices, orders (+ realtime feed for KDS and pending self-orders — WebSocket/SSE), payments, refunds, shifts & cash moves, inventory & moves, POs & payables, expenses, settlements, transfers, logs, settings.

---

## 8. Assets
- `assets/pay/*.svg` — payment logos (QRIS, Mastercard, Visa, GoPay, OVO, DANA, ShopeePay). Use official brand assets in production.
- Menu photos are Unsplash URLs (see `MENU` in `omnify-data.js`); replace with the client's own photos (4:3 crop, ≥480px wide).
- Wordmark `>omnify▌` is pure text (JetBrains Mono 800) + a coloured block; no image file.
- Icons: Material Symbols Rounded, names listed in the nav section and in `LOG_TYPES`.

## 9. Files in this bundle
- `Omnify.dc.html` — the complete app prototype (markup = layout/styling reference; logic class at the bottom = behaviour reference). Open in a browser; it has a preview-device tweak (Tablet lanskap 1180×820, Tablet potret 820×1180, Ponsel 390×844).
- `omnify-store.js` — data schema, seed generator, all calculations (totals, shift, aging, permissions).
- `omnify-data.js` — menu, ingredients, recipes, suppliers, payment methods, tables.
- `support.js` — runtime needed only to open the prototype; not for production.
- `tokens.css` — design tokens as CSS variables.
- `assets/pay/` — payment logos.
- `screenshots/` — full-length captures of every module (lock screen + 15 pages), one folder per viewport:
  - `1-desktop-1440/` (1440 wide, full sidebar)
  - `2-tablet-landscape-1180/` (icon rail)
  - `3-tablet-portrait-820/` (icon rail, stacked cards)
  - `4-mobile-390/` (bottom tab bar)
  Files are named `NN-modul.png` in nav order (00-kunci-pin, 01-ringkasan … 15-pengaturan). Each shot is the full scroll height of the page, so the sidebar/rail stretches to match. Dashboard is captured in "Semua outlet" view; all other pages in Kopi Senja · Kemang as Owner (Arif).

### Layout note: scrolling grids
Page bodies that are both `overflow:auto` and `display:grid` must set `grid-auto-rows: max-content`. Without it, the browser shrinks auto rows to fit the container and cards with `overflow:hidden` get clipped instead of scrolling.

Demo PINs: Rina 1111 (kasir, Kemang), Bayu 2222, Sinta 3333 (Senopati), Yoga 4444 (kasir+dapur, BSD), Dewi 5555 (manajer), Arif 6666 (owner).
