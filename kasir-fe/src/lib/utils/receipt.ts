import type { Order, Store } from '$lib/api/types';
import { paymentText } from '$lib/utils/payment';
import { language } from '$lib/i18n/language.svelte';
import { formatDateTime, formatRupiah } from '$lib/utils/format';

/** Paper width and which lines the customer receipt and kitchen ticket print (stored on the store). */
export type ReceiptOptions = {
  paper: '58' | '80';
  show_addr: boolean;
  show_phone: boolean;
  show_cashier: boolean;
  show_cust: boolean;
  show_no: boolean;
  show_mods: boolean;
  show_tax: boolean;
  show_pay: boolean;
  k_title: string;
  k_outlet: boolean;
  k_server: boolean;
  k_cust: boolean;
};

export const RECEIPT_DEFAULTS: ReceiptOptions = {
  paper: '58',
  show_addr: true,
  show_phone: true,
  show_cashier: true,
  show_cust: true,
  show_no: true,
  show_mods: true,
  show_tax: true,
  show_pay: true,
  k_title: 'Pesanan Baru',
  k_outlet: true,
  k_server: true,
  k_cust: true
};

type StoreLike = Pick<
  Store,
  'name' | 'logo_url' | 'show_logo' | 'address' | 'phone' | 'receipt_header' | 'receipt_footer' | 'receipt_options'
>;

export const receiptOptions = (store?: Pick<Store, 'receipt_options'> | null): ReceiptOptions => ({
  ...RECEIPT_DEFAULTS,
  ...(store?.receipt_options ?? {})
});

/** Printable characters per line: 32 on 58 mm paper, 48 on 80 mm. */
export const paperChars = (o: ReceiptOptions) => (o.paper === '80' ? 48 : 32);

/** One printed line. The preview, browser print and ESC/POS all render this same list. */
export type ReceiptLine =
  | { t: 'logo'; url: string }
  | { t: 'text'; text: string; align?: 'left' | 'center'; bold?: boolean; big?: boolean; muted?: boolean; indent?: boolean }
  | { t: 'row'; left: string; right: string; bold?: boolean; big?: boolean; muted?: boolean; accent?: 'discount' }
  | { t: 'rule' };

export function snapshotNames(snapshot: unknown[] | null | undefined): string {
  if (!snapshot?.length) return '';
  return snapshot
    .map((e) => {
      if (typeof e === 'string') return e;
      if (e && typeof e === 'object') {
        const r = e as Record<string, unknown>;
        return String(r.name ?? r.label ?? r.choice_name ?? r.item_name ?? '');
      }
      return '';
    })
    .filter(Boolean)
    .join(', ');
}

const lines_ = (text: string | null | undefined) => (text ?? '').split('\n').map((l) => l.trim()).filter(Boolean);
const orderNo = (o: Order) => o.order_number ?? o.id.slice(0, 8);

/** Where the order is eaten: platform name, dine-in with table, or take away. */
export function orderWhere(order: Order): string {
  if (order.channel) return order.channel;
  if (order.order_type === 'DINE_IN') return `${language.t('txDineIn')}${order.table_number ? ` · ${order.table_number}` : ''}`;
  if (order.order_type === 'TAKE_AWAY') return language.t('txTakeAway');
  return '';
}

