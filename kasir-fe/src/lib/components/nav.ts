import type { Role } from '$lib/api/types';
import type { MessageKey } from '$lib/i18n/messages';

export type NavItem = { href: string; labelKey: MessageKey; subtitleKey?: MessageKey; icon: string; roles: Role[] };
export type NavGroup = { labelKey: MessageKey; items: NavItem[] };

const ALL: Role[] = ['OWNER', 'MANAGER', 'OPERATOR'];
const MGMT: Role[] = ['OWNER', 'MANAGER'];

export const navGroups: NavGroup[] = [
  {
    labelKey: 'navOperations',
    items: [
      { href: '/dashboard', labelKey: 'dashboard', icon: 'space_dashboard', roles: ALL },
      { href: '/pos', labelKey: 'pos', icon: 'point_of_sale', roles: ALL },
      { href: '/transactions', labelKey: 'transactions', icon: 'receipt_long', roles: ALL },
      { href: '/selforder', labelKey: 'selfOrder', icon: 'qr_code_2', roles: MGMT }
    ]
  },
  {
    labelKey: 'navMenu',
    items: [
      { href: '/products', labelKey: 'products', subtitleKey: 'productsHeaderSubtitle', icon: 'local_cafe', roles: MGMT },
      { href: '/discounts', labelKey: 'discounts', icon: 'sell', roles: MGMT }
    ]
  },
  {
    labelKey: 'navTeam',
    items: [
      { href: '/users', labelKey: 'users', icon: 'badge', roles: MGMT },
      { href: '/settings', labelKey: 'settings', icon: 'settings', roles: MGMT },
      { href: '/account', labelKey: 'account', icon: 'manage_accounts', roles: ALL }
    ]
  }
];

export const adminGroup: NavGroup = {
  labelKey: 'admin',
  items: [{ href: '/admin', labelKey: 'superAdmin', icon: 'admin_panel_settings', roles: ALL }]
};
