export type Role = 'OWNER' | 'MANAGER' | 'OPERATOR';
export type PaymentMethod = 'CASH' | 'CARD' | 'QRIS' | 'TRANSFER';
export type OrderStatus = 'PENDING' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED';
export type DiscountType = 'PERCENTAGE' | 'FIXED';
export type DiscountScope = 'ORDER' | 'ITEM';
export type DiscountTargetType = 'ALL' | 'CATEGORY' | 'ITEM';

export type User = {
  id: string;
  email: string;
  full_name?: string | null;
  phone?: string | null;
  is_active?: boolean;
  is_superadmin?: boolean;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export type Store = {
  id: string;
  name: string;
  slug?: string;
  description?: string | null;
  role?: Role;
  logo_url?: string | null;
  self_order_enabled?: boolean;
  selforder_is_open?: boolean;
  show_logo?: boolean;
  receipt_header?: string | null;
  receipt_footer?: string | null;
  pos_dine_in_enabled?: boolean;
  pos_table_enabled?: boolean;
  pos_table_count?: number;
  pos_customer_name_enabled?: boolean;
};

export type AdminStore = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
  self_order_enabled: boolean;
  owner_email?: string | null;
  owner_id?: string | null;
};

export type StoreMember = {
  user_id?: string;
  id?: string;
  uid?: string;
  email: string;
  full_name?: string | null;
  phone?: string | null;
  role: Role;
};

export type Category = {
  id: string;
  name: string;
  icon?: string | null;
  sort_order?: number;
};

export type OptionGroup = {
  id: string;
  name?: string;
  label?: string;
  required?: boolean;
  choices?: OptionChoice[];
  option_choices?: OptionChoice[];
};

export type OptionChoice = {
  id: string;
  name?: string;
  label?: string;
};

export type AddonGroup = {
  id: string;
  name?: string;
  label?: string;
  min_select?: number;
  max_select?: number | null;
  choices?: AddonChoice[];
  addon_choices?: AddonChoice[];
};

export type AddonChoice = {
  id: string;
  name?: string;
  label?: string;
  extra_price?: number;
  price?: number;
};

export type Item = {
  id: string;
  category_id?: string | null;
  name: string;
  description?: string | null;
  price?: number;
  base_price?: number;
  /** HPP (cost of goods), Rupiah. */
  cost_price?: number | null;
  is_available?: boolean;
  image_url?: string | null;
  icon?: string | null;
  /** null = always available (no tracking). 0 = out of stock. >0 = tracked stock remaining. */
  stock?: number | null;
  option_groups?: OptionGroup[];
  addon_groups?: AddonGroup[];
};

export type Order = {
  id: string;
  order_number?: string;
  status: OrderStatus;
  payment_method: PaymentMethod;
  subtotal?: number;
  discount_amount?: number;
  total_amount: number;
  discount_code_snapshot?: string | null;
  notes?: string | null;
  order_type?: 'DINE_IN' | 'TAKE_AWAY' | null;
  table_number?: string | null;
  customer_name?: string | null;
  created_at?: string;
  staff_name?: string | null;
  items?: Array<{
    id: string;
    item_id?: string | null;
    package_id?: string | null;
    item_name_snapshot: string;
    quantity: number;
    unit_price_snapshot: number;
    addon_total_snapshot?: number;
    line_total?: number;
    item_discount_amount?: number | null;
    options_snapshot?: unknown[] | null;
    addons_snapshot?: unknown[] | null;
  }>;
};

export type Discount = {
  id: string;
  name: string;
  code?: string | null;
  discount_type: DiscountType;
  value: number;
  max_discount_amount?: number | null;
  scope: DiscountScope;
  target_type?: DiscountTargetType | null;
  target_item_id?: string | null;
  target_category_id?: string | null;
  is_automatic: boolean;
  min_order_amount?: number | null;
  max_uses?: number | null;
  used_count?: number;
  expires_at?: string | null;
  is_active: boolean;
  created_at?: string;
};

export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type SalesReport = {
  order_count?: number;
  total_orders?: number;
  total_revenue: number;
  avg_order_value?: number;
};

export type TopItemReport = {
  item_name?: string;
  name?: string;
  quantity_sold?: number;
  quantity?: number;
  total_revenue?: number;
  revenue?: number;
};

export type PaymentReport = {
  payment_method: PaymentMethod;
  total_revenue?: number;
  revenue?: number;
  order_count?: number;
};

export type DashboardReport = {
  sales: SalesReport;
  top_items: TopItemReport[];
  payments: PaymentReport[];
};
