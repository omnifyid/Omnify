type PricedItem = {
  price?: number | string | null;
  base_price?: number | string | null;
  [key: string]: unknown;
};

export function getItemPrice(item: PricedItem) {
  const value = item.price ?? item.base_price ?? 0;
  const numericValue = typeof value === 'string' ? Number(value) : value;
  return Number.isFinite(numericValue) ? numericValue : 0;
}
