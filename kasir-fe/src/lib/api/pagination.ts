import type { PaginatedResponse } from './types';

export function paginatedItems<T>(response: PaginatedResponse<T>) {
  return response.items;
}
