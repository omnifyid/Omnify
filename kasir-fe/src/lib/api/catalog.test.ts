import { describe, expect, it } from 'vitest';
import { toAddonGroupsPayload, toCategoryPayload, toItemUpdatePayload, toOptionGroupsPayload } from './catalog';

describe('toCategoryPayload', () => {
  it('trims category name and omits an empty icon', () => {
    expect(toCategoryPayload({ name: '  Coffee  ', icon: '  ' })).toEqual({ name: 'Coffee' });
  });
});

describe('toAddonGroupsPayload', () => {
  it('keeps addon names and integer extra prices for backend sync', () => {
    expect(
      toAddonGroupsPayload([
        {
          name: 'Extras',
          min_select: 0,
          max_select: 2,
          choices: [
            { name: 'Extra Shot', extra_price: 5000 },
            { name: '  ', extra_price: 1000 }
          ]
        }
      ])
    ).toEqual([
      {
        name: 'Extras',
        min_select: 0,
        max_select: 2,
        choices: [{ name: 'Extra Shot', extra_price: 5000 }]
      }
    ]);
  });
});

describe('toItemUpdatePayload', () => {
  it('trims product names and normalizes empty category to null', () => {
    expect(toItemUpdatePayload({ name: '  Latte  ', categoryId: '' })).toEqual({ name: 'Latte', category_id: null });
  });
});

describe('toOptionGroupsPayload', () => {
  it('keeps option group labels and removes empty choices', () => {
    expect(
      toOptionGroupsPayload([
        {
          name: 'Sugar Level',
          required: true,
          choices: [{ name: 'Normal' }, { name: '  ' }]
        }
      ])
    ).toEqual([
      {
        name: 'Sugar Level',
        required: true,
        choices: [{ name: 'Normal' }]
      }
    ]);
  });
});
