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
        sort_order: 0,
        choices: [{ label: 'Extra Shot', extra_price: 5000, sort_order: 0 }]
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
          choices: [{ name: 'Normal', is_default: true }, { name: '  ' }]
        }
      ])
    ).toEqual([
      {
        name: 'Sugar Level',
        is_required: true,
        sort_order: 0,
        choices: [{ label: 'Normal', is_default: true, sort_order: 0 }]
      }
    ]);
  });
});

import { toModifierPayloads } from './catalog';

describe('toModifierPayloads', () => {
  it('splits single-choice groups into options and multi-choice groups into add-ons', () => {
    const out = toModifierPayloads([
      { name: 'Ukuran', required: true, multi: false, max: null, choices: [{ name: 'Reguler', extra_price: 0, is_default: true }, { name: 'Besar', extra_price: 6000, is_default: false }] },
      { name: 'Topping', required: false, multi: true, max: 2, choices: [{ name: 'Boba', extra_price: 5000, is_default: false }, { name: ' ', extra_price: 0, is_default: false }] },
      { name: '', required: false, multi: false, max: null, choices: [] }
    ]);
    expect(out.option_groups).toHaveLength(1);
    expect(out.option_groups[0].choices[1]).toMatchObject({ label: 'Besar', extra_price: 6000 });
    expect(out.addon_groups).toEqual([
      { name: 'Topping', is_required: false, min_select: 0, max_select: 2, sort_order: 0, choices: [{ label: 'Boba', extra_price: 5000, is_default: false, sort_order: 0 }] }
    ]);
  });
});
