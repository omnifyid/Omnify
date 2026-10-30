import { api } from '$lib/api/client';
import type { ShiftCurrent } from '$lib/api/types';
import { session } from './session.svelte';

class ShiftState {
  current = $state<ShiftCurrent | null>(null);
  error = $state('');

  async load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) {
      this.current = null;
      return;
    }
    try {
      this.current = await api.get<ShiftCurrent>(`/stores/${storeId}/shifts/current`);
      this.error = '';
    } catch (err) {
      this.error = err instanceof Error ? err.message : '';
    }
  }
}

export const shiftState = new ShiftState();
