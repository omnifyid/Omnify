import { describe, expect, it } from 'vitest';

import { paginatedItems } from './pagination';

describe('paginatedItems', () => {
  it('returns the items from a paginated response', () => {
    const orders = [{ id: 'order-1' }, { id: 'order-2' }];

    expect(paginatedItems({ items: orders, total: 2, limit: 50, offset: 0 })).toBe(orders);
  });
});
