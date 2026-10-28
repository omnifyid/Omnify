/* Omnify shared store — data model, seed (60 hari, 3 outlet), kalkulasi.
 * Semua record transaksional punya outletId. Angka uang dalam Rupiah bulat.
 * orders:      { id, no, outletId, channel:'direct'|'gofood'|'grabfood'|'shopeefood', source:'kasir'|'qr'|'manual'|'api',
 *                type:'dine'|'take'|'online', table, customer, items:[{id,qty,voidQty,price,origPrice,mods,note,done}],
 *                sub, disc, discPct, discLabel, svc, tax, total, paid, refunded, method, status, createdAt, paidAt,
 *                userId, shiftId, channelOrderId, driver, appNote, appTotal, commissionAmount, expectedPayout,
 *                expectedPayoutDate, settlementId, cancelReason, wasted, reopenedFrom }
 *   status direct: pending|new|cooking|ready|served|rejected|cancelled|reopened
 *   status online: new(Diterima)|cooking(Disiapkan)|ready(Siap diambil)|picked(Diambil driver)|served(Selesai)|pcancel
 *   Pendapatan (incl. pajak) = total − refunded untuk status valid. total sudah dikurangi void.
 * refunds:     { id, orderId, outletId, t, amount, method, type:'void'|'partial'|'full'|'cancel'|'reopen', shiftId, userId, approverId, reason, items }
 * shifts:      { id, outletId, userId, openedAt, openCash, closedAt, denoms, counted, expected, variance, note, approverId, status:'open'|'closed'|'reviewed', reviewNote, reviewedBy }
 * cashMoves:   { id, shiftId, outletId, t, type:'in'|'out'|'nosale', amount, category, reason, userId, expenseId, payPaymentId, refType }
 * expenses:    { id, no, outletId, date, category, desc, amount, source:'drawer'|'bank'|'ewallet'|'petty', shiftId, cashMoveId, receipt, recurring, seriesId, status:'posted'|'draft', userId }
 * payables:    { id, poId, poNo, outletId, sup, invoiceNo, invoiceDate, term, termDays, dueDate, total, paid }
 * payPayments: { id, payableId, outletId, t, amount, source, shiftId, userId }
 * settlements: { id, no, outletId, channel, receivedAt, amount, expected, diff, reason, orderIds, userId }
 * transfers:   { id, no, from, to, lines:[{ing,qty,recv}], status:'requested'|'sent'|'received', requestedAt/By, sentAt/By, receivedAt/By }
 * wastes:      { id, outletId, t, source, orderId, items:[{id,qty}], value }
 * logs (read-only): { id, t, outletId, userId, role, type, objType, objId, objLabel, before, after, approverId, reason, device }
 */
