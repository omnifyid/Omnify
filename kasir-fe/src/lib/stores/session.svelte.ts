import { api } from '$lib/api/client';
import type { Store } from '$lib/api/types';

class SessionState {
  stores = $state<Store[]>([]);
  selectedStoreId = $state<string | null>(null);
  loadingStores = $state(false);

  get selectedStore() {
    return this.stores.find((store) => store.id === this.selectedStoreId) ?? this.stores[0] ?? null;
  }

  async loadStores() {
    this.loadingStores = true;
    try {
      this.stores = await api.get<Store[]>('/stores');
      if (!this.selectedStoreId || !this.stores.some((store) => store.id === this.selectedStoreId)) {
        this.selectedStoreId = this.stores[0]?.id ?? null;
      }
    } finally {
      this.loadingStores = false;
    }
  }
}

export const session = new SessionState();
