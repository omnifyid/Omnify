import type { Order, PaymentMethod, Store } from '$lib/api/types';

export type MethodVariants = { enabled: boolean; options: string[] };
export type PaymentOptions = { cash: boolean; edc: MethodVariants; qris: MethodVariants; transfer: boolean };

// same bank list for EDC and QRIS
export const BANK_PRESETS = ['BCA', 'Mandiri', 'BNI', 'BRI', 'BSI', 'CIMB Niaga', 'Permata', 'BTN'];
export const QRIS_WALLET_PRESETS = ['GoPay', 'OVO', 'DANA', 'ShopeePay', 'LinkAja'];

export const paymentOptions = (store?: Pick<Store, 'payment_options'> | null): PaymentOptions => {
  const o = store?.payment_options;
  return {
    cash: o?.cash ?? true,
    edc: { enabled: o?.edc?.enabled ?? true, options: o?.edc?.options ?? [] },
    qris: { enabled: o?.qris?.enabled ?? true, options: o?.qris?.options ?? [] },
    transfer: o?.transfer ?? true
  };
};

/** Methods the POS offers, in display order. */
export const enabledMethods = (o: PaymentOptions): PaymentMethod[] => [
  ...(o.cash ? (['CASH'] as const) : []),
  ...(o.edc.enabled ? (['CARD'] as const) : []),
  ...(o.qris.enabled ? (['QRIS'] as const) : []),
  ...(o.transfer ? (['TRANSFER'] as const) : [])
];

/** EDC banks / QRIS providers to pick from for a method (empty = no choice). */
export const providersFor = (o: PaymentOptions, m: PaymentMethod): string[] =>
  m === 'CARD' ? o.edc.options : m === 'QRIS' ? o.qris.options : [];

/** "QRIS · GoPay" / "CARD · BCA" / "CASH". */
export const paymentText = (order: Pick<Order, 'payment_method' | 'payment_provider'>) =>
  order.payment_provider ? `${order.payment_method} · ${order.payment_provider}` : order.payment_method;
