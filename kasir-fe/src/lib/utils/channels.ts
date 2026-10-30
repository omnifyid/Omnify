import type { OrderChannel } from '$lib/api/types';

export const CHANNEL_META: Record<OrderChannel, { label: string; logo: string }> = {
  GOFOOD: { label: 'GoFood', logo: '/images/channels/gofood.svg' },
  GRABFOOD: { label: 'GrabFood', logo: '/images/channels/grabfood.svg' },
  SHOPEEFOOD: { label: 'ShopeeFood', logo: '/images/channels/shopeefood.svg' }
};