export function customerReceipt(order: Order, store: StoreLike, o: ReceiptOptions, cashPaid = 0): ReceiptLine[] {
  const t = language.t.bind(language);
  const out: ReceiptLine[] = [];
  out.push({ t: 'text', text: store.name, align: 'center', bold: true, big: true });
  if (o.show_addr) lines_(store.address).forEach((text) => out.push({ t: 'text', text, align: 'center', muted: true }));
  if (o.show_phone && store.phone?.trim()) out.push({ t: 'text', text: store.phone.trim(), align: 'center', muted: true });
  out.push({ t: 'rule' });

  if (order.created_at) out.push({ t: 'text', text: formatDateTime(order.created_at) });
  if (o.show_no) out.push({ t: 'row', left: t('receiptNo'), right: `#${orderNo(order)}` });
  if (o.show_cashier && order.operator_name) out.push({ t: 'row', left: t('receiptCashier'), right: order.operator_name });
  if (o.show_cust && order.customer_name) out.push({ t: 'row', left: t('customerName'), right: order.customer_name });
  const where = orderWhere(order);
  if (where) out.push({ t: 'row', left: t('serviceOption'), right: where });
  out.push({ t: 'rule' });

  for (const item of order.items ?? []) {
    out.push({ t: 'row', left: `${item.item_name_snapshot} x${item.quantity}`, right: formatRupiah(item.line_total ?? 0) });
    const mods = [snapshotNames(item.options_snapshot), snapshotNames(item.addons_snapshot)].filter(Boolean).join(', ');
    if (o.show_mods && mods) out.push({ t: 'text', text: mods, muted: true, indent: true });
    if (o.show_mods && item.note) out.push({ t: 'text', text: `“${item.note}”`, muted: true, indent: true });
    if ((item.item_discount_amount ?? 0) > 0) {
      out.push({ t: 'row', left: `  ${t('discounts')}`, right: `-${formatRupiah(item.item_discount_amount ?? 0)}`, accent: 'discount' });
    }
  }
  out.push({ t: 'rule' });

  const itemDisc = (order.items ?? []).reduce((s, i) => s + (i.item_discount_amount ?? 0), 0);
  const service = o.show_tax ? (order.service_amount ?? 0) : 0;
  const pb1 = o.show_tax ? (order.pb1_amount ?? 0) : 0;
  if ((order.discount_amount ?? 0) > 0 || itemDisc > 0 || service > 0 || pb1 > 0) {
    out.push({ t: 'row', left: t('subtotal'), right: formatRupiah(order.subtotal ?? 0) });
  }
  if (itemDisc > 0) out.push({ t: 'row', left: t('discounts'), right: `-${formatRupiah(itemDisc)}`, accent: 'discount' });
  if ((order.discount_amount ?? 0) > 0) {
    const code = order.discount_code_snapshot ? ` (${order.discount_code_snapshot})` : '';
    out.push({ t: 'row', left: `${t('discounts')}${code}`, right: `-${formatRupiah(order.discount_amount ?? 0)}`, accent: 'discount' });
  }
  if (service > 0) out.push({ t: 'row', left: t('serviceLabel'), right: formatRupiah(service) });
  if (pb1 > 0) out.push({ t: 'row', left: t('pb1Label'), right: formatRupiah(pb1) });
  out.push({ t: 'row', left: t('total').toUpperCase(), right: formatRupiah(order.total_amount), bold: true, big: true });

  if (o.show_pay) {
    out.push({ t: 'row', left: t('payment'), right: paymentText(order) });
    const tendered = order.cash_received ?? cashPaid;
    if (tendered > 0) {
      out.push({ t: 'row', left: t('cash'), right: formatRupiah(tendered) });
      out.push({ t: 'row', left: t('change'), right: formatRupiah(tendered - order.total_amount), bold: true });
    }
  }
  out.push({ t: 'rule' });

  out.push({ t: 'text', text: t('thankYou'), align: 'center', muted: true });
  return out;
}

export function kitchenTicket(order: Order, store: StoreLike, o: ReceiptOptions): ReceiptLine[] {
  const t = language.t.bind(language);
  const out: ReceiptLine[] = [{ t: 'text', text: o.k_title.trim() || RECEIPT_DEFAULTS.k_title, align: 'center', bold: true }];
  if (o.k_outlet) out.push({ t: 'text', text: store.name, align: 'center', muted: true });
  out.push({ t: 'text', text: `#${orderNo(order)}`, align: 'center', bold: true, big: true });
  if (order.created_at) out.push({ t: 'text', text: formatDateTime(order.created_at), align: 'center', muted: true });
  out.push({ t: 'rule' });
  const where = orderWhere(order);
  if (where) out.push({ t: 'text', text: where, bold: true });
  if (o.k_cust && order.customer_name) out.push({ t: 'text', text: order.customer_name });
  if (o.k_server && order.operator_name) out.push({ t: 'text', text: `${t('servedBy')}: ${order.operator_name}` });
  out.push({ t: 'rule' });
  for (const item of order.items ?? []) {
    const left = item.quantity - (item.void_qty ?? 0);
    if (left <= 0) continue;
    out.push({ t: 'text', text: `${left}x ${item.item_name_snapshot}`, bold: true });
    const mods = [snapshotNames(item.options_snapshot), snapshotNames(item.addons_snapshot)].filter(Boolean).join(', ');
    if (mods) out.push({ t: 'text', text: mods, muted: true, indent: true });
    if (item.note) out.push({ t: 'text', text: `“${item.note}”`, muted: true, indent: true });
  }
  if (order.notes?.trim()) {
    out.push({ t: 'rule' });
    out.push({ t: 'text', text: `${t('txTicketNote')}: ${order.notes.trim()}` });
  }
  return out;
}

/** Sample order for the settings preview when the store has no real one. */
export function sampleOrder(): Order {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    order_number: 'ORD-20260519-00001',
    status: 'COMPLETED',
    payment_method: 'CASH',
    subtotal: 70000,
    discount_amount: 0,
    total_amount: 77000,
    service_amount: 0,
    pb1_amount: 7000,
    cash_received: 100000,
    operator_name: 'Sari Dewi',
    customer_name: 'Budi Santoso',
    order_type: 'DINE_IN',
    table_number: '5',
    notes: 'Kurang manis',
    created_at: new Date().toISOString(),
    items: [
      {
        id: 'i1', item_name_snapshot: 'Kopi Susu', quantity: 1, unit_price_snapshot: 30000, line_total: 30000,
        options_snapshot: [{ label: 'Es' }, { label: 'Less Sugar' }], addons_snapshot: [{ label: 'Extra Shot' }]
      },
      { id: 'i2', item_name_snapshot: 'Americano', quantity: 2, unit_price_snapshot: 20000, line_total: 40000 }
    ]
  } as Order;
}