(function () {
const D = 86400000, H = 3600000, MIN = 60000, VER = 7, KEY = 'omnify-db-v7', SKEY = 'omnify-session-v7';
const sod = t => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
const clone = o => JSON.parse(JSON.stringify(o));
const r500 = v => Math.ceil(v / 500) * 500;
const isDrink = c => c === 'Kopi' || c === 'Non-kopi';
const modAdd = (OM, id, m) => (m && m.size === 'L' ? 6000 : 0) + (m && m.milk === 'oat' && OM.MB[id].milk ? 8000 : 0);
const modsStr = (OM, id, m) => { if (!m) return ''; const p = [m.temp === 'ice' ? 'Es' : 'Panas']; if (m.size === 'L') p.push('Besar'); if (m.milk === 'oat' && OM.MB[id].milk) p.push('Susu oat'); if (m.sugar === 'less') p.push('Kurang manis'); if (m.sugar === 'none') p.push('Tanpa gula'); return p.join(' · '); };

const OUTLETS = [
  { id: 'kmg', name: 'Kemang', full: 'Kopi Senja · Kemang', addr: 'Jl. Kemang Raya No. 18, Jakarta Selatan', phone: '021-7199-0418', npwpd: 'P2.0018.2210.7', pb1: 10, svc: 5, svcOn: false, open: '07:00', close: '22:00', rcHead: 'KOPI SENJA KEMANG · Jl. Kemang Raya No. 18', rcFoot: 'Terima kasih! IG @kopisenja', active: true, device: 'iPad Kasir 01' },
  { id: 'snp', name: 'Senopati', full: 'Kopi Senja · Senopati', addr: 'Jl. Senopati No. 62, Kebayoran Baru, Jakarta Selatan', phone: '021-2751-6620', npwpd: 'P2.0018.3391.2', pb1: 10, svc: 5, svcOn: true, open: '07:00', close: '23:00', rcHead: 'KOPI SENJA SENOPATI · Jl. Senopati No. 62', rcFoot: 'Terima kasih! IG @kopisenja', active: true, device: 'iPad Kasir 01' },
  { id: 'bsd', name: 'BSD', full: 'Kopi Senja · BSD', addr: 'Ruko Golden Boulevard Blok C-7, BSD City, Tangerang Selatan', phone: '021-5316-0287', npwpd: '36.74.0412.88', pb1: 10, svc: 0, svcOn: false, open: '08:00', close: '22:00', rcHead: 'KOPI SENJA BSD · Golden Boulevard C-7', rcFoot: 'Terima kasih! IG @kopisenja', active: true, device: 'Tablet Kasir 01' },
];
const USERS = [
  { id: 'u1', name: 'Rina', role: 'kasir', outlets: ['kmg'], pin: '1111', phone: '0812-3300-1182' },
  { id: 'u2', name: 'Bayu', role: 'kasir', outlets: ['kmg'], pin: '2222', phone: '0813-2201-7744' },
  { id: 'u5', name: 'Sinta', role: 'kasir', outlets: ['snp'], pin: '3333', phone: '0857-1123-6650' },
  { id: 'u6', name: 'Yoga', role: 'kasirdapur', outlets: ['bsd'], pin: '4444', phone: '0821-7765-0091' },
  { id: 'u3', name: 'Dewi', role: 'manajer', outlets: ['kmg', 'snp'], pin: '5555', phone: '0811-8890-2210', device: 'MacBook Dewi' },
  { id: 'u4', name: 'Arif', role: 'owner', outlets: ['kmg', 'snp', 'bsd'], pin: '6666', phone: '0811-1200-4400', device: 'iPhone Arif' },
];
const ROLES = {
  owner: { label: 'Owner', desc: 'Semua akses, semua outlet' },
  manajer: { label: 'Manajer outlet', desc: 'Semua untuk outletnya, menyetujui PIN' },
  kasir: { label: 'Kasir', desc: 'Kasir, Pesanan, shift sendiri' },
  kasirdapur: { label: 'Kasir + Dapur', desc: 'Kasir, Pesanan, shift sendiri, layar dapur, resep & ketersediaan' },
  dapur: { label: 'Dapur', desc: 'Layar dapur, resep & ketersediaan' },
};
const ALLR = ['owner', 'manajer'];
const PAGE_ROLES = { dashboard: ALLR, pos: ['owner', 'manajer', 'kasir', 'kasirdapur'], orders: ['owner', 'manajer', 'kasir', 'kasirdapur'], selforder: ALLR, tables: ALLR, kitchen: ['owner', 'manajer', 'dapur', 'kasirdapur'], products: ALLR, discounts: ALLR, inventory: ALLR, purchasing: ALLR, finance: ALLR, staff: ALLR, audit: ALLR, reports: ALLR, settings: ALLR };
const HOME = { owner: 'dashboard', manajer: 'dashboard', kasir: 'pos', kasirdapur: 'pos', dapur: 'kitchen' };
const PERM_ROWS = [
  { g: 'Halaman', label: 'Ringkasan', page: 'dashboard' }, { g: 'Halaman', label: 'Kasir', page: 'pos' }, { g: 'Halaman', label: 'Pesanan', page: 'orders' },
  { g: 'Halaman', label: 'Self Order & Meja', page: 'tables' }, { g: 'Halaman', label: 'Dapur & Bar (KDS, resep)', page: 'kitchen' }, { g: 'Halaman', label: 'Produk & Diskon', page: 'products' },
  { g: 'Halaman', label: 'Inventaris & Pembelian', page: 'inventory' }, { g: 'Halaman', label: 'Keuangan', page: 'finance' }, { g: 'Halaman', label: 'Karyawan, Log, Laporan', page: 'audit' }, { g: 'Halaman', label: 'Pengaturan', page: 'settings' },
  { g: 'Aksi', label: 'Buka & tutup shift sendiri, kas masuk/keluar', roles: ['owner', 'manajer', 'kasir', 'kasirdapur'] },
  { g: 'Aksi', label: 'Minta void, refund, diskon, ubah harga (butuh PIN)', roles: ['owner', 'manajer', 'kasir', 'kasirdapur'] },
  { g: 'Aksi', label: 'Menyetujui dengan PIN', roles: ALLR },
  { g: 'Aksi', label: 'Tinjau shift & selisih kas', roles: ALLR },
  { g: 'Aksi', label: 'Ubah harga produk & resep', roles: ALLR },
  { g: 'Aksi', label: 'Ubah data outlet sendiri', roles: ALLR },
  { g: 'Aksi', label: 'Ubah pengaturan bisnis (modul, kanal, kebijakan)', roles: ['owner'] },
  { g: 'Aksi', label: 'Ubah peran & outlet pengguna', roles: ['owner'] },
  { g: 'Aksi', label: 'Lihat semua outlet sekaligus', roles: ['owner'] },
  { g: 'Aksi', label: 'Ubah atau hapus log aktivitas', roles: [] },
];
const CHANNELS = [
  { id: 'gofood', label: 'GoFood', mark: 'GF', color: '#9E1B2F', tint: '#FBEFF1' },
  { id: 'grabfood', label: 'GrabFood', mark: 'GR', color: '#14633A', tint: '#EAF5EE' },
  { id: 'shopeefood', label: 'ShopeeFood', mark: 'SF', color: '#9A3412', tint: '#FCF0E8' },
];
const CHB = Object.fromEntries(CHANNELS.map(c => [c.id, c]));
const isOnline = o => !!(o && o.channel && o.channel !== 'direct');
const EXP_CATS = ['Sewa', 'Listrik & air', 'Gaji & upah', 'Bahan non-stok', 'Marketing', 'Perbaikan & perawatan', 'Transport', 'Internet & software', 'Lain-lain'];
const SETTINGS = {
  channels: { gofood: { on: true, comm: 20, markup: 20, inclTax: true, lag: 2 }, grabfood: { on: true, comm: 20, markup: 20, inclTax: true, lag: 3 }, shopeefood: { on: true, comm: 18, markup: 15, inclTax: true, lag: 7 } },
  varianceThreshold: 20000, discThreshold: 10, defaultFloat: 500000, expenseCats: EXP_CATS.slice(),
};
const FUNDS = [{ id: 'drawer', label: 'Laci kasir' }, { id: 'bank', label: 'Bank' }, { id: 'ewallet', label: 'E-wallet' }, { id: 'petty', label: 'Kas kecil' }];
const FB = Object.fromEntries(FUNDS.map(f => [f.id, f]));
const TERMS = [{ id: 'tunai', label: 'Tunai', days: 0 }, { id: 'h7', label: 'H+7', days: 7 }, { id: 'h14', label: 'H+14', days: 14 }, { id: 'h30', label: 'H+30', days: 30 }, { id: 'custom', label: 'Lainnya', days: null }];
const DENOMS = [100000, 50000, 20000, 10000, 5000, 2000, 1000];
const CASH_IN_CATS = ['Tambah uang kembalian', 'Dari kas kecil', 'Setoran pemilik', 'Lain-lain'];
const CASH_OUT_NONEXP = ['Setor ke bank', 'Pindah ke kas kecil'];
const REASONS = {
  void: ['Salah input', 'Pelanggan berubah pikiran', 'Item habis', 'Kualitas tidak sesuai', 'Lain-lain'],
  refund: ['Pesanan salah', 'Kualitas tidak sesuai', 'Terlalu lama', 'Kompensasi keluhan', 'Lain-lain'],
  cancel: ['Pelanggan membatalkan', 'Salah input', 'Item habis', 'Pembayaran ganda', 'Lain-lain'],
  disc: ['Kompensasi keluhan', 'Pelanggan tetap', 'Karyawan', 'Rekanan', 'Lain-lain'],
  price: ['Harga lama di menu', 'Porsi khusus', 'Kompensasi', 'Lain-lain'],
  reopen: ['Salah metode bayar', 'Tambah item', 'Salah pesanan', 'Lain-lain'],
  nosale: ['Tukar uang kecil', 'Cek isi laci', 'Koreksi kembalian', 'Lain-lain'],
  stock: ['Hasil stock opname', 'Barang rusak', 'Koreksi input', 'Lain-lain'],
  variance: ['Salah kembalian', 'Uang palsu ditolak', 'Belum ditemukan', 'Lain-lain'],
  pcancel: ['Driver tidak ditemukan', 'Pelanggan membatalkan', 'Restoran terlalu lama', 'Item habis', 'Lain-lain'],
  settle: ['Penyesuaian komisi', 'Pesanan dibatalkan platform', 'Biaya promo merchant', 'Biaya iklan/layanan', 'Pembulatan', 'Lain-lain'],
};
const LOG_TYPES = {
  void_item: ['Void item', 'remove_shopping_cart'], cancel_order: ['Batalkan pesanan dibayar', 'cancel'], refund: ['Refund', 'currency_exchange'],
  discount_manual: ['Diskon manual', 'percent'], price_override: ['Ubah harga di kasir', 'edit'], reopen_bill: ['Buka ulang tagihan', 'restart_alt'],
  no_sale: ['Buka laci tanpa transaksi', 'point_of_sale'], stock_adjust: ['Penyesuaian stok', 'inventory'], shift_variance: ['Tutup shift dengan selisih', 'warning'],
  shift_open: ['Buka shift', 'lock_open'], shift_close: ['Tutup shift', 'lock'], shift_review: ['Tinjau shift', 'fact_check'],
  cash_in: ['Kas masuk', 'south_west'], cash_out: ['Kas keluar', 'north_east'], login: ['Masuk', 'login'], logout: ['Keluar', 'logout'],
  price_change: ['Ubah harga produk', 'sell'], recipe_change: ['Ubah resep', 'menu_book'], permission_change: ['Ubah izin pengguna', 'admin_panel_settings'],
  settings_change: ['Ubah pengaturan', 'settings'], online_cancel: ['Dibatalkan platform', 'delivery_dining'], expense: ['Catat pengeluaran', 'receipt'],
  payable_pay: ['Bayar hutang', 'payments'], settlement: ['Catat pencairan', 'account_balance'], transfer: ['Transfer stok', 'swap_horiz'], po_receive: ['Terima barang', 'inventory_2'], data_reset: ['Reset data demo', 'restart_alt'],
};
const DISCOUNTS = [
  { id: 'd1', name: 'Senja Hemat', code: 'SENJA10', type: 'pct', value: 10, active: true, used: 38, note: 'Semua menu' },
  { id: 'd2', name: 'Happy Hour Kopi', code: 'HAPPY15', type: 'pct', value: 15, active: true, used: 21, note: 'Setiap hari 14:00–16:00' },
  { id: 'd3', name: 'Potongan Rp20rb', code: 'HEMAT20', type: 'amt', value: 20000, active: false, used: 4, note: 'Min. belanja Rp150.000' },
];

// ── harga & total ───────────────────────────────────────────────────────────
const outletOf = (db, oid) => (db.outlets || []).find(o => o.id === oid) || OUTLETS[0];
const carried = (db, pid, oid) => { const c = db.prodCfg[pid]; if (!c || c.active === false) return false; const o = c.out && c.out[oid]; return !o || o.on !== false; };
const outletPrice = (db, pid, oid) => { const c = db.prodCfg[pid]; const o = c && c.out && c.out[oid]; return (o && o.price) || (c ? c.base : 0); };
const autoChPrice = (db, pid, oid, ch, add) => r500((outletPrice(db, pid, oid) + (add || 0)) * (1 + db.settings.channels[ch].markup / 100));
const chPrice = (db, pid, oid, ch, add) => {
  add = add || 0; if (!ch || ch === 'direct') return outletPrice(db, pid, oid) + add;
  const c = db.prodCfg[pid], ov = c && c.ch && c.ch[ch];
  return ov ? ov + r500(add * (1 + db.settings.channels[ch].markup / 100)) : autoChPrice(db, pid, oid, ch, add);
};
const lineQty = l => l.qty - (l.voidQty || 0);
function calcTot(db, oid, lines, type, ch, discPct) {
  const ol = outletOf(db, oid), pb = ol.pb1 / 100;
  const sub = lines.reduce((a, l) => a + l.price * lineQty(l), 0);
  if (ch && ch !== 'direct') {
    const cs = db.settings.channels[ch]; let tax, total;
    if (cs.inclTax) { total = Math.round(sub); tax = Math.round(total - total / (1 + pb)); } else { tax = Math.round(sub * pb); total = Math.round(sub + tax); }
    const comm = Math.round(total * cs.comm / 100);
    return { sub, disc: 0, svc: 0, tax, total, commissionAmount: comm, expectedPayout: total - comm, inclTax: cs.inclTax };
  }
  const d = Math.round(sub * (discPct || 0)), svc = type === 'dine' && ol.svcOn ? Math.round((sub - d) * ol.svc / 100) : 0, tax = Math.round((sub - d + svc) * pb);
  return { sub, disc: d, svc, tax, total: sub - d + svc + tax };
}
const VALID = { new: 1, cooking: 1, ready: 1, picked: 1, served: 1 };
const validSale = o => !!VALID[o.status];
const revenueOf = o => validSale(o) ? o.total - (o.refunded || 0) : 0;
const netOf = o => { if (!validSale(o) || !o.total) return 0; return (o.total - o.tax) * (o.total - (o.refunded || 0)) / o.total; };
function usage(OM, items) {
  const use = {};
  items.forEach(c => { const q = lineQty(c); if (q <= 0) return; const f = c.mods && c.mods.size === 'L' ? 1.4 : 1; Object.entries(OM.REC[c.id] || {}).forEach(([k, r]) => { const kk = k === 'milk' && c.mods && c.mods.milk === 'oat' ? 'oat' : k; use[kk] = (use[kk] || 0) + r * f * q; }); });
  return use;
}
const costOf = (OM, id) => Object.entries(OM.REC[id] || {}).reduce((a, [k, q]) => a + q * OM.IB[k].cost, 0);

// ── kalkulasi shift (di-cache per referensi array) ───────────────────────────
let IX = {};
function index(db) {
  if (IX.o === db.orders && IX.r === db.refunds && IX.c === db.cashMoves) return IX.v;
  const sh = {}, g = id => sh[id] || (sh[id] = { cashSales: 0, cashRefunds: 0, cashIn: 0, cashOut: 0, nosale: 0, nOrders: 0, pay: {}, payRef: {}, ch: {}, chN: {}, refunds: [], moves: [] });
  db.orders.forEach(o => {
    if (!o.shiftId) return; const x = g(o.shiftId);
    if (isOnline(o)) { if (o.status !== 'pcancel') { x.ch[o.channel] = (x.ch[o.channel] || 0) + o.total; x.chN[o.channel] = (x.chN[o.channel] || 0) + 1; } return; }
    if (!o.paidAt) return; x.nOrders++; const amt = o.paid != null ? o.paid : o.total;
    if (o.method === 'cash') x.cashSales += amt; else x.pay[o.method] = (x.pay[o.method] || 0) + amt;
  });
  db.refunds.forEach(r => { if (!r.shiftId) return; const x = g(r.shiftId); x.refunds.push(r); if (r.method === 'cash') x.cashRefunds += r.amount; else if (!CHB[r.method]) x.payRef[r.method] = (x.payRef[r.method] || 0) + r.amount; });
  db.cashMoves.forEach(m => { const x = g(m.shiftId); x.moves.push(m); if (m.type === 'in') x.cashIn += m.amount; else if (m.type === 'out') x.cashOut += m.amount; else if (m.type === 'nosale') x.nosale++; });
  IX = { o: db.orders, r: db.refunds, c: db.cashMoves, v: sh }; return sh;
}
function shiftCalc(db, s) {
  const x = index(db)[s.id] || { cashSales: 0, cashRefunds: 0, cashIn: 0, cashOut: 0, nosale: 0, nOrders: 0, pay: {}, payRef: {}, ch: {}, chN: {}, refunds: [], moves: [] };
  return { ...x, expected: s.openCash + x.cashSales - x.cashRefunds + x.cashIn - x.cashOut };
}
const payStatus = (p, now) => { const rem = p.total - p.paid; if (rem <= 0) return 'lunas'; if (p.dueDate < sod(now)) return 'overdue'; return p.paid > 0 ? 'partial' : 'unpaid'; };
const overdueDays = (p, now) => Math.max(0, Math.floor((sod(now) - p.dueDate) / D));
function aging(payables, now) {
  const b = { cur: 0, d30: 0, d60: 0, d90: 0 };
  payables.forEach(p => { const rem = p.total - p.paid; if (rem <= 0) return; const od = p.dueDate < sod(now) ? overdueDays(p, now) : 0; if (!od) b.cur += rem; else if (od <= 30) b.d30 += rem; else if (od <= 60) b.d60 += rem; else b.d90 += rem; });
  return b;
}
const receivable = o => isOnline(o) && o.status !== 'pcancel' && (o.expectedPayout || 0) > 0 && !o.settlementId;

// ── persistensi ─────────────────────────────────────────────────────────────
const DBK = ['v', 'seededAt', 'outlets', 'users', 'settings', 'prodCfg', 'stockBy', 'tablesBy', 'unavailableBy', 'orders', 'moves', 'pos', 'opnames', 'shifts', 'cashMoves', 'expenses', 'payables', 'payPayments', 'settlements', 'refunds', 'wastes', 'transfers', 'logs', 'nextNoBy', 'seq', 'discounts', 'payEnabled', 'selfOrderOn', 'soPrefix'];
function load() { try { const raw = localStorage.getItem(KEY); if (!raw) return null; const db = JSON.parse(raw); return db && db.v === VER ? db : null; } catch (e) { return null; } }
function save(st) { try { const o = {}; DBK.forEach(k => { o[k] = st[k]; }); localStorage.setItem(KEY, JSON.stringify(o)); return true; } catch (e) { return false; } }
function loadSess() { try { return JSON.parse(localStorage.getItem(SKEY) || 'null'); } catch (e) { return null; } }
function saveSess(s) { try { localStorage.setItem(SKEY, JSON.stringify(s)); } catch (e) { } }

// ── seed ────────────────────────────────────────────────────────────────────
function seed(OM, now) {
  let s0 = 20261028; const R = () => { s0 = (Math.imul(s0, 1664525) + 1013904223) >>> 0; return s0 / 4294967296; };
  const ri = (a, b) => a + Math.floor(R() * (b - a + 1)), pk = a => a[Math.floor(R() * a.length)];
  const wp = pairs => { let t = 0; pairs.forEach(p => { t += p[1]; }); let x = R() * t; for (const p of pairs) { x -= p[1]; if (x <= 0) return p[0]; } return pairs[pairs.length - 1][0]; };
  const today = sod(now);
  const db = { v: VER, seededAt: now, outlets: clone(OUTLETS), users: clone(USERS), settings: clone(SETTINGS), prodCfg: {}, stockBy: {}, tablesBy: {}, unavailableBy: { kmg: {}, snp: {}, bsd: {} }, orders: [], moves: [], pos: [], opnames: [], shifts: [], cashMoves: [], expenses: [], payables: [], payPayments: [], settlements: [], refunds: [], wastes: [], transfers: [], logs: [], nextNoBy: {}, seq: {}, discounts: clone(DISCOUNTS), payEnabled: Object.fromEntries(OM.PAY.map(p => [p.id, true])), selfOrderOn: true, soPrefix: 'Meja' };
  const nid = p => { db.seq[p] = (db.seq[p] || 0) + 1; return p + '-' + String(db.seq[p]).padStart(4, '0'); };
  const U = Object.fromEntries(db.users.map(u => [u.id, u]));
  const devOf = oid => { const o = outletOf(db, oid); return o.device + ' · ' + o.name; };
  const L = e => { const u = U[e.userId]; db.logs.push({ id: nid('LG'), t: e.t, outletId: e.outletId || null, userId: e.userId, role: u.role, type: e.type, objType: e.objType || null, objId: e.objId || null, objLabel: e.objLabel || '', before: e.before == null ? null : e.before, after: e.after == null ? null : e.after, approverId: e.approverId || null, reason: e.reason || '', device: e.device || u.device || devOf(e.outletId) }); };
  const OIDS = ['kmg', 'snp', 'bsd'];

  OM.MENU.forEach(m => { db.prodCfg[m.id] = { base: m.price, active: true, ch: {}, out: { kmg: { on: true, price: null }, snp: { on: true, price: null }, bsd: { on: true, price: null } } }; });
  db.prodCfg.k5.out.bsd.on = false; db.prodCfg.f2.out.bsd.on = false; db.prodCfg.k5.out.snp.price = 42000; db.prodCfg.f1.out.snp.price = 48000; db.prodCfg.k1.ch.gofood = 34000;
  const rq = (i, v) => i.unit === 'pcs' ? Math.round(v) : Math.round(v * 100) / 100;
  db.stockBy.kmg = Object.fromEntries(OM.INGS.map(i => [i.id, i.on]));
  db.stockBy.snp = Object.fromEntries(OM.INGS.map(i => [i.id, rq(i, i.on * 1.35)])); db.stockBy.snp.milk = 22; db.stockBy.snp.croissant = 18; db.stockBy.snp.espresso = 2.6;
  db.stockBy.bsd = Object.fromEntries(OM.INGS.map(i => [i.id, rq(i, i.on * 0.85)])); db.stockBy.bsd.espresso = 0.9; db.stockBy.bsd.cup = 90;
  OIDS.forEach(oid => { db.tablesBy[oid] = Object.fromEntries(OM.TABLES.map(x => [x.id, { status: 'free', since: null, orders: [], note: '' }])); });

  const W = { k1: 22, k4: 12, k3: 11, p1: 10, f1: 8, n1: 7, f2: 6, k2: 7, k5: 3, n2: 4, n3: 5, p2: 6, p3: 4, f3: 3, f4: 3 };
  const WP = Object.entries(W);
  const NAMES = ['Andi', 'Sari', 'Maya', 'Kevin', 'Nadia', 'Rafi', 'Tom', 'Laras', 'Bima', 'Citra', 'Dimas', 'Eka', 'Fikri', 'Gita', 'Hana', 'Indra', 'Joko', 'Kirana', 'Lukas', 'Mira'];
  const DRIVERS = ['Pak Sutrisno', 'Mas Andre', 'Pak Wawan', 'Mas Rizky', 'Pak Darto', 'Mas Ilham', 'Pak Yanto', 'Mas Bagas'];
  const METH = [['cash', 30], ['edc', 50], ['gopay', 8], ['ovo', 5], ['dana', 4], ['shopeepay', 3]];
  const HW = { 7: .5, 8: 1, 9: .9, 10: .6, 11: .6, 12: 1, 13: .9, 14: .6, 15: .7, 16: .8, 17: .7, 18: .6, 19: .6, 20: .5, 21: .3 };
  const sampleT = (a, b) => { for (let k = 0; k < 30; k++) { const t = a + R() * (b - a); if (R() < (HW[new Date(t).getHours()] || .25)) return Math.round(t); } return Math.round(a + R() * (b - a)); };
  const pid6 = ch => ch === 'gofood' ? 'GF-' + ri(100000, 999999) + '-' + ri(10, 99) : ch === 'grabfood' ? 'GR-A' + ri(1000000, 9999999) : 'SF' + ri(10000000, 99999999);
  const mkItems = (oid, ch) => {
    const n = wp([[1, 40], [2, 35], [3, 18], [4, 7]]), items = [];
    for (let i = 0; i < n; i++) {
      let pid, g = 0; do { pid = wp(WP); g++; } while (!carried(db, pid, oid) && g < 20);
      const m = OM.MB[pid]; const mods = isDrink(m.cat) ? { size: R() < .2 ? 'L' : 'R', temp: R() < .7 ? 'ice' : 'hot', milk: m.milk && R() < .1 ? 'oat' : 'fresh', sugar: R() < .15 ? 'less' : 'normal' } : null;
      const key = pid + JSON.stringify(mods || {}), ex = items.find(x => x.key === key);
      if (ex) ex.qty++; else items.push({ key, id: pid, qty: R() < .15 ? 2 : 1, mods, note: modsStr(OM, pid, mods), price: chPrice(db, pid, oid, ch, modAdd(OM, pid, mods)), done: true });
    }
    return items;
  };
  const CASHIER = { kmg: ['u1', 'u2'], snp: ['u5', 'u5'], bsd: ['u6', 'u6'] };
  const APPR = { kmg: 'u3', snp: 'u3', bsd: 'u4' };
  const BASEN = { kmg: 19, snp: 23, bsd: 15 };
  const wasteOf = (oid, o, t, src, items) => { db.wastes.push({ id: nid('WS'), outletId: oid, t, source: src, orderId: o.id, items: items.map(x => ({ id: x.id, qty: x.qty })), value: Math.round(items.reduce((a, x) => a + costOf(OM, x.id) * x.qty, 0)) }); };
  const apply = (o, tot) => { o.sub = tot.sub; o.disc = tot.disc; o.svc = tot.svc; o.tax = tot.tax; o.total = tot.total; if (tot.commissionAmount != null) { o.commissionAmount = tot.commissionAmount; o.expectedPayout = tot.expectedPayout; } };
  const mkOrder = (oid, no, t, w, opt) => {
    opt = opt || {};
    const ch = opt.ch || (R() < .24 ? wp([['gofood', 45], ['grabfood', 35], ['shopeefood', 20]]) : 'direct'), on = ch !== 'direct';
    const items = opt.items ? opt.items.map(([id, qty, mods]) => { const mm = isDrink(OM.MB[id].cat) ? { size: 'R', temp: 'ice', milk: 'fresh', sugar: 'normal', ...(mods || {}) } : null; return { key: id + JSON.stringify(mm || {}), id, qty, mods: mm, note: modsStr(OM, id, mm), price: chPrice(db, id, oid, ch, modAdd(OM, id, mm)), done: false }; }) : mkItems(oid, ch);
    const type = opt.type || (on ? 'online' : R() < .6 ? 'dine' : 'take');
    let discPct = 0, discLabel = '';
    if (!on && !opt.items) { if (R() < .08) { const p = pk([['SENJA10', 10], ['HAPPY15', 15]]); discPct = p[1] / 100; discLabel = p[0]; } }
    const tot = calcTot(db, oid, items, type, ch, discPct);
    const method = on ? ch : (opt.method || wp(METH));
    const o = { id: 'O-' + oid + '-' + no, no, outletId: oid, channel: ch, source: on ? 'manual' : (opt.source || (type === 'dine' && R() < .15 ? 'qr' : 'kasir')), type, table: type === 'dine' ? (opt.table || 'T' + String(ri(1, 12)).padStart(2, '0')) : null, customer: opt.cust || (on || R() < .4 ? pk(NAMES) : 'Umum'), items, ...tot, discPct, discLabel, paid: on || opt.status === 'pending' ? 0 : tot.total, refunded: 0, method: opt.status === 'pending' ? 'none' : method, status: opt.status || 'served', createdAt: t, paidAt: on || opt.status === 'pending' ? null : t, userId: w ? w.user : null, shiftId: w && opt.status !== 'pending' ? w.id : null };
    if (opt.custNote) o.custNote = opt.custNote;
    if (on) Object.assign(o, { channelOrderId: pid6(ch), driver: opt.driver || pk(DRIVERS), appNote: R() < .3 ? pk(['Sendok garpu ya', 'Es dipisah', 'Jangan pedas', 'Tolong dibungkus rapi']) : '', appTotal: tot.total, expectedPayoutDate: sod(t) + db.settings.channels[ch].lag * D, settlementId: null });
    return o;
  };

  OIDS.forEach((oid, k) => {
    const wins = [];
    for (let d = 59; d >= 0; d--) {
      const day0 = today - d * D, dow = new Date(day0).getDay();
      let blocks = [[day0 + 7 * H, day0 + 15 * H], [day0 + 15 * H, day0 + 22 * H]];
      if (d === 0) { blocks = blocks.map(([a, b]) => [a, Math.min(b, now)]).filter(([a, b]) => b - a >= 10 * MIN); }
      blocks.forEach(([a, b], bi) => {
        const f = (dow === 0 || dow === 6 ? 1.3 : dow === 5 ? 1.1 : 1) * (0.85 + R() * .3) * (1 + (59 - d) * 0.0017);
        const full = bi === 0 ? 8 * H : 7 * H;
        const n = Math.max(1, Math.round(BASEN[oid] * (bi === 0 ? .55 : .45) * f * Math.min(1, (b - a) / full)));
        const sh = { id: nid('SH'), outletId: oid, userId: CASHIER[oid][bi], openedAt: a, openCash: 500000, closedAt: d === 0 && b >= now ? now : b, denoms: null, counted: null, expected: null, variance: null, note: '', approverId: null, status: 'closed', reviewNote: '', reviewedBy: null };
        db.shifts.push(sh); wins.push({ id: sh.id, a, b, user: sh.userId, d, n, sh, last: d === 0 && b >= now });
      });
    }
    const slots = [];
    wins.forEach(w => { const lim = w.last ? (oid === 'kmg' ? now - 70 * MIN : now - 18 * MIN) : w.b - 2 * MIN; if (lim <= w.a + 2 * MIN) return; for (let i = 0; i < w.n; i++) slots.push({ t: sampleT(w.a + 2 * MIN, lim), w }); });
    slots.sort((a, b) => a.t - b.t);
    let no = 1001;
    const recent = Date.now() - 7 * D;
    slots.forEach(({ t, w }) => {
      const o = mkOrder(oid, no++, t, w); db.orders.push(o);
      const fraud = oid === 'snp' && t > today - 6 * D;
      const appr = APPR[oid] === w.user ? 'u4' : APPR[oid];
      if (o.channel === 'direct') {
        if (R() < (fraud ? .012 : .006)) {
          const pct = ri(15, 30), tot = calcTot(db, oid, o.items, o.type, 'direct', pct / 100); o.discPct = pct / 100; o.discLabel = 'Diskon manual ' + pct + '%'; apply(o, tot); o.paid = o.total;
          L({ t, outletId: oid, userId: w.user, type: 'discount_manual', objType: 'order', objId: o.id, objLabel: 'Pesanan #' + o.no, before: '0%', after: pct + '%', approverId: appr, reason: pk(REASONS.disc) });
        }
        const rT = Math.min(t + ri(3, 20) * MIN, w.b - MIN);
        const r = R();
        if (r < (fraud ? .03 : .008) && o.items.some(l => l.qty > 0)) {
          const li = Math.floor(R() * o.items.length), it = o.items[li], before = lineQty(it); it.voidQty = (it.voidQty || 0) + 1;
          const tot = calcTot(db, oid, o.items, o.type, 'direct', o.discPct); const amt = o.total - tot.total; apply(o, tot); const made = R() < .4;
          db.refunds.push({ id: nid('RF'), orderId: o.id, outletId: oid, t: rT, amount: amt, method: o.method, type: 'void', shiftId: w.id, userId: w.user, approverId: appr, reason: pk(REASONS.void), items: [{ id: it.id, qty: 1 }] });
          if (made) wasteOf(oid, o, rT, 'void', [{ id: it.id, qty: 1 }]);
          L({ t: rT, outletId: oid, userId: w.user, type: 'void_item', objType: 'order', objId: o.id, objLabel: 'Pesanan #' + o.no, before: before + '× ' + OM.MB[it.id].name, after: (before - 1) + '× ' + OM.MB[it.id].name, approverId: appr, reason: db.refunds[db.refunds.length - 1].reason + (made ? ' · sudah dibuat' : '') });
        } else if (r < .016) {
          const amt = Math.min(o.total, Math.round(o.items[0].price * 1.1)); o.refunded = amt; const m = o.method === 'cash' ? 'cash' : o.method;
          db.refunds.push({ id: nid('RF'), orderId: o.id, outletId: oid, t: rT, amount: amt, method: m, type: 'partial', shiftId: w.id, userId: w.user, approverId: appr, reason: pk(REASONS.refund) });
          L({ t: rT, outletId: oid, userId: w.user, type: 'refund', objType: 'order', objId: o.id, objLabel: 'Pesanan #' + o.no, before: fmtR(o.total), after: fmtR(o.total - amt), approverId: appr, reason: db.refunds[db.refunds.length - 1].reason + ' · ' + (m === 'cash' ? 'Tunai' : (OM.PB[m] || {}).label) });
        } else if (r < .02) {
          o.status = 'cancelled'; o.refunded = o.total; const made = R() < .5;
          db.refunds.push({ id: nid('RF'), orderId: o.id, outletId: oid, t: rT, amount: o.total, method: o.method, type: 'cancel', shiftId: w.id, userId: w.user, approverId: appr, reason: pk(REASONS.cancel) });
          if (made) wasteOf(oid, o, rT, 'cancel', o.items);
          L({ t: rT, outletId: oid, userId: w.user, type: 'cancel_order', objType: 'order', objId: o.id, objLabel: 'Pesanan #' + o.no, before: 'Dibayar ' + fmtR(o.total), after: 'Dibatalkan', approverId: appr, reason: db.refunds[db.refunds.length - 1].reason });
        }
      } else if (R() < .015) {
        o.status = 'pcancel'; o.cancelReason = pk(REASONS.pcancel); o.wasted = R() < .5; o.commissionAmount = 0; o.expectedPayout = 0;
        if (o.wasted) wasteOf(oid, o, t + 15 * MIN, 'pcancel', o.items);
        L({ t: t + 15 * MIN, outletId: oid, userId: w.user, type: 'online_cancel', objType: 'order', objId: o.id, objLabel: CHB[o.channel].label + ' ' + o.channelOrderId, before: 'Disiapkan', after: 'Dibatalkan platform', reason: o.cancelReason + (o.wasted ? ' · makanan terbuang' : '') });
      }
    });
    // pesanan terbaru (KDS) per outlet
    const liveW = wins.find(w => w.last);
    const findW = () => liveW;
    const HC = oid === 'kmg' ? [
      [62, { type: 'dine', table: 'T01', items: [['k3', 1, { temp: 'hot' }], ['p1', 1]], status: 'served', method: 'shopeepay' }],
      [48, { type: 'take', items: [['n3', 2], ['k1', 1]], status: 'served', method: 'dana', cust: 'Tom' }],
      [34, { type: 'dine', table: 'T04', items: [['f3', 1], ['k2', 1, { temp: 'hot' }]], status: 'served', method: 'edc', cust: 'Umum' }],
      [16.4, { type: 'take', items: [['k5', 1, { temp: 'hot' }], ['p2', 2]], status: 'ready', method: 'ovo', cust: 'Maya' }],
      [12.6, { type: 'dine', table: 'T09', items: [['f2', 1], ['n1', 1], ['f4', 1]], status: 'cooking', method: 'edc', cust: 'Kevin', done: [1] }],
      [11, { ch: 'grabfood', items: [['k1', 2], ['p3', 1]], status: 'ready', cust: 'Laras', driver: 'Mas Andre' }],
      [7.2, { type: 'dine', table: 'T02', items: [['f1', 1], ['k3', 2, { temp: 'hot' }]], status: 'cooking', method: 'cash', cust: 'Umum', done: [1] }],
      [5, { ch: 'gofood', items: [['k4', 1, { size: 'L' }], ['f1', 1]], status: 'cooking', cust: 'Bima', driver: 'Pak Sutrisno' }],
      [3.5, { type: 'take', items: [['k4', 1, { size: 'L', milk: 'oat' }], ['p3', 1]], status: 'new', method: 'gopay', cust: 'Sari' }],
      [2.1, { type: 'dine', table: 'T08', items: [['k3', 2, { temp: 'hot' }], ['p1', 1]], status: 'pending', source: 'qr', cust: 'Rafi' }],
      [1.2, { type: 'dine', table: 'T07', items: [['k1', 2, { sugar: 'less' }], ['p1', 2]], status: 'new', method: 'edc', cust: 'Andi' }],
      [0.6, { type: 'dine', table: 'T03', items: [['k1', 1, { size: 'L' }], ['n1', 1, { sugar: 'none' }], ['p3', 1]], status: 'pending', source: 'qr', cust: 'Nadia', custNote: 'Tolong cepat ya, mau meeting' }],
    ] : oid === 'snp' ? [
      [9, { type: 'take', items: [['k2', 1], ['p1', 1]], status: 'ready', method: 'edc', cust: 'Gita' }],
      [6, { ch: 'shopeefood', items: [['k1', 2], ['f1', 1]], status: 'cooking', cust: 'Dimas', driver: 'Mas Ilham' }],
      [2, { type: 'dine', table: 'T03', items: [['k4', 1], ['p3', 1]], status: 'new', method: 'cash', cust: 'Eka' }],
    ] : [
      [8, { type: 'dine', table: 'T01', items: [['f1', 1], ['n3', 1]], status: 'cooking', method: 'edc', cust: 'Indra' }],
      [3, { ch: 'grabfood', items: [['k1', 1], ['p2', 2]], status: 'new', cust: 'Kirana', driver: 'Pak Yanto' }],
    ];
    const tb = db.tablesBy[oid];
    HC.forEach(([ago, opt]) => {
      const t = Math.round(now - ago * MIN), w = findW(t);
      if (!w || t < w.a + MIN) return;
      const o = mkOrder(oid, no++, t, w, opt);
      if (opt.done) o.items.forEach((it, i) => { it.done = opt.done.includes(i); });
      if (o.status === 'ready' || o.status === 'served') o.items.forEach(it => { it.done = true; });
      db.orders.push(o);
      if (o.table && ['new', 'cooking', 'ready'].includes(o.status)) { const x = tb[o.table]; tb[o.table] = { status: 'occupied', since: x.status === 'occupied' ? x.since : t, orders: [...(x.status === 'occupied' ? x.orders : []), o.no], note: '' }; }
    });
    if (oid === 'kmg' && liveW) { tb.T04 = { status: 'dirty', since: now - 30 * MIN, orders: [], note: '' }; tb.T11 = { status: 'reserved', since: null, orders: [], note: 'Bu Lina · 4 orang · 19:00' }; }
    db.nextNoBy[oid] = no;

    // kas & tutup shift
    wins.forEach(w => {
      const sh = w.sh, fraud = oid === 'snp' && w.d <= 6, appr = APPR[oid] === w.user ? 'u4' : APPR[oid];
      const at = () => Math.round(w.a + (w.b - w.a) * (0.15 + R() * 0.7));
      if (R() < .3) {
        const exp = R() < .6 ? ['Bahan non-stok', 'Es batu kristal 2 karung', ri(5, 12) * 5000] : ['Transport', 'Parkir & ojek antar barang', ri(2, 8) * 5000];
        const t = at(), cmId = nid('CM'), exId = nid('EX');
        db.cashMoves.push({ id: cmId, shiftId: sh.id, outletId: oid, t, type: 'out', amount: exp[2], category: exp[0], reason: exp[1], userId: w.user, expenseId: exId });
        db.expenses.push({ id: exId, no: exId, outletId: oid, date: t, category: exp[0], desc: exp[1], amount: exp[2], source: 'drawer', shiftId: sh.id, cashMoveId: cmId, receipt: R() < .7 ? 'struk-' + exId.toLowerCase() + '.jpg' : null, recurring: false, seriesId: null, status: 'posted', userId: w.user });
      }
      if (R() < .05) { const t = at(); db.cashMoves.push({ id: nid('CM'), shiftId: sh.id, outletId: oid, t, type: 'in', amount: 100000, category: 'Tambah uang kembalian', reason: 'Pecahan Rp5.000 dari kas kecil', userId: w.user }); }
      if (R() < (fraud ? .4 : .03)) { const t = at(), rs = pk(REASONS.nosale); db.cashMoves.push({ id: nid('CM'), shiftId: sh.id, outletId: oid, t, type: 'nosale', amount: 0, category: '', reason: rs, userId: w.user, approverId: appr }); L({ t, outletId: oid, userId: w.user, type: 'no_sale', objType: 'shift', objId: sh.id, objLabel: 'Shift ' + sh.id, approverId: appr, reason: rs }); }
      if (w.d <= 6) L({ t: w.a, outletId: oid, userId: w.user, type: 'login', objType: 'user', objId: w.user, objLabel: U[w.user].name });
      L({ t: w.a + MIN, outletId: oid, userId: w.user, type: 'shift_open', objType: 'shift', objId: sh.id, objLabel: 'Shift ' + sh.id, after: fmtR(sh.openCash) });
      if (w.last && oid !== 'kmg') { sh.closedAt = null; sh.status = 'open'; return; }
      if (w.last) sh.closedAt = now - MIN;
      if (!w.last) sh.closedAt = w.b;
      const x = shiftCalc(db, sh); IX = {};
      const r = R(); let v = 0;
      if (r < .2) v = (R() < .5 ? -1 : 1) * ri(1, 10) * 500; else if (r < .28) v = -ri(2, 8) * 5000; else if (r < .3) v = R() < .5 ? -ri(5, 12) * 10000 : ri(2, 4) * 10000;
      if (fraud && R() < .4) v = -ri(3, 6) * 10000;
      sh.expected = x.expected; sh.variance = v; sh.counted = x.expected + v;
      const thr = db.settings.varianceThreshold;
      if (Math.abs(v) > thr) { sh.note = pk(REASONS.variance) + (v < 0 ? ' · uang kurang' : ' · uang lebih'); sh.approverId = appr; L({ t: sh.closedAt, outletId: oid, userId: w.user, type: 'shift_variance', objType: 'shift', objId: sh.id, objLabel: 'Shift ' + sh.id, before: 'Seharusnya ' + fmtR(sh.expected), after: 'Dihitung ' + fmtR(sh.counted), approverId: appr, reason: sh.note }); }
      L({ t: sh.closedAt, outletId: oid, userId: w.user, type: 'shift_close', objType: 'shift', objId: sh.id, objLabel: 'Shift ' + sh.id, after: 'Selisih ' + (v ? (v < 0 ? '−' : '+') + fmtR(Math.abs(v)) : 'Rp 0') });
      if (w.d <= 6) L({ t: sh.closedAt + 1000, outletId: oid, userId: w.user, type: 'logout', objType: 'user', objId: w.user, objLabel: U[w.user].name });
      if (w.d > 3 && R() < .75) { sh.status = 'reviewed'; sh.reviewedBy = 'u4'; sh.reviewNote = Math.abs(v) > thr ? 'Sudah dibahas dengan kasir' : 'OK'; }
    });
  });

  // pencairan platform (mingguan per outlet & kanal)
  const wk = t => { const d = new Date(sod(t)); const k = (d.getDay() + 6) % 7; return d.getTime() - k * D; };
  OIDS.forEach(oid => CHANNELS.forEach(c => {
    const g = {};
    db.orders.forEach(o => { if (o.outletId === oid && o.channel === c.id && receivable(o)) { const k = wk(o.expectedPayoutDate); (g[k] = g[k] || []).push(o); } });
    Object.keys(g).map(Number).sort((a, b) => a - b).forEach(k => {
      const end = k + 7 * D; if (end > today - 2 * D) return;
      if (oid === 'kmg' && c.id === 'gofood' && end > today - 12 * D) return;
      const os = g[k], exp = os.reduce((a, o) => a + o.expectedPayout, 0); const r = R();
      const diff = r < .15 ? -ri(2, 15) * 1000 : r < .2 ? -ri(20, 60) * 1000 : 0;
      const st = { id: nid('PC'), no: null, outletId: oid, channel: c.id, receivedAt: end + D + 10 * H, amount: exp + diff, expected: exp, diff, reason: diff ? (r < .15 ? pk(['Biaya promo merchant', 'Penyesuaian komisi']) : 'Pesanan dibatalkan platform') : '', orderIds: os.map(o => o.id), userId: 'u4' };
      st.no = st.id; db.settlements.push(st); os.forEach(o => { o.settlementId = st.id; });
      L({ t: st.receivedAt, outletId: oid, userId: 'u4', type: 'settlement', objType: 'settlement', objId: st.id, objLabel: c.label + ' ' + st.id, before: 'Diharapkan ' + fmtR(exp), after: 'Diterima ' + fmtR(st.amount), reason: st.reason });
    });
  }));

  // pembelian & hutang
  const PLAN = { s1: [14, 'h30'], s2: [7, 'h14'], s3: [7, 'tunai'], s4: [7, 'h7'], s5: [14, 'h30'] };
  const TD = Object.fromEntries(TERMS.map(t => [t.id, t.days]));
  const recs = [];
  OIDS.forEach((oid, k) => Object.entries(PLAN).forEach(([sup, [ev, term]]) => {
    for (let d = 56 - k * 2 - (sup.charCodeAt(1) % 3); d >= 2; d -= ev) recs.push({ oid, sup, term, d });
  }));
  recs.sort((a, b) => b.d - a.d);
  recs.forEach(rc => {
    const lines = OM.INGS.filter(i => i.sup === rc.sup).map(i => ({ ing: i.id, qty: i.unit === 'pcs' ? Math.round(i.par * (1.5 + R())) : Math.round(i.par * (1.5 + R()) * 2) / 2, cost: i.cost }));
    const total = Math.round(lines.reduce((a, l) => a + l.qty * l.cost, 0)), rcv = today - rc.d * D + 10 * H, no = nid('PO');
    const pay = { id: nid('AP'), poId: no, poNo: no, outletId: rc.oid, sup: rc.sup, invoiceNo: 'INV/' + rc.sup.toUpperCase() + '/' + ri(1000, 9999), invoiceDate: sod(rcv), term: rc.term, termDays: TD[rc.term], dueDate: sod(rcv) + TD[rc.term] * D, total, paid: 0 };
    db.pos.push({ id: no, no, outletId: rc.oid, sup: rc.sup, lines, status: 'received', createdAt: rcv - D, eta: 'Diterima', term: rc.term, termDays: TD[rc.term], receivedAt: rcv, invoiceNo: pay.invoiceNo, payableId: pay.id });
    db.payables.push(pay);
    const P = (t, amt, src) => { db.payPayments.push({ id: nid('PP'), payableId: pay.id, outletId: rc.oid, t, amount: amt, source: src, shiftId: null, userId: 'u4' }); pay.paid += amt; };
    if (rc.term === 'tunai') P(rcv, total, 'petty');
    else if (pay.dueDate < today) { const r = R(); if (r < .78) P(Math.min(pay.dueDate - ri(0, 2) * D + 11 * H, now), total, 'bank'); else if (r < .9) P(pay.dueDate - D + 11 * H, Math.round(total / 2), 'bank'); }
    else if (R() < .15) P(rcv + D, Math.round(total / 2), 'bank');
  });
  [['kmg', 's5', 100, 30, 3250000, 0], ['snp', 's1', 70, 30, 4860000, 2000000], ['bsd', 's2', 40, 14, 1720000, 0]].forEach(([oid, sup, ago, days, total, paid]) => {
    const p = { id: nid('AP'), poId: null, poNo: 'Saldo awal', outletId: oid, sup, invoiceNo: 'INV/' + sup.toUpperCase() + '/' + ri(1000, 9999), invoiceDate: today - ago * D, term: days === 30 ? 'h30' : 'h14', termDays: days, dueDate: today - ago * D + days * D, total, paid: 0 };
    db.payables.push(p); if (paid) { db.payPayments.push({ id: nid('PP'), payableId: p.id, outletId: oid, t: p.dueDate + 3 * D, amount: paid, source: 'bank', shiftId: null, userId: 'u4' }); p.paid = paid; }
  });
  const kPo = (sup, st, ago, eta, oid, term) => { const no = nid('PO'); db.pos.push({ id: no, no, outletId: oid, sup, lines: OM.INGS.filter(i => i.sup === sup).slice(0, 3).map(i => ({ ing: i.id, qty: i.unit === 'pcs' ? Math.round(i.par * 1.5) : Math.round(i.par * 3) / 2, cost: i.cost })), status: st, createdAt: now - ago, eta, term, termDays: TD[term], receivedAt: null, invoiceNo: '', payableId: null }); };
  kPo('s1', 'sent', 20 * H, 'Besok', 'kmg', 'h30'); kPo('s2', 'draft', 30 * MIN, '—', 'kmg', 'h14'); kPo('s4', 'sent', 3 * H, 'Hari ini', 'snp', 'h7');

  // pengeluaran rutin
  const REC = [
    ['Sewa', 'Sewa tempat bulanan', 1, { kmg: 35000000, snp: 45000000, bsd: 25000000 }, 'bank', false],
    ['Internet & software', 'Internet + langganan Omnify Pro', 3, { kmg: 1150000, snp: 1150000, bsd: 1150000 }, 'bank', false],
    ['Listrik & air', 'Tagihan PLN & PDAM', 6, { kmg: 5200000, snp: 6400000, bsd: 4100000 }, 'bank', true],
    ['Lain-lain', 'Iuran keamanan & kebersihan', 10, { kmg: 300000, snp: 450000, bsd: 250000 }, 'petty', false],
    ['Gaji & upah', 'Gaji karyawan', 25, { kmg: 26000000, snp: 31000000, bsd: 19000000 }, 'bank', false],
  ];
  const nd = new Date(now);
  OIDS.forEach(oid => REC.forEach(([cat, desc, day, amt, src, varAmt]) => {
    const series = 'RS-' + oid + '-' + cat.replace(/\W/g, '');
    let drafted = false;
    for (let mo = -3; mo <= 1; mo++) {
      const dt = new Date(nd.getFullYear(), nd.getMonth() + mo, day, 9).getTime();
      if (dt < now - 62 * D) continue;
      const a = varAmt ? Math.round(amt[oid] * (0.9 + R() * 0.25) / 1000) * 1000 : amt[oid];
      if (dt <= now) { const id = nid('EX'); db.expenses.push({ id, no: id, outletId: oid, date: dt, category: cat, desc, amount: a, source: src, shiftId: null, cashMoveId: null, receipt: 'bukti-' + id.toLowerCase() + '.pdf', recurring: true, seriesId: series, status: 'posted', userId: 'u4' }); }
      else if (!drafted) { drafted = true; const id = nid('EX'); db.expenses.push({ id, no: id, outletId: oid, date: dt, category: cat, desc, amount: amt[oid], source: src, shiftId: null, cashMoveId: null, receipt: null, recurring: true, seriesId: series, status: 'draft', userId: 'u4' }); }
    }
  }));
  [['snp', 'Marketing', 'Endorse influencer kuliner', 2500000, 'ewallet', 18], ['kmg', 'Marketing', 'Cetak menu & poster promo', 850000, 'petty', 26], ['kmg', 'Perbaikan & perawatan', 'Servis mesin espresso', 1200000, 'bank', 9], ['bsd', 'Perbaikan & perawatan', 'Ganti selang AC', 450000, 'petty', 33]].forEach(([oid, cat, desc, a, src, ago]) => { const id = nid('EX'); db.expenses.push({ id, no: id, outletId: oid, date: today - ago * D + 11 * H, category: cat, desc, amount: a, source: src, shiftId: null, cashMoveId: null, receipt: 'bukti-' + id.toLowerCase() + '.jpg', recurring: false, seriesId: null, status: 'posted', userId: 'u3' }); });

  // transfer, mutasi, opname, log lain
  db.transfers.push({ id: 'TR-0001', no: 'TR-0001', from: 'kmg', to: 'snp', lines: [{ ing: 'milk', qty: 10, recv: 9.5 }, { ing: 'croissant', qty: 12, recv: 12 }], status: 'received', requestedAt: today - 6 * D + 9 * H, requestedBy: 'u3', sentAt: today - 5 * D + 8 * H, sentBy: 'u1', receivedAt: today - 5 * D + 11 * H, receivedBy: 'u5', note: '' });
  db.transfers.push({ id: 'TR-0002', no: 'TR-0002', from: 'snp', to: 'bsd', lines: [{ ing: 'espresso', qty: 1, recv: null }, { ing: 'oat', qty: 3, recv: null }], status: 'sent', requestedAt: today - D + 15 * H, requestedBy: 'u6', sentAt: now - 3 * H, sentBy: 'u5', receivedAt: null, receivedBy: null, note: '' });
  db.transfers.push({ id: 'TR-0003', no: 'TR-0003', from: 'kmg', to: 'bsd', lines: [{ ing: 'cup', qty: 100, recv: null }], status: 'requested', requestedAt: now - 2 * H, requestedBy: 'u6', sentAt: null, sentBy: null, receivedAt: null, receivedBy: null, note: 'Cup habis sebelum PO datang' });
  db.seq.TR = 3;
  L({ t: today - 5 * D + 11 * H, outletId: 'snp', userId: 'u5', type: 'transfer', objType: 'transfer', objId: 'TR-0001', objLabel: 'TR-0001 Kemang → Senopati', before: 'Dikirim 10 L susu segar', after: 'Diterima 9,5 L (selisih −0,5 L)', reason: 'Selisih saat penerimaan' });
  db.moves.push({ t: now - 190 * MIN, outletId: 'kmg', ing: 'bread', d: 30, reason: 'Penerimaan PO pagi' }, { t: now - 190 * MIN, outletId: 'kmg', ing: 'donut', d: 12, reason: 'Penerimaan PO pagi' }, { t: now - 150 * MIN, outletId: 'kmg', ing: 'milk', d: -1, reason: 'Terbuang · kedaluwarsa' }, { t: now - 120 * MIN, outletId: 'kmg', ing: 'croissant', d: -2, reason: 'Terbuang · rusak' }, { t: now - 3 * H, outletId: 'snp', ing: 'espresso', d: -1, reason: 'Transfer keluar TR-0002 → BSD' }, { t: now - 3 * H, outletId: 'snp', ing: 'oat', d: -3, reason: 'Transfer keluar TR-0002 → BSD' });
  [[7, -184000, 'kmg', 'u3'], [14, -96500, 'kmg', 'u3'], [8, -142000, 'snp', 'u3'], [10, -61000, 'bsd', 'u4']].forEach(([ago, v, oid, by]) => { const no = nid('SO'); db.opnames.push({ no, t: today - ago * D + 21 * H, items: 20, varianceVal: v, by: U[by].name, outletId: oid }); L({ t: today - ago * D + 21 * H, outletId: oid, userId: by, type: 'stock_adjust', objType: 'opname', objId: no, objLabel: 'Stock opname ' + no, before: '20 bahan', after: 'Selisih ' + fmtR(v), approverId: by === 'u3' ? 'u3' : 'u4', reason: 'Hasil stock opname' }); });
  db.opnames.sort((a, b) => b.t - a.t);
  L({ t: today - 20 * D + 10 * H, outletId: null, userId: 'u4', type: 'price_change', objType: 'product', objId: 'k3', objLabel: 'Cappuccino · harga dasar', before: fmtR(30000), after: fmtR(32000), device: 'iPhone Arif' });
  L({ t: today - 15 * D + 14 * H, outletId: 'snp', userId: 'u3', type: 'price_change', objType: 'product', objId: 'k5', objLabel: 'Manual Brew V60 · harga Senopati', before: fmtR(38000), after: fmtR(42000) });
  L({ t: today - 12 * D + 9 * H, outletId: null, userId: 'u3', type: 'recipe_change', objType: 'product', objId: 'k1', objLabel: 'Kopi Susu Aren · resep', before: 'Gula aren cair 25 ml', after: 'Gula aren cair 30 ml' });
  L({ t: today - 30 * D + 20 * H, outletId: null, userId: 'u4', type: 'settings_change', objType: 'settings', objId: 'grabfood', objLabel: 'Kanal GrabFood · komisi', before: '18%', after: '20%' });
  L({ t: today - 45 * D + 9 * H, outletId: null, userId: 'u4', type: 'permission_change', objType: 'user', objId: 'u3', objLabel: 'Dewi · outlet', before: 'Kemang', after: 'Kemang, Senopati' });
  L({ t: today - 25 * D + 9 * H, outletId: null, userId: 'u4', type: 'settings_change', objType: 'settings', objId: 'policy', objLabel: 'Batas selisih kas', before: fmtR(25000), after: fmtR(20000) });
  const ACT = { pending: 1, new: 1, cooking: 1, ready: 1, picked: 1 };
  db.orders.forEach(o => {
    if (ACT[o.status]) return;
    o.items = o.items.map(l => { const x = { id: l.id, qty: l.qty, price: l.price }; if (l.mods && (l.mods.size === 'L' || l.mods.milk === 'oat' || l.mods.sugar !== 'normal' || l.mods.temp === 'hot')) x.mods = l.mods; if (l.voidQty) x.voidQty = l.voidQty; return x; });
    ['discLabel', 'custNote', 'appNote'].forEach(k => { if (!o[k]) delete o[k]; }); if (!o.discPct) delete o.discPct; if (!o.refunded) delete o.refunded;
  });
  db.orders.sort((a, b) => b.createdAt - a.createdAt);
  db.logs.sort((a, b) => b.t - a.t);
  db.expenses.sort((a, b) => b.date - a.date);
  db.pos.sort((a, b) => b.createdAt - a.createdAt);
  db.shifts.sort((a, b) => b.openedAt - a.openedAt);
  IX = {};
  return db;
}
function fmtR(n) { return (n < 0 ? '−' : '') + 'Rp ' + Math.round(Math.abs(n)).toLocaleString('id-ID'); }

window.OS = { VER, D, H, MIN, sod, clone, r500, OUTLETS, USERS, ROLES, PAGE_ROLES, HOME, PERM_ROWS, CHANNELS, CHB, isOnline, EXP_CATS, FUNDS, FB, TERMS, DENOMS, CASH_IN_CATS, CASH_OUT_NONEXP, REASONS, LOG_TYPES,
  outletOf, carried, outletPrice, autoChPrice, chPrice, modAdd, modsStr, lineQty, calcTot, validSale, revenueOf, netOf, usage, costOf, index, shiftCalc, payStatus, overdueDays, aging, receivable,
  DBK, load, save, loadSess, saveSess, seed, fmtR };
})();
