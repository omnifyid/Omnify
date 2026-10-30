export const EXPENSE_CATEGORIES = [
  'Sewa',
  'Listrik & air',
  'Gaji & upah',
  'Bahan non-stok',
  'Marketing',
  'Perbaikan & perawatan',
  'Transport',
  'Internet & software',
  'Lain-lain'
];

export const CASH_IN_CATEGORIES = ['Tambah uang kembalian', 'Dari kas kecil', 'Setoran pemilik', 'Lain-lain'];
export const CASH_OUT_TRANSFERS = ['Setor ke bank', 'Pindah ke kas kecil'];

export const digitsOnly = (v: string) => v.replace(/\D/g, '');

/** Formats typed digits with id-ID thousands dots; returns '' for empty. */
export const formatDigits = (v: string) => {
  const d = digitsOnly(v);
  return d ? parseInt(d, 10).toLocaleString('id-ID') : '';
};

export const parseAmount = (v: string) => parseInt(digitsOnly(v) || '0', 10);
