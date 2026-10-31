import { auth } from '$lib/stores/auth.svelte';
import { session } from '$lib/stores/session.svelte';
import { adminGroup, navGroups, type NavGroup } from './nav';

/** Nav groups visible to the current user/store. */
export function visibleGroups(): NavGroup[] {
  if (auth.user?.is_superadmin) return [adminGroup];
  const role = session.selectedStore?.role ?? null;
  const selfOrderEnabled = session.selectedStore?.self_order_enabled ?? false;
  const kitchenEnabled = session.selectedStore?.kitchen_enabled ?? false;
  const inventoryEnabled = session.selectedStore?.inventory_enabled !== false;
  const financeEnabled = session.selectedStore?.finance_enabled !== false;
  if (!role) return [];
  return navGroups
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => i.roles.includes(role) && (i.href !== '/selforder' || selfOrderEnabled) &&
          (i.href !== '/kitchen' || kitchenEnabled) &&
          (i.href !== '/inventory' || inventoryEnabled) && (i.href !== '/finance' || financeEnabled))
    }))
    .filter((g) => g.items.length > 0);
}
