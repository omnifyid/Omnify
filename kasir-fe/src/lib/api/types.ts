export type Role = 'OWNER' | 'MANAGER' | 'OPERATOR';
export type PaymentMethod = 'CASH' | 'CARD' | 'QRIS' | 'TRANSFER' | 'PLATFORM';
export type OrderChannel = 'GOFOOD' | 'GRABFOOD' | 'SHOPEEFOOD';
export type KitchenStatus = 'NEW' | 'COOKING' | 'READY' | 'SERVED';
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
  is_open?: boolean;
  show_logo?: boolean;
  receipt_header?: string | null;
  receipt_footer?: string | null;
  address?: string | null;
  phone?: string | null;
  receipt_options?: Partial<import('$lib/utils/receipt').ReceiptOptions> | null;
  expense_categories?: string[];
  payment_options?: Partial<import('$lib/utils/payment').PaymentOptions> | null;
  pos_dine_in_enabled?: boolean;
  pos_table_enabled?: boolean;
  pos_table_count?: number;
  pos_customer_name_enabled?: boolean;
  kitchen_enabled?: boolean;
  inventory_enabled?: boolean;
  finance_enabled?: boolean;
  tax_bp?: number;
  service_bp?: number;
  pb1_bp?: number;
  shift_variance_threshold?: number;
  default_float?: number;
  /** catalog owner: the parent store edits products, branches follow it */
  is_parent?: boolean;
  has_branches?: boolean;
  parent_store_name?: string | null;
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
  // product summary from the list endpoint
  item_count?: number;
};

export type OptionGroup = {
  id: string;
  name?: string;
  label?: string;
  required?: boolean;
  is_required?: boolean;
  choices?: OptionChoice[];
  option_choices?: OptionChoice[];
};

export type OptionChoice = {
  id: string;
  name?: string;
  label?: string;
  is_default?: boolean;
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

export type BranchSetting = { store_id: string; store_name: string; is_sold: boolean; is_parent?: boolean; price: number | null };

export type Item = {
  id: string;
  category_id?: string | null;
  name: string;
  description?: string | null;
  price?: number;
  base_price?: number;
  /** HPP (cost of goods), Rupiah. */
  cost_price?: number | null;
  /** manual platform prices (staff only), e.g. { GOFOOD: 25000 } */
  channel_prices?: Partial<Record<OrderChannel, number>>;
  is_available?: boolean;
  /** false when this branch does not sell the item */
  is_sold?: boolean;
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
  operator_id?: string | null;
  status: OrderStatus;
  payment_method: PaymentMethod;
  payment_provider?: string | null;
  subtotal?: number;
  discount_amount?: number;
  total_amount: number;
  discount_code_snapshot?: string | null;
  notes?: string | null;
  order_type?: 'DINE_IN' | 'TAKE_AWAY' | null;
  table_number?: string | null;
  customer_name?: string | null;
  kitchen_status?: KitchenStatus | null;
  channel?: OrderChannel | null;
  channel_order_id?: string | null;
  app_total?: number | null;
  commission_amount?: number | null;
  expected_payout?: number | null;
  tax_amount?: number | null;
  expected_payout_date?: string | null;
  settlement_id?: string | null;
  driver_name?: string | null;
  service_amount?: number;
  pb1_amount?: number;
  refunded_amount?: number;
  refunds?: OrderRefund[];
  created_at?: string;
  operator_name?: string | null;
  /** cash handed over by the customer (cash orders), for the change line */
  cash_received?: number | null;
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
    is_done?: boolean;
    void_qty?: number;
  }>;
};

export type OrderRefund = {
  id: string;
  type: 'VOID' | 'REFUND';
  method: 'CASH' | 'TRANSFER';
  amount: number;
  reason: string;
  quantity: number | null;
  order_item_id: string | null;
  refunded_at: string;
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
  target_item_name?: string | null;
  target_category_name?: string | null;
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

export type Ingredient = {
  id: string;
  name: string;
  unit: string;
  category: string | null;
  stock: number;
  min_stock: number;
  cost_price: number;
};

export type MovementType = 'INITIAL' | 'RESTOCK' | 'SALE' | 'RETURN' | 'OPNAME';

export type StockMovement = {
  id: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  type: MovementType;
  quantity: number;
  balance_after: number;
  note: string | null;
  order_id: string | null;
  created_at: string;
};

export type RecipeLine = {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity: number;
  cost_price: number;
};

export type ChannelSetting = {
  channel: OrderChannel;
  enabled: boolean;
  commission_bp: number;
  markup_bp: number;
  payout_lag_days: number;
};

export type ExpenseSource = 'BANK' | 'EWALLET' | 'PETTY' | 'DRAWER';

export type Expense = {
  id: string;
  date: string;
  category: string;
  description: string;
  amount: number;
  source: ExpenseSource;
  recurring: boolean;
  status: 'DRAFT' | 'POSTED';
};

export type ExpenseSummary = {
  total: number;
  posted_count: number;
  draft_count: number;
  by_category: { category: string; total: number }[];
};

export type ChannelOverview = {
  channel: OrderChannel;
  outstanding: number;
  outstanding_count: number;
  overdue: number;
  received_month: number;
  commission_month: number;
};

export type Receivable = {
  id: string;
  order_number: string;
  channel_order_id: string | null;
  created_at: string;
  total_amount: number;
  expected_payout: number;
  expected_payout_date: string;
};

export type PlatformSettlement = {
  id: string;
  channel: OrderChannel;
  received_date: string;
  amount: number;
  expected: number;
  diff: number;
  order_count: number;
  reason: string | null;
};

export type ShiftStatus = 'OPEN' | 'CLOSED' | 'REVIEWED';

export type Shift = {
  id: string;
  status: ShiftStatus;
  opened_by_name: string | null;
  opened_at: string;
  opening_cash: number;
  carry_expected: number | null;
  closed_by_name: string | null;
  closed_at: string | null;
  counted_cash: number | null;
  expected_cash: number | null;
  variance: number | null;
  note: string | null;
  review_note: string | null;
};

export type CashMovement = {
  id: string;
  type: 'IN' | 'OUT';
  amount: number;
  category: string;
  reason: string;
  created_at: string;
  user_name: string | null;
};

export type ShiftDetail = Shift & {
  cash_sales: number;
  cash_refunds: number;
  cash_in: number;
  cash_out: number;
  non_cash: { method: string; total: number; count: number }[];
  movements: CashMovement[];
};

export type ShiftCurrent = {
  shift: Shift | null;
  cash_sales: number;
  cash_refunds: number;
  cash_in: number;
  cash_out: number;
  last_counted_cash: number | null;
  last_closed_at: string | null;
  cash_on_hand: number | null;
  default_float: number;
  variance_threshold: number;
};

export type ShiftSummary = {
  count: number;
  open_count: number;
  review_count: number;
  big_count: number;
  total_variance: number;
};

export type IngredientSummary = {
  count: number;
  low_count: number;
  stock_value: number;
  categories: string[];
};

export type SettlementBatch = {
  date: string;
  order_count: number;
  gross: number;
  expected: number;
};

export type ReceivableSelection = {
  ids: string[];
  count: number;
  expected: number;
};
