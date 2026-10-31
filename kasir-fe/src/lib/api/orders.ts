import type { OrderChannel, PaymentMethod } from './types';

export type CartOrderItem = {
  itemId: string;
  quantity: number;
  optionChoiceIds?: string[];
  addonChoiceIds?: string[];
};

export function toOrderPayload(input: {
  paymentMethod?: PaymentMethod;
  paymentProvider?: string | null;
  discountCode?: string;
  items: CartOrderItem[];
  orderType?: 'DINE_IN' | 'TAKE_AWAY' | null;
  tableNumber?: string | null;
  customerName?: string | null;
  notes?: string | null;
  channel?: OrderChannel | null;
  channelOrderId?: string | null;
  appTotal?: number | null;
  driverName?: string | null;
  cashReceived?: number | null;
}) {
  return {
    payment_method: input.channel ? undefined : input.paymentMethod,
    payment_provider: input.channel ? undefined : input.paymentProvider || undefined,
    discount_code: input.channel ? undefined : input.discountCode?.trim() || undefined,
    items: input.items.map((item) => ({
      item_id: item.itemId,
      quantity: item.quantity,
      selected_option_choice_ids: item.optionChoiceIds ?? [],
      selected_addon_choice_ids: item.addonChoiceIds ?? []
    })),
    order_type: input.orderType ?? null,
    table_number: input.tableNumber ?? null,
    customer_name: input.customerName ?? null,
    notes: input.notes ?? null,
    channel: input.channel ?? null,
    channel_order_id: input.channelOrderId?.trim() || null,
    app_total: input.appTotal ?? null,
    cash_received: input.cashReceived ?? null,
    driver_name: input.driverName?.trim() || null
  };
}
