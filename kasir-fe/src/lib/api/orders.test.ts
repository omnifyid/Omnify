import { describe, expect, it } from 'vitest';
import { toOrderPayload } from './orders';

describe('toOrderPayload', () => {
  it('converts cart items into the backend order creation shape', () => {
    const payload = toOrderPayload({
      paymentMethod: 'QRIS',
      discountCode: 'HEMAT10',
      items: [
        {
          itemId: 'item-1',
          quantity: 2,
          optionChoiceIds: ['less-sugar'],
          addonChoiceIds: ['extra-shot']
        }
      ]
    });

    expect(payload).toEqual({
      payment_method: 'QRIS',
      discount_code: 'HEMAT10',
      items: [
        {
          item_id: 'item-1',
          quantity: 2,
          selected_option_choice_ids: ['less-sugar'],
          selected_addon_choice_ids: ['extra-shot'],
          note: null
        }
      ],
      order_type: null,
      table_number: null,
      customer_name: null,
      guest_count: null,
      segment: null,
      notes: null,
      channel: null,
      channel_order_id: null,
      app_total: null,
      cash_received: null,
      driver_name: null
    });
  });

  it('drops payment method and discount for online orders and keeps the driver', () => {
    const payload = toOrderPayload({
      paymentMethod: 'CASH',
      discountCode: 'X',
      channel: 'GOFOOD',
      channelOrderId: ' F-1 ',
      driverName: ' Budi ',
      items: [{ itemId: 'item-1', quantity: 1 }]
    });

    expect(payload.payment_method).toBeUndefined();
    expect(payload.discount_code).toBeUndefined();
    expect(payload.channel_order_id).toBe('F-1');
    expect(payload.driver_name).toBe('Budi');
  });
});
