export const PAGE_SIZE = 20;

export const pageCount = (total: number, size = PAGE_SIZE) => Math.max(1, Math.ceil(total / size));

/** Rows of a 1-based page; the page is clamped so a shrinking list never strands the user. */
export function slicePage<T>(rows: T[], page: number, size = PAGE_SIZE): T[] {
  const p = Math.min(Math.max(1, page), pageCount(rows.length, size));
  return rows.slice((p - 1) * size, p * size);
}
