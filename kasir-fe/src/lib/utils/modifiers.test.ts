import { describe, expect, it } from 'vitest';
import { getAddonPriceTotal, getChoiceLabel, getGroupChoices, getGroupLabel, hasItemModifiers } from './modifiers';

describe('hasItemModifiers', () => {
  it('detects items with option choices', () => {
    expect(hasItemModifiers({ option_groups: [{ id: 'size', name: 'Size', choices: [{ id: 'hot', name: 'Hot' }] }] })).toBe(true);
  });
});

describe('getAddonPriceTotal', () => {
  it('sums selected addon prices', () => {
    expect(
      getAddonPriceTotal(
        { addon_groups: [{ id: 'extras', name: 'Extras', choices: [{ id: 'shot', name: 'Extra Shot', extra_price: 5000 }] }] },
        ['shot']
      )
    ).toBe(5000);
  });
});

describe('modifier labels', () => {
  it('uses label fields when name fields are not present', () => {
    expect(getGroupLabel({ id: 'size', label: 'Size' })).toBe('Size');
    expect(getChoiceLabel({ id: 'large', label: 'Large' })).toBe('Large');
  });

  it('reads option_choices as a choice list alias', () => {
    expect(getGroupChoices({ id: 'size', name: 'Size', option_choices: [{ id: 'large', label: 'Large' }] })).toEqual([
      { id: 'large', label: 'Large' }
    ]);
  });
});
