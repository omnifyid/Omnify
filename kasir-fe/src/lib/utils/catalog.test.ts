import { describe, expect, it } from 'vitest';
import { getItemPrice } from './catalog';

describe('getItemPrice', () => {
  it('uses backend base_price when item price is not present', () => {
    expect(getItemPrice({ id: '1', name: 'Latte', base_price: 25000 })).toBe(25000);
  });
});
