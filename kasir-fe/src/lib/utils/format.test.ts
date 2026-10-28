import { describe, expect, it } from 'vitest';
import { formatDateTime, formatRupiah } from './format';

describe('formatRupiah', () => {
  it('formats integer rupiah amounts without decimal digits', () => {
    expect(formatRupiah(125000)).toBe('Rp125.000');
  });
});

describe('formatDateTime', () => {
  it('formats ISO timestamps for Indonesian locale display', () => {
    expect(formatDateTime('2026-05-03T10:30:00.000Z')).toContain('2026');
  });
});
