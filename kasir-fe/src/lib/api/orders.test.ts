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
          option_choice_ids: ['less-sugar'],
          addon_choice_ids: ['extra-shot']
        }
      ]
    });
  });
});
