<script lang="ts">
  import { page } from '$app/stores';
  import { api, mediaUrl } from '$lib/api/client';
  import { toOrderPayload } from '$lib/api/orders';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Category, ChannelSetting, Discount, Item, Order, OrderChannel, PaymentMethod, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { getItemPrice } from '$lib/utils/catalog';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { getChoiceLabel, getChoicePrice, getGroupChoices, getGroupLabel, hasItemModifiers } from '$lib/utils/modifiers';
  import { printEscPos, canPrint } from '$lib/utils/bluetooth-printer';
  import { buildReceiptBytes } from '$lib/utils/escpos';
  import CupcakeIcon from '$lib/components/CupcakeIcon.svelte';
  import ReceiptView from '$lib/components/ReceiptView.svelte';
  import { customerReceipt, receiptOptions } from '$lib/utils/receipt';
  import { chip, CHIP_ROW } from '$lib/utils/ui';
  import { enabledMethods, paymentOptions, providersFor } from '$lib/utils/payment';

  type CartLine = {
    lineId: string;
    item: Item;
    quantity: number;
    optionChoiceIds: string[];
    addonChoiceIds: string[];
    note: string;
  };

  const PAYMENT_ICONS: Record<string, string> = { CASH: '💵', CARD: '💳', QRIS: '▦', TRANSFER: '↗' };

  function paymentLabel(method: PaymentMethod): string {
    if (method === 'CASH') return language.t('cash');
    if (method === 'CARD') return language.t('card');
    if (method === 'TRANSFER') return language.t('transfer');
    if (method === 'PLATFORM') return language.t('online');
    return 'QRIS';
  }

  let categories = $state<Category[]>([]);
  let items = $state<Item[]>([]);
  let activeCategoryId = $state('all');
  let search = $state('');
  let cart = $state<CartLine[]>([]);
  let paymentMethod = $state<PaymentMethod>('CASH');
  let paymentProvider = $state('');
  let payOpts = $derived(paymentOptions(session.selectedStore));
  let payments = $derived(enabledMethods(payOpts).map((value) => ({ value, icon: PAYMENT_ICONS[value] })));
  let providers = $derived(providersFor(payOpts, paymentMethod));
  // keep the picked method / bank valid when store settings or the method change
  $effect(() => {
    if (payments.length && !payments.some((p) => p.value === paymentMethod)) paymentMethod = payments[0].value;
  });
  $effect(() => {
    if (!providers.includes(paymentProvider)) paymentProvider = providers[0] ?? '';
  });
  let discountCode = $state('');
  let loading = $state(false);
  let checkingOut = $state(false);
  let error = $state('');
  let receiptOrder = $state<Order | null>(null);
  let modifierItem = $state<Item | null>(null);
  let modifierQty = $state(1);
  let modifierNote = $state('');
  let modifierNoteOn = $state(false);
  let payModalOpen = $state(false);
  // open bill being paid; null = paying the cart
  let payTarget = $state<Order | null>(null);
  let toast = $state('');
  let toastTimer: ReturnType<typeof setTimeout> | undefined;
  function showToast(message: string) {
    toast = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast = ''), 3200);
  }
  let selectedOptionChoiceIds = $state<Record<string, string>>({});
  let selectedAddonChoiceIds = $state<string[]>([]);

  // ── Online food platforms ─────────────────────────────────
  const CHANNEL_META: Record<OrderChannel, { label: string; logo: string }> = {
    GOFOOD: { label: 'GoFood', logo: '/images/channels/gofood.svg' },
    GRABFOOD: { label: 'GrabFood', logo: '/images/channels/grabfood.svg' },
    SHOPEEFOOD: { label: 'ShopeeFood', logo: '/images/channels/shopeefood.svg' }
  };
  let channelSettings = $state<ChannelSetting[]>([]);
  let enabledChannels = $derived(channelSettings.filter((c) => c.enabled));
  let hasOnline = $derived(enabledChannels.length > 0);
  let onlineMode = $state(false);
  let channel = $state<OrderChannel | null>(null);
  let markupBp = $derived(onlineMode ? (channelSettings.find((c) => c.channel === channel)?.markup_bp ?? 0) : 0);
  let taxBp = $derived(session.selectedStore?.tax_bp ?? 0);
  let onlineOrderId = $state('');
  let onlineCustomer = $state('');
  let onlineDriver = $state('');
  let onlineNote = $state('');
  let onlineAppTotal = $state('');
  let appTotalNum = $derived(parseInt(onlineAppTotal.replace(/\D/g, '') || '0', 10));
  let onlineValid = $derived(!!channel && !!onlineOrderId.trim() && !!onlineCustomer.trim() && appTotalNum > 0);

  /** Online price: amount × (1 + markup), rounded up to the next Rp500 (mirrors the backend). */
  function mk(amount: number) {
    if (!markupBp || amount <= 0) return amount;
    return Math.ceil((amount * (10000 + markupBp)) / (10000 * 500)) * 500;
  }

  /** Price of one unit of the item (before add-ons) in the current mode. */
  function itemPrice(item: Item) {
    const manual = onlineMode && channel ? item.channel_prices?.[channel] : undefined;
    return manual || mk(getItemPrice(item));
  }

  /** Extra price of the picked option and add-on choices. */
  function addonTotal(item: Item, ids: string[], optionIds: string[] = []) {
    const sum = (groups: Array<NonNullable<Item['option_groups']>[number] | NonNullable<Item['addon_groups']>[number]>, picked: string[]) =>
      groups.reduce((s, group) => s + getGroupChoices(group).reduce((gs, c) => gs + (picked.includes(c.id) ? mk(getChoicePrice(c)) : 0), 0), 0);
    return sum(item.addon_groups ?? [], ids) + sum(item.option_groups ?? [], optionIds);
  }

  function pickType(type: 'DINE_IN' | 'TAKE_AWAY') {
    if (onlineMode) setOnline(false);
    orderType = orderType === type ? null : type;
  }

  function setOnline(on: boolean) {
    onlineMode = on;
    promoResult = null;
    if (on) {
      orderType = null;
      posTableNumber = null;
      discountCode = '';
      appliedDiscountLabel = '';
      if (!channel || !enabledChannels.some((c) => c.channel === channel)) channel = enabledChannels[0]?.channel ?? null;
    } else {
      resetOnlineForm();
      schedulePromoCheck();
    }
  }

  function resetOnlineForm() {
    onlineOrderId = '';
    onlineCustomer = '';
    onlineDriver = '';
    onlineNote = '';
    onlineAppTotal = '';
  }

  let filteredItems = $derived(
    items.filter((item) => {
      const matchesCategory = activeCategoryId === 'all' || item.category_id === activeCategoryId;
      const matchesSearch = item.name.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesSearch && item.is_available !== false;
    })
  );
  let subtotal = $derived(cart.reduce((sum, line) => sum + getLineUnitPrice(line) * line.quantity, 0));
  let onlineTax = $derived(taxBp > 0 ? subtotal - Math.round((subtotal * 10000) / (10000 + taxBp)) : 0);

  let posDineInEnabled = $derived(session.selectedStore?.pos_dine_in_enabled ?? false);
  let orderType = $state<'DINE_IN' | 'TAKE_AWAY' | null>(null);
  let dineInActive = $derived(posDineInEnabled && !onlineMode && orderType === 'DINE_IN');

  type PromoResult = { valid: boolean; subtotal: number; discount_amount: number; total_amount: number; message: string };
  const feeRound = (amount: number, bp: number) => Math.floor((amount * bp + 5000) / 10000);
  let promoResult = $state<PromoResult | null>(null);
  let promoLoading = $state(false);
  let netDue = $derived(promoResult?.valid ? promoResult.total_amount : subtotal);
  // Service (dine-in only) and PB1 mirror order_service.direct_order_fees; the server is authoritative.
  let serviceFee = $derived(dineInActive ? feeRound(netDue, session.selectedStore?.service_bp ?? 0) : 0);
  let pb1Fee = $derived(onlineMode ? 0 : feeRound(netDue + serviceFee, session.selectedStore?.pb1_bp ?? 0));
  let totalDue = $derived(netDue + serviceFee + pb1Fee);
  let payTotal = $derived(payTarget ? payTarget.total_amount : totalDue);

  let cashAmount = $state('0');
  let receiptCashPaid = $state(0);
  let receiptOpts = $derived(receiptOptions(session.selectedStore));
  let receiptLines = $derived(receiptOrder && session.selectedStore ? customerReceipt(receiptOrder, session.selectedStore, receiptOpts, receiptCashPaid) : []);
  let cashPaid = $derived(parseInt(cashAmount) || 0);
  let change = $derived(cashPaid - payTotal);

  let discounts = $state<Discount[]>([]);
  let discountModalOpen = $state(false);
  let appliedDiscountLabel = $state('');
  let autoPromoTimer: ReturnType<typeof setTimeout> | null = null;

  const usable = (d: Discount) =>
    d.is_active &&
    !(d.expires_at && new Date(d.expires_at.endsWith('Z') || /[+-]\d\d:\d\d$/.test(d.expires_at) ? d.expires_at : d.expires_at + 'Z') < new Date()) &&
    !(d.max_uses != null && d.used_count != null && d.used_count >= d.max_uses);
  let autoDiscounts = $derived(discounts.filter((d) => d.is_automatic && usable(d)));
  let codeDiscounts = $derived(discounts.filter((d) => !d.is_automatic && !!d.code && usable(d)));

  // payment tiles follow the store's payment settings: one per method, or per EDC bank / QRIS provider
  const WALLET_LOGOS: Record<string, string> = { gopay: 'gopay.svg', ovo: 'Logo_ovo_purple.svg', dana: 'Logo_dana_blue.svg', shopeepay: 'Shopee.svg' };
  type PayTile = { key: string; method: PaymentMethod; provider: string; label: string; icon: string; logo: string | null };
  let payTiles = $derived.by(() => {
    const out: PayTile[] = [];
    for (const method of payments.map((p) => p.value)) {
      const names = providersFor(payOpts, method);
      const icon = method === 'CASH' ? 'payments' : method === 'CARD' ? 'contactless' : method === 'QRIS' ? 'qr_code_2' : 'account_balance';
      if (!names.length) out.push({ key: method, method, provider: '', label: paymentLabel(method), icon, logo: method === 'QRIS' ? 'Logo_QRIS.svg' : null });
      else for (const name of names) out.push({ key: `${method}:${name}`, method, provider: name, label: method === 'CARD' ? `EDC ${name}` : name, icon, logo: method === 'QRIS' ? (WALLET_LOGOS[name.toLowerCase().replace(/\s/g, '')] ?? 'Logo_QRIS.svg') : null });
    }
    return out;
  });
  function pickPayTile(t: PayTile) {
    paymentMethod = t.method;
    paymentProvider = t.provider;
  }
  function onCashInput(e: Event & { currentTarget: HTMLInputElement }) {
    const digits = e.currentTarget.value.replace(/\D/g, '');
    cashAmount = digits ? String(parseInt(digits, 10)) : '0';
    e.currentTarget.value = cashPaid > 0 ? cashPaid.toLocaleString('id-ID') : '';
  }
  let quickCash = $derived.by(() => {
    const ups = [payTotal, ...[10000, 50000, 100000].map((u) => Math.ceil(payTotal / u) * u)];
    return [...new Set(ups)].filter((v) => v >= payTotal).slice(0, 4);
  });


  function discountSummary(d: Discount): string {
    if (d.discount_type === 'PERCENTAGE') {
      const pct = (d.value / 100).toFixed(0);
      return d.max_discount_amount
        ? `${pct}% (${language.t('max')} ${formatRupiah(d.max_discount_amount)})`
        : `${pct}%`;
    }
    return formatRupiah(d.value);
  }

  function handleCharge() {
    if (onlineMode) {
      void checkout();
    } else {
      payTarget = null;
      cashAmount = String(totalDue);
      mobileCartOpen = false;
      payModalOpen = true;
    }
  }
  let totalItems = $derived(cart.reduce((sum, line) => sum + line.quantity, 0));
  let activeCategoryName = $derived(activeCategoryId === 'all' ? language.t('allMenu') : categories.find((category) => category.id === activeCategoryId)?.name ?? language.t('menu'));
  let modifierUnitPrice = $derived(modifierItem ? itemPrice(modifierItem) + addonTotal(modifierItem, selectedAddonChoiceIds, Object.values(selectedOptionChoiceIds)) : 0);
  let canAddModifierItem = $derived(
    modifierItem
      ? (modifierItem.option_groups ?? []).every((group) => !(group.is_required ?? group.required) || Boolean(selectedOptionChoiceIds[group.id])) &&
        (modifierItem.addon_groups ?? []).every(
          (group) => !(group.is_required || (group.min_select ?? 0) > 0) || getGroupChoices(group).some((c) => selectedAddonChoiceIds.includes(c.id))
        )
      : false
  );

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    error = '';
    try {
      const [catsRes, itemsRes, discountsRes] = await Promise.all([
        api.get<PaginatedResponse<Category>>(`/stores/${storeId}/categories?limit=100`),
        api.get<PaginatedResponse<Item>>(`/stores/${storeId}/items?limit=1000&is_sold=true`),
        api.get<PaginatedResponse<Discount>>(`/stores/${storeId}/discounts?limit=100`)
      ]);
      categories = paginatedItems(catsRes);
      items = paginatedItems(itemsRes);
      discounts = paginatedItems(discountsRes);
      channelSettings = await api.get<ChannelSetting[]>(`/stores/${storeId}/channels`).catch(() => []);
      if (onlineMode && !enabledChannels.length) setOnline(false);
      void loadOpenBills();
    } catch (err) { error = err instanceof Error ? err.message : language.t('error'); }
    finally { loading = false; }
  }

  /** After a sale only the catalog (stock) changes; categories, discounts and platforms stay as loaded. */
  async function refreshItems() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      items = paginatedItems(await api.get<PaginatedResponse<Item>>(`/stores/${storeId}/items?limit=1000&is_sold=true`));
    } catch { /* the next full load will retry */ }
  }

  const snapNames = (l: NonNullable<Order['items']>[number]) =>
    [...(l.options_snapshot ?? []), ...(l.addons_snapshot ?? [])].map((m) => (m as { label?: string }).label).filter(Boolean).join(', ');

  function sameChoices(left: string[], right: string[]) {
    return left.length === right.length && [...left].sort().every((value, index) => value === [...right].sort()[index]);
  }

  function lineFor(item: Item, optionChoiceIds: string[] = [], addonChoiceIds: string[] = [], note = '') {
    return cart.find(
      (line) =>
        line.item.id === item.id &&
        line.note.trim() === note.trim() &&
        sameChoices(line.optionChoiceIds, optionChoiceIds) &&
        sameChoices(line.addonChoiceIds, addonChoiceIds)
    );
  }

  function itemQuantity(item: Item) {
    return cart.reduce((sum, line) => sum + (line.item.id === item.id ? line.quantity : 0), 0);
  }

  function getLineUnitPrice(line: CartLine) {
    return itemPrice(line.item) + addonTotal(line.item, line.addonChoiceIds, line.optionChoiceIds);
  }

  function addItem(item: Item) {
    if (hasItemModifiers(item)) {
      openModifierModal(item);
      return;
    }
    addConfiguredItem(item, 1, [], []);
  }

  function addConfiguredItem(item: Item, quantity: number, optionChoiceIds: string[], addonChoiceIds: string[], note = '') {
    if (item.stock !== null && item.stock !== undefined) {
      const remaining = item.stock - itemQuantity(item);
      if (remaining <= 0) return;
      quantity = Math.min(quantity, remaining);
    }
    const existing = lineFor(item, optionChoiceIds, addonChoiceIds, note);
    if (existing) existing.quantity += quantity;
    else cart.push({ lineId: Math.random().toString(36).slice(2), item, quantity, optionChoiceIds, addonChoiceIds, note: note.trim() });
    schedulePromoCheck();
  }

  function openModifierModal(item: Item) {
    modifierItem = item;
    modifierQty = 1;
    modifierNote = '';
    modifierNoteOn = false;
    // preselect the choices flagged as default
    selectedOptionChoiceIds = Object.fromEntries(
      (item.option_groups ?? []).flatMap((g) => {
        const choices = getGroupChoices(g);
        // a required group starts with its default, or its first choice
        const d = choices.find((c) => c.is_default) ?? ((g.is_required ?? g.required) ? choices[0] : undefined);
        return d ? [[g.id, d.id]] : [];
      })
    );
    selectedAddonChoiceIds = (item.addon_groups ?? []).flatMap((g) => getGroupChoices(g).filter((c) => c.is_default).map((c) => c.id));
  }

  function closeModifierModal() {
    modifierItem = null;
  }

  function toggleAddon(choiceId: string) {
    if (selectedAddonChoiceIds.includes(choiceId)) {
      selectedAddonChoiceIds = selectedAddonChoiceIds.filter((id) => id !== choiceId);
      return;
    }
    const group = modifierItem?.addon_groups?.find((g) => getGroupChoices(g).some((c) => c.id === choiceId));
    const max = group?.max_select;
    if (group && max) {
      const picked = getGroupChoices(group).filter((c) => selectedAddonChoiceIds.includes(c.id));
      // at the limit: swap out the oldest pick of the group
      if (picked.length >= max) selectedAddonChoiceIds = selectedAddonChoiceIds.filter((id) => id !== picked[0].id);
    }
    selectedAddonChoiceIds = [...selectedAddonChoiceIds, choiceId];
  }

  function addModifierItemToCart() {
    if (!modifierItem || !canAddModifierItem) return;
    addConfiguredItem(modifierItem, modifierQty, Object.values(selectedOptionChoiceIds), selectedAddonChoiceIds, modifierNoteOn ? modifierNote : '');
    closeModifierModal();
  }

  function choiceNames(line: CartLine) {
    const optionNames = (line.item.option_groups ?? []).flatMap((group) =>
      getGroupChoices(group).filter((choice) => line.optionChoiceIds.includes(choice.id)).map((choice) => getChoiceLabel(choice))
    );
    const addonNames = (line.item.addon_groups ?? []).flatMap((group) =>
      getGroupChoices(group).filter((choice) => line.addonChoiceIds.includes(choice.id)).map((choice) => getChoiceLabel(choice))
    );
    return [...optionNames, ...addonNames].join(', ');
  }

  function changeQty(line: CartLine, delta: number) {
    line.quantity += delta;
    if (line.quantity <= 0) cart = cart.filter((item) => item.lineId !== line.lineId);
    schedulePromoCheck();
  }



  // ── Open bills (saved unpaid, paid later) ─────────────────
  let openBills = $state<Order[]>([]);
  let openBillTotal = $state(0);
  let openBillModal = $state(false);
  let openBillQuery = $state('');
  let openBillTimer: ReturnType<typeof setTimeout> | undefined;

  async function loadOpenBills() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      const q = new URLSearchParams({ status: 'OPEN', limit: '50' });
      if (openBillQuery.trim()) q.set('search', openBillQuery.trim());
      const res = await api.get<PaginatedResponse<Order>>(`/stores/${storeId}/orders?${q}`);
      openBills = paginatedItems(res);
      openBillTotal = res.total;
    } catch { /* the badge is informational */ }
  }

  function searchOpenBills() {
    clearTimeout(openBillTimer);
    openBillTimer = setTimeout(() => void loadOpenBills(), 350);
  }

  function openBillList() {
    openBillQuery = '';
    openBillModal = true;
    void loadOpenBills();
  }

  function payOpenBill(order: Order) {
    payTarget = order;
    cashAmount = String(order.total_amount);
    paymentMethod = payments[0]?.value ?? 'CASH';
    openBillModal = false;
    mobileCartOpen = false;
    error = '';
    payModalOpen = true;
  }

  function closePay() {
    payModalOpen = false;
    payTarget = null;
    error = '';
  }

  // open bill being extended with more items (earlier lines stay as sent to the kitchen)
  let addTo = $state<Order | null>(null);
  let addNet = $derived(addTo ? addTo.total_amount - (addTo.service_amount ?? 0) - (addTo.pb1_amount ?? 0) + subtotal : 0);
  let addService = $derived(addTo?.order_type === 'DINE_IN' ? feeRound(addNet, session.selectedStore?.service_bp ?? 0) : 0);
  let addPb1 = $derived(addTo ? feeRound(addNet + addService, session.selectedStore?.pb1_bp ?? 0) : 0);
  let addTotal = $derived(addNet + addService + addPb1);

  // void a line of the open bill being extended (Owner / Manager)
  const VOID_REASONS = ['Salah input', 'Pelanggan komplain', 'Item habis', 'Lain-lain'];
  let canVoid = $derived(['OWNER', 'MANAGER'].includes(session.selectedStore?.role ?? ''));
  let voidLine = $state<NonNullable<Order['items']>[number] | null>(null);
  let voidQty = $state(1);
  let voidReason = $state('');
  let voidSaving = $state(false);
  let voidError = $state('');
  const unitsLeft = (l: NonNullable<Order['items']>[number]) => l.quantity - (l.void_qty ?? 0);
  let billUnits = $derived((addTo?.items ?? []).reduce((n, l) => n + unitsLeft(l), 0));

  function openVoid(line: NonNullable<Order['items']>[number]) {
    voidLine = line;
    voidQty = 1;
    voidReason = '';
    voidError = '';
  }

  async function submitVoid() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !addTo || !voidLine || !voidReason) return;
    voidSaving = true;
    voidError = '';
    try {
      const order = await api.post<Order>(`/stores/${storeId}/orders/${addTo.id}/items/${voidLine.id}/void`, { quantity: voidQty, reason: voidReason });
      addTo = order;
      voidLine = null;
      showToast(language.t('obVoided'));
      await Promise.all([refreshItems(), loadOpenBills()]);
    } catch (err) {
      voidError = err instanceof Error ? err.message : language.t('error');
    } finally {
      voidSaving = false;
    }
  }

  function startAddTo(order: Order) {
    addTo = order;
    orderType = (order.order_type as typeof orderType) ?? null;
    posTableNumber = order.table_number ?? null;
    customerName = order.customer_name ?? '';
    guestCount = order.guest_count ?? 1;
    segment = order.segment ?? '';
    discountCode = '';
    appliedDiscountLabel = '';
    promoResult = null;
    openBillModal = false;
    error = '';
  }

  function cancelAdd() {
    addTo = null;
    resetOrderMeta();
  }

  async function saveAdd() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !addTo || cart.length === 0) return;
    checkingOut = true;
    error = '';
    try {
      const order = await api.post<Order>(`/stores/${storeId}/orders/${addTo.id}/items`, {
        items: cart.map((line) => ({
          item_id: line.item.id,
          quantity: line.quantity,
          selected_option_choice_ids: line.optionChoiceIds,
          selected_addon_choice_ids: line.addonChoiceIds,
          note: line.note.trim() || null
        })),
        table_number: posTableEnabled ? posTableNumber : null,
        customer_name: posCustomerNameEnabled && customerName ? customerName : null,
        guest_count: guestCount,
        segment: segment || null
      });
      cart = [];
      addTo = null;
      resetOrderMeta();
      mobileCartOpen = false;
      showToast(`${language.t('obAdded')} · ${order.order_number}`);
      await Promise.all([refreshItems(), loadOpenBills()]);
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      checkingOut = false;
    }
  }

  async function saveOpenBill() {
    const storeId = session.selectedStore?.id;
    if (!storeId || cart.length === 0 || onlineMode) return;
    checkingOut = true;
    error = '';
    try {
      const order = await api.post<Order>(`/stores/${storeId}/orders`, toOrderPayload({
        openBill: true,
        discountCode,
        items: cart.map((line) => ({
          itemId: line.item.id,
          quantity: line.quantity,
          optionChoiceIds: line.optionChoiceIds,
          addonChoiceIds: line.addonChoiceIds,
          note: line.note
        })),
        orderType: posDineInEnabled ? orderType : null,
        tableNumber: posTableEnabled ? posTableNumber : null,
        customerName: posCustomerNameEnabled && customerName ? customerName : null,
        guestCount,
        segment
      }));
      cart = [];
      discountCode = '';
      appliedDiscountLabel = '';
      promoResult = null;
      resetOrderMeta();
      mobileCartOpen = false;
      showToast(`${language.t('obSaved')} · ${order.order_number}`);
      await Promise.all([refreshItems(), loadOpenBills()]);
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      checkingOut = false;
    }
  }

  async function confirmPay() {
    if (!payTarget) return checkout();
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    checkingOut = true;
    error = '';
    try {
      const order = await api.post<Order>(`/stores/${storeId}/orders/${payTarget.id}/pay`, {
        payment_method: paymentMethod,
        payment_provider: providers.length ? paymentProvider : null,
        cash_received: paymentMethod === 'CASH' && cashPaid >= payTotal ? cashPaid : null
      });
      receiptCashPaid = paymentMethod === 'CASH' ? cashPaid : 0;
      payModalOpen = false;
      payTarget = null;
      cashAmount = '0';
      receiptOrder = order;
      await loadOpenBills();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      checkingOut = false;
    }
  }

  // /pos?pay=<order id> (from Transactions) opens that bill's payment
  let payQueryDone = false;
  $effect(() => {
    const id = $page.url.searchParams.get('pay');
    const storeId = session.selectedStore?.id;
    if (!id || !storeId || payQueryDone) return;
    payQueryDone = true;
    void api.get<Order>(`/stores/${storeId}/orders/${id}`).then((o) => { if (o.status === 'OPEN') payOpenBill(o); }).catch(() => {});
  });

  function cartItemsPayload() {
    return cart.map((line) => ({
      item_id: line.item.id,
      quantity: line.quantity,
      selected_option_choice_ids: line.optionChoiceIds,
      selected_addon_choice_ids: line.addonChoiceIds,
      note: line.note.trim() || null
    }));
  }

  async function checkPromo() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !discountCode.trim() || cart.length === 0) return;
    promoLoading = true;
    try {
      const result = await api.post<PromoResult>(`/stores/${storeId}/orders/preview`, {
        discount_code: discountCode.trim(),
        order_type: dineInActive ? 'DINE_IN' : null,
        items: cartItemsPayload()
      });
      promoResult = result;
    } catch (err) {
      promoResult = { valid: false, subtotal, discount_amount: 0, total_amount: subtotal, message: err instanceof Error ? err.message : language.t('error') };
    } finally {
      promoLoading = false;
    }
  }

  async function checkAutoPromo() {
    const storeId = session.selectedStore?.id;
    if (!storeId || cart.length === 0) return;
    promoLoading = true;
    try {
      const clientTotal = subtotal;
      const result = await api.post<PromoResult>(`/stores/${storeId}/orders/preview`, {
        items: cartItemsPayload()
      });
      // Backend bakes auto ITEM discounts into result.subtotal, not discount_amount.
      // Detect them by comparing the client total (pre-discount) vs backend subtotal (post-discount).
      const autoAmount = clientTotal - result.subtotal;
      if (autoAmount > 0) {
        promoResult = { valid: true, subtotal: clientTotal, discount_amount: autoAmount, total_amount: result.subtotal, message: '' };
        if (!appliedDiscountLabel) appliedDiscountLabel = language.t('automatic');
      } else {
        promoResult = null;
      }
    } catch {
      promoResult = null;
    } finally {
      promoLoading = false;
    }
  }

  function schedulePromoCheck() {
    if (autoPromoTimer !== null) clearTimeout(autoPromoTimer);
    if (onlineMode || addTo) { promoResult = null; return; }
    if (cart.length === 0) { promoResult = null; return; }
    autoPromoTimer = setTimeout(() => {
      if (discountCode) void checkPromo();
      else void checkAutoPromo();
    }, 400);
  }

  function selectDiscountFromModal(d: Discount) {
    discountCode = d.code ?? '';
    appliedDiscountLabel = d.name;
    discountModalOpen = false;
    promoResult = null;
    if (cart.length > 0) void checkPromo();
  }

  function clearAppliedDiscount() {
    discountCode = '';
    appliedDiscountLabel = '';
    promoResult = null;
    if (cart.length > 0) void checkAutoPromo();
  }


  async function checkout() {
    const storeId = session.selectedStore?.id;
    if (!storeId || cart.length === 0) return;
    checkingOut = true;
    error = '';
    try {
      const online = onlineMode && channel;
      const order = await api.post<Order>(`/stores/${storeId}/orders`, toOrderPayload({
        paymentMethod,
        paymentProvider: providers.length ? paymentProvider : null,
        channel: online ? channel : null,
        channelOrderId: online ? onlineOrderId : null,
        appTotal: online ? appTotalNum : null,
        driverName: online ? onlineDriver : null,
        notes: online ? onlineNote.trim() || null : null,
        discountCode,
        items: cart.map((line) => ({
          itemId: line.item.id,
          quantity: line.quantity,
          optionChoiceIds: line.optionChoiceIds,
          addonChoiceIds: line.addonChoiceIds,
          note: line.note
        })),
        orderType: posDineInEnabled && !online ? orderType : null,
        tableNumber: posTableEnabled && !online ? posTableNumber : null,
        guestCount: online ? null : guestCount,
        segment: online ? null : segment,
        customerName: online ? onlineCustomer.trim() : posCustomerNameEnabled && customerName ? customerName : null,
        cashReceived: !online && paymentMethod === 'CASH' && cashPaid >= totalDue ? cashPaid : null
      }));
      cart = [];
      discountCode = '';
      appliedDiscountLabel = '';
      promoResult = null;
      resetOrderMeta();
      resetOnlineForm();
      receiptCashPaid = paymentMethod === 'CASH' ? cashPaid : 0;
      cashAmount = '0';
      payModalOpen = false;
      receiptOrder = order;
      mobileCartOpen = false;
      await refreshItems();
    } catch (err) { error = err instanceof Error ? err.message : 'Checkout failed'; }
    finally { checkingOut = false; }
  }

  function closeReceipt() {
    receiptOrder = null;
    receiptCashPaid = 0;
    btError = '';
  }

  let btPrinting = $state(false);
  let btError = $state('');

  async function handleBtPrint() {
    if (!receiptOrder) return;
    btPrinting = true;
    btError = '';
    try {
      const store = session.selectedStore;
      if (!store) return;
      const bytes = await buildReceiptBytes(receiptOrder, store, receiptCashPaid);
      await printEscPos(bytes);
    } catch (err) {
      btError = err instanceof Error ? err.message : language.t('error');
    } finally {
      btPrinting = false;
    }
  }

  // ── POS order metadata ────────────────────────────────────
  let posTableEnabled = $derived(session.selectedStore?.pos_table_enabled ?? false);
  let posTableCount = $derived(session.selectedStore?.pos_table_count ?? 10);
  let posCustomerNameEnabled = $derived(session.selectedStore?.pos_customer_name_enabled ?? false);
  let hasOrderInfo = $derived(posDineInEnabled || posTableEnabled || posCustomerNameEnabled);

  let posTableNumber = $state<string | null>(null);
  let customerName = $state('');
  let tableModalOpen = $state(false);
  let guestCount = $state(1);
  let segment = $state('');
  let detailOpen = $state(false);
  let noteOpenId = $state<string | null>(null);
  const focusEl = (node: HTMLElement) => node.focus();
  let whereStr = $derived(
    [
      orderType === 'DINE_IN' ? language.t('dineIn') : orderType === 'TAKE_AWAY' ? language.t('takeAway') : '',
      posTableNumber ? `${language.t('table')} ${posTableNumber}` : '',
      customerName,
      `${guestCount} ${language.t('guestCount').toLowerCase()}`
    ].filter(Boolean).join(' · ')
  );  const SEGMENTS = ['FAM', 'GENZ', 'GENM', 'GENA', 'OFFC', 'CPL'] as const;
  const segLabel = (code: string) => language.t(`seg${code}` as 'segFAM');

  function resetOrderMeta() {
    orderType = null;
    posTableNumber = null;
    customerName = '';
    guestCount = 1;
    segment = '';
    detailOpen = false;
  }

  let mobileCartOpen = $state(false);

  const VIEW_KEY = 'kasir.pos.viewMode';
  let viewMode = $state<'grid' | 'list'>((localStorage.getItem(VIEW_KEY) as 'grid' | 'list') ?? 'grid');

  function setViewMode(mode: 'grid' | 'list') {
    viewMode = mode;
    localStorage.setItem(VIEW_KEY, viewMode);
  }

  let loadedStoreId = $state('');
  $effect(() => {
    const storeId = session.selectedStore?.id;
    if (storeId && storeId !== loadedStoreId) {
      loadedStoreId = storeId;
      void load();
    }
  });
</script>

<svelte:head><title>{language.t('pos')} | Kasir</title></svelte:head>

<!-- Payment modal -->
{#if payModalOpen}
  <div class="sheet-backdrop cash-backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) closePay(); }}>
    <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
    <section class="pay-modal" role="dialog" aria-modal="true" aria-label={language.t('payMethod')}>
      <div class="pay-sum">
        <div class="pay-sum-head">{language.t('order')}</div>
        <div>
          <div class="pay-sum-lbl">{language.t('payBillTotal')}</div>
          <div class="pay-sum-total">{formatRupiah(payTotal)}</div>
          {#if !payTarget && promoResult?.valid && promoResult.discount_amount > 0}
            <div class="pay-sum-save">{language.t('discountSavings')} {formatRupiah(promoResult.discount_amount)}</div>
          {/if}
        </div>
        <div class="pay-sum-items">
          {#if payTarget}
            {#each payTarget.items ?? [] as l (l.id)}
              <div class="pay-sum-line">
                <span class="pay-sum-qty">{l.quantity}×</span>
                <div class="min-w-0 flex-1">
                  <div>{l.item_name_snapshot}</div>
                  {#if snapNames(l) || l.note}<div class="pay-sum-sub">{[snapNames(l), l.note ? `“${l.note}”` : ''].filter(Boolean).join(' · ')}</div>{/if}
                </div>
              </div>
            {/each}
          {:else}
          {#each cart as l (l.lineId)}
            <div class="pay-sum-line">
              <span class="pay-sum-qty">{l.quantity}×</span>
              <div class="min-w-0 flex-1">
                <div>{l.item.name}</div>
                {#if choiceNames(l) || l.note}<div class="pay-sum-sub">{[choiceNames(l), l.note ? `“${l.note}”` : ''].filter(Boolean).join(' · ')}</div>{/if}
              </div>
            </div>
          {/each}
          {/if}
        </div>
        <div class="pay-sum-sub">{payTarget ? [payTarget.order_number, payTarget.table_number ? `${language.t('table')} ${payTarget.table_number}` : '', payTarget.customer_name ?? ''].filter(Boolean).join(' · ') : whereStr}</div>
      </div>
      <div class="pay-main">
        <div class="flex items-center justify-between">
          <span class="text-base font-semibold">{language.t('payMethod')}</span>
          <button class="icon-btn" onclick={closePay} aria-label={language.t('close')}><span class="ms !text-[18px]" aria-hidden="true">close</span></button>
        </div>
        <div class="pay-tiles" role="radiogroup" aria-label={language.t('payMethod')}>
          {#each payTiles as t (t.key)}
            {@const active = paymentMethod === t.method && (paymentProvider === t.provider || !t.provider)}
            <button type="button" role="radio" aria-checked={active} class="pay-tile {active ? 'pay-tile--active' : ''}" onclick={() => pickPayTile(t)}>
              <span class="pay-tile-icon">
                {#if t.logo}<img src="/images/pay/{t.logo}" alt="" />{:else}<span class="ms" aria-hidden="true">{t.icon}</span>{/if}
              </span>
              <span class="pay-tile-lbl">{t.label}</span>
            </button>
          {/each}
        </div>
        <div class="pay-panel">
          {#if paymentMethod === 'CASH'}
            <label class="block">
              <span class="pay-panel-lbl">{language.t('cashReceived')}</span>
              <span class="pay-cash-input"><span>Rp</span><input type="text" inputmode="numeric" value={cashPaid > 0 ? cashPaid.toLocaleString('id-ID') : ''} oninput={onCashInput} /></span>
            </label>
            <div class="flex flex-wrap gap-2">
              {#each quickCash as q (q)}
                <button class="pay-quick" onclick={() => (cashAmount = String(q))}>{q === payTotal ? language.t('exactAmount') : formatRupiah(q)}</button>
              {/each}
            </div>
            <div class="pay-change">
              <span>{cashPaid >= payTotal ? language.t('change') : language.t('short')}</span>
              <span class={cashPaid >= payTotal ? 'text-[var(--om-brand)]' : 'text-red-700'}>{formatRupiah(Math.abs(change))}</span>
            </div>
          {:else if paymentMethod === 'CARD'}
            <div class="pay-hint"><span class="ms !text-[56px]" aria-hidden="true">contactless</span><strong>{language.t('payEdcTitle')}</strong><span>{language.t('payEdcHint')}{paymentProvider ? ` · ${paymentProvider}` : ''}</span></div>
          {:else if paymentMethod === 'QRIS'}
            <div class="pay-hint"><span class="ms !text-[56px]" aria-hidden="true">qr_code_2</span><strong>{language.t('payQrTitle')}{paymentProvider ? ` ${paymentProvider}` : ''}</strong><span>{formatRupiah(payTotal)}</span></div>
          {:else}
            <div class="pay-hint"><span class="ms !text-[56px]" aria-hidden="true">account_balance</span><strong>{language.t('payTransferTitle')}</strong><span>{language.t('payTransferHint')}</span></div>
          {/if}
        </div>
        {#if error}<div class="menu-error" role="alert">{error}</div>{/if}
        <button class="charge-btn" disabled={checkingOut || (paymentMethod === 'CASH' && cashPaid < payTotal)} onclick={confirmPay}>
          {checkingOut ? language.t('processing') : `${language.t('confirm')} · ${formatRupiah(payTotal)}`}
        </button>
      </div>
    </section>
  </div>
{/if}

<!-- Void a line of the open bill -->
{#if voidLine}
  <div class="sheet-backdrop cash-backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) voidLine = null; }}>
    <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
    <section class="void-modal" role="dialog" aria-modal="true" aria-label={language.t('txVoidItem')}>
      <div class="flex items-center gap-3">
        <div class="min-w-0 flex-1">
          <div class="text-base font-semibold">{language.t('txVoidItem')}</div>
          <div class="truncate text-sm text-[var(--text-muted)]">{voidLine.item_name_snapshot}</div>
        </div>
        <button class="icon-btn" onclick={() => (voidLine = null)} aria-label={language.t('close')}><span class="ms !text-[20px]" aria-hidden="true">close</span></button>
      </div>
      {#if voidError}<div class="menu-error" role="alert">{voidError}</div>{/if}
      <div>
        <div class="group-label">{language.t('txVoidQty')}</div>
        <div class="qty-stepper mt-1 w-fit">
          <button class="step-btn" disabled={voidQty <= 1} onclick={() => (voidQty -= 1)}>−</button>
          <span class="step-num">{voidQty}</span>
          <button class="step-btn" disabled={voidQty >= Math.min(unitsLeft(voidLine), billUnits - 1)} onclick={() => (voidQty += 1)}>+</button>
        </div>
      </div>
      <div>
        <div class="group-label">{language.t('txReason')}</div>
        <div class="mt-1 flex flex-wrap gap-1.5">
          {#each VOID_REASONS as r (r)}<button class="choice-btn {voidReason === r ? 'choice-btn--active' : ''}" aria-pressed={voidReason === r} onclick={() => (voidReason = r)}>{r}</button>{/each}
        </div>
      </div>
      <button class="charge-btn" disabled={!voidReason || voidSaving} onclick={submitVoid}>{voidSaving ? language.t('saving') : language.t('txVoidItem')}</button>
    </section>
  </div>
{/if}

<!-- Open bills -->
{#if openBillModal}
  <div class="sheet-backdrop cash-backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) openBillModal = false; }}>
    <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
    <section class="ob-modal" role="dialog" aria-modal="true" aria-label={language.t('obTitle')}>
      <div class="ob-head">
        <div class="min-w-0 flex-1">
          <div class="text-base font-semibold">{language.t('obTitle')}</div>
          <div class="text-xs text-[var(--text-muted)]">{openBillTotal} · {formatRupiah(openBills.reduce((s, o) => s + o.total_amount, 0))}</div>
        </div>
        <button class="icon-btn" onclick={() => (openBillModal = false)} aria-label={language.t('close')}><span class="ms !text-[20px]" aria-hidden="true">close</span></button>
      </div>
      <label class="ob-search"><span class="ms !text-[20px]" aria-hidden="true">search</span><input placeholder={language.t('obSearch')} bind:value={openBillQuery} oninput={searchOpenBills} /></label>
      <div class="ob-list">
        {#each openBills as b (b.id)}
          <div class="ob-row">
            <div class="min-w-0 flex-1">
              <div class="flex items-baseline gap-2"><span class="font-semibold whitespace-nowrap">{(b.order_number ?? '').split('-').slice(-1)[0]}</span><span class="truncate">{b.customer_name || language.t('obWalkIn')}</span></div>
              <div class="text-xs text-[var(--text-muted)]">{[b.table_number ? `${language.t('table')} ${b.table_number}` : '', b.guest_count ? `${b.guest_count} ${language.t('guestCount').toLowerCase()}` : '', formatDateTime(b.created_at)].filter(Boolean).join(' · ')}</div>
            </div>
            <span class="font-bold tabular-nums whitespace-nowrap">{formatRupiah(b.total_amount)}</span>
            <button class="ob-add" onclick={() => startAddTo(b)}>{language.t('obAdd')}</button>
            <button class="ob-pay" onclick={() => payOpenBill(b)}>{language.t('obPay')}</button>
          </div>
        {:else}
          <div class="ob-empty"><span class="ms !text-[32px]" aria-hidden="true">task_alt</span><strong>{language.t('obEmpty')}</strong><span>{language.t('obEmptyHint')}</span></div>
        {/each}
      </div>
    </section>
  </div>
{/if}

{#if toast}<div class="pos-toast" role="status">{toast}</div>{/if}

<!-- Table picker modal -->
{#if tableModalOpen}
  <div
    class="sheet-backdrop"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) tableModalOpen = false; }}
  >
    <section class="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font flex-1 text-2xl font-bold text-[var(--espresso)]">{language.t('selectTable')}</h2>
        <button class="icon-btn" onclick={() => tableModalOpen = false} aria-label={language.t('close')}><span class="ms !text-[18px]" aria-hidden="true">close</span></button>
      </div>
      <div class="min-h-0 flex-1 overflow-y-auto p-5">
        <div class="grid grid-cols-4 gap-2">
          {#each Array.from({ length: posTableCount }, (_, i) => i + 1) as n}
            <button
              class="rounded-2xl border px-2 py-3 text-sm font-bold transition
                {posTableNumber === String(n)
                  ? 'border-[var(--espresso)] bg-[var(--espresso)] text-[var(--white)]'
                  : 'border-[var(--border)] bg-[var(--white)] text-[var(--espresso)] hover:bg-[var(--cream)]'}"
              onclick={() => { posTableNumber = String(n); tableModalOpen = false; }}
            >{n}</button>
          {/each}
        </div>
      </div>
      {#if posTableNumber}
        <div class="border-t border-[var(--border)] p-4">
          <button class="btn-outline w-full" onclick={() => { posTableNumber = null; tableModalOpen = false; }}>
            {language.t('removeTableSelection')}
          </button>
        </div>
      {/if}
    </section>
  </div>
{/if}

{#snippet typeTabs()}
  <div class="type-seg">
    {#if posDineInEnabled}
      <button class="type-btn {!onlineMode && orderType === 'DINE_IN' ? 'type-btn--active' : ''}" onclick={() => pickType('DINE_IN')}>{language.t('dineIn')}</button>
      <button class="type-btn {!onlineMode && orderType === 'TAKE_AWAY' ? 'type-btn--active' : ''}" onclick={() => pickType('TAKE_AWAY')}>{language.t('takeAway')}</button>
    {/if}
    {#if hasOnline}
      <button class="type-btn {onlineMode ? 'type-btn--active' : ''}" onclick={() => setOnline(!onlineMode)}>{language.t('online')}</button>
    {/if}
  </div>
{/snippet}

{#snippet onlineForm()}
  {#if onlineMode}
    <div class="online-form">
      <div class="online-channels">
        {#each enabledChannels as c (c.channel)}
          <button class="online-ch {channel === c.channel ? 'online-ch--active' : ''}" aria-label={CHANNEL_META[c.channel].label} aria-pressed={channel === c.channel} onclick={() => (channel = c.channel)}>
            <img src={CHANNEL_META[c.channel].logo} alt={CHANNEL_META[c.channel].label} />
          </button>
        {/each}
      </div>
      <label class="block">
        <span class="online-lbl">{language.t('onlinePlatformId')} *</span>
        <input class="field text-sm" placeholder={language.t('onlinePlatformIdHint')} bind:value={onlineOrderId} />
      </label>
      <label class="block">
        <span class="online-lbl">{language.t('onlineCustomer')} *</span>
        <input class="field text-sm" bind:value={onlineCustomer} />
      </label>
      <label class="block">
        <span class="online-lbl">{language.t('onlineDriver')}</span>
        <input class="field text-sm" maxlength="100" bind:value={onlineDriver} />
      </label>
      <label class="block">
        <span class="online-lbl">{language.t('onlineNote')}</span>
        <input class="field text-sm" bind:value={onlineNote} />
      </label>
      <label class="block">
        <span class="online-lbl">{language.t('onlineAppTotal')} (Rp) *</span>
        <input
          class="field text-right text-sm"
          type="text"
          inputmode="numeric"
          placeholder="0"
          value={onlineAppTotal}
          oninput={(e) => { const d = e.currentTarget.value.replace(/\D/g, ''); onlineAppTotal = d ? parseInt(d, 10).toLocaleString('id-ID') : ''; e.currentTarget.value = onlineAppTotal; }}
        />
      </label>
      {#if appTotalNum > 0 && appTotalNum !== subtotal}
        <div class="online-warn" role="alert">{language.t('onlineMismatch')} {formatRupiah(subtotal)}</div>
      {/if}
      {#if onlineTax > 0}
        <div class="online-tax">{language.t('onlineTaxIncluded')} {(taxBp / 100).toFixed(taxBp % 100 ? 2 : 0)}% · {formatRupiah(onlineTax)}</div>
      {/if}
    </div>
  {/if}
{/snippet}

{#snippet cartLines()}
  {#each cart as line (line.lineId)}
    {@const atLimit = line.item.stock !== null && line.item.stock !== undefined && line.quantity >= line.item.stock}
    <div class="cart-line">
      <div class="cart-line-body" role="button" tabindex="0" title={language.t('lineNote')} onclick={() => (noteOpenId = noteOpenId === line.lineId ? null : line.lineId)} onkeydown={(e) => { if (e.key === 'Enter') noteOpenId = noteOpenId === line.lineId ? null : line.lineId; }}>
        <div class="cart-line-name">{line.item.name}</div>
        {#if choiceNames(line)}<div class="cart-line-mods">{choiceNames(line)}</div>{/if}
        {#if line.note && noteOpenId !== line.lineId}<div class="cart-line-note">“{line.note}”</div>{/if}
        {#if noteOpenId === line.lineId}
          <input
            class="field mt-1 py-1.5 text-sm"
            maxlength="200"
            placeholder={language.t('lineNotePlaceholder')}
            aria-label={language.t('lineNote')}
            bind:value={line.note}
            onclick={(e) => e.stopPropagation()}
            onkeydown={(e) => { if (e.key === 'Enter') noteOpenId = null; }}
            onblur={() => (noteOpenId = null)}
            use:focusEl
          />
        {/if}
        {#if atLimit}<div class="cart-line-limit">{language.t('maxStockReached')}</div>{/if}
        {#if getLineUnitPrice(line) > 0}<div class="cart-line-price">{formatRupiah(getLineUnitPrice(line) * line.quantity)}</div>{/if}
      </div>
      <div class="qty-stepper">
        <button class="step-btn" onclick={() => changeQty(line, -1)}>−</button>
        <span class="step-num">{line.quantity}</span>
        <button class="step-btn" disabled={atLimit} onclick={() => changeQty(line, 1)}>+</button>
      </div>
    </div>
  {:else}
    <div class="cart-empty">
      <div class="cart-empty-icon">🧾</div>
      <div>{language.t('cartEmpty')}</div>
    </div>
  {/each}
{/snippet}

{#snippet orderDetail()}
  {#if !onlineMode}
    <div class="detail-wrap">
      <button class="detail-summary" aria-expanded={detailOpen} aria-label={language.t('orderDetail')} onclick={() => (detailOpen = !detailOpen)}>
        <span class="detail-chips">
          {#if posTableEnabled}
            <span class="detail-chip {posTableNumber ? 'detail-chip--on' : ''}"><span class="ms !text-[16px]" aria-hidden="true">table_restaurant</span>{posTableNumber ? `${language.t('table')} ${posTableNumber}` : language.t('selectTable')}</span>
          {/if}
          {#if posCustomerNameEnabled}
            <span class="detail-chip detail-chip--shrink"><span class="ms !text-[16px]" aria-hidden="true">person</span><span class="truncate">{customerName || language.t('customerNamePlaceholder').replace('...', '')}</span></span>
          {/if}
          <span class="detail-chip"><span class="ms !text-[16px]" aria-hidden="true">group</span>{guestCount}</span>
          <span class="detail-chip detail-chip--shrink"><span class="ms !text-[16px]" aria-hidden="true">pie_chart</span><span class="truncate">{segment ? segLabel(segment) : language.t('segment')}</span></span>
        </span>
        <span class="ms" aria-hidden="true">{detailOpen ? 'expand_less' : 'expand_more'}</span>
      </button>
      {#if detailOpen}
        <div class="detail-body">
          {#if posTableEnabled || posCustomerNameEnabled}
            <div class="detail-row">
              {#if posTableEnabled}
                <button class="detail-field" onclick={() => (tableModalOpen = true)}>
                  <span class="ms !text-[20px]" aria-hidden="true">table_restaurant</span>
                  <span class="flex-1 truncate text-left">{posTableNumber ? `${language.t('table')} ${posTableNumber}` : language.t('selectTable')}</span>
                  {#if posTableNumber}<span class="meta-clear" role="button" tabindex="0" aria-label={language.t('removeTableSelection')} onclick={(e) => { e.stopPropagation(); posTableNumber = null; }} onkeydown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); posTableNumber = null; } }}>×</span>{/if}
                </button>
              {/if}
              {#if posCustomerNameEnabled}
                <label class="detail-field">
                  <span class="ms !text-[20px]" aria-hidden="true">person</span>
                  <input class="min-w-0 flex-1 bg-transparent outline-none" placeholder={language.t('customerNamePlaceholder')} bind:value={customerName} />
                </label>
              {/if}
            </div>
          {/if}
          <div class="detail-row">
            <div class="detail-field detail-field--stepper" role="group" aria-label={language.t('guestCount')}>
              <button class="detail-step" aria-label="−" onclick={() => (guestCount = Math.max(1, guestCount - 1))}><span class="ms !text-[20px]" aria-hidden="true">remove</span></button>
              <span class="flex items-center gap-1 font-medium"><span class="ms !text-[20px]" aria-hidden="true">group</span>{guestCount}</span>
              <button class="detail-step" aria-label="+" onclick={() => (guestCount = Math.min(999, guestCount + 1))}><span class="ms !text-[20px]" aria-hidden="true">add</span></button>
            </div>
            <label class="detail-field relative">
              <span class="ms !text-[20px]" aria-hidden="true">pie_chart</span>
              <select class="min-w-0 flex-1 appearance-none bg-transparent pr-6 outline-none" aria-label={language.t('segment')} bind:value={segment}>
                <option value="">{language.t('segmentPlaceholder')}</option>
                {#each SEGMENTS as code (code)}<option value={code}>{code} · {segLabel(code)}</option>{/each}
              </select>
              <span class="ms pointer-events-none absolute right-2 !text-[20px]" aria-hidden="true">expand_more</span>
            </label>
          </div>
        </div>
      {/if}
    </div>
  {/if}
{/snippet}

{#snippet cartPanel(sheet: boolean)}
  <div class="cart-header {sheet ? 'sheet-header' : ''}">
    {#if sheet}<button class="icon-btn" onclick={() => (mobileCartOpen = false)} aria-label={language.t('close')}><span class="ms !text-[22px]" aria-hidden="true">arrow_back</span></button>{/if}
    <h2 class="cart-title">{addTo ? `${language.t('obAddingTo')} #${(addTo.order_number ?? '').split('-').slice(-1)[0]}` : language.t('order')}</h2>
    {#if totalItems > 0}<span class="cart-badge">{totalItems}</span>{/if}
    <button class="ob-open" aria-label={language.t('obTitle')} title={language.t('obTitle')} onclick={openBillList}>
      <span class="ms" aria-hidden="true">receipt_long</span>
      {#if openBillTotal > 0}<span class="ob-open-badge">{openBillTotal}</span>{/if}
    </button>
  </div>
  {#if (posDineInEnabled || hasOnline) && !addTo}<div class="cart-types">{@render typeTabs()}</div>{/if}
  {@render orderDetail()}
  <div class="cart-lines">
    {@render onlineForm()}
    {#if addTo}
      {#each addTo.items ?? [] as l (l.id)}
        <div class="cart-line cart-line--locked">
          <span class="ms !text-[18px] text-[var(--text-muted)]" aria-hidden="true">lock</span>
          <div class="cart-line-body">
            <div class="cart-line-name {unitsLeft(l) <= 0 ? 'line-through' : ''}">{unitsLeft(l)}× {l.item_name_snapshot}{#if l.void_qty}<span class="ml-1.5 text-[12px] font-bold text-[var(--om-danger)]">{l.void_qty} {language.t('txVoided')}</span>{/if}</div>
            {#if snapNames(l) || l.note}<div class="cart-line-mods">{[snapNames(l), l.note ? `“${l.note}”` : ''].filter(Boolean).join(' · ')}</div>{/if}
          </div>
          {#if canVoid && unitsLeft(l) > 0}
            <button class="line-void" disabled={billUnits <= 1} title={billUnits <= 1 ? language.t('txVoidOpenLast') : language.t('txVoidItem')} aria-label={`${language.t('txVoidItem')} ${l.item_name_snapshot}`} onclick={() => openVoid(l)}>
              <span class="ms !text-[16px]" aria-hidden="true">delete</span>{language.t('txVoid')}
            </button>
          {/if}
        </div>
      {/each}
    {/if}
    {@render cartLines()}
  </div>
  <div class="cart-footer">
    {#if !onlineMode && !addTo}
      <div class="discount-row">
        {#if promoResult?.valid && promoResult.discount_amount > 0}
          <div class="discount-chip">
            <span class="ms !text-[13px] shrink-0" aria-hidden="true">sell</span>
            <span class="discount-chip-label">
              {appliedDiscountLabel || language.t('discounts')}
              <span class="discount-chip-savings">· {language.t('discountSavings')} {formatRupiah(promoResult.discount_amount)}</span>
            </span>
            <button class="discount-chip-clear" onclick={clearAppliedDiscount} aria-label={language.t('discounts')}>×</button>
          </div>
        {:else if promoResult !== null && !promoResult.valid}
          <div class="discount-err-row">
            <button class="discount-trigger" onclick={() => (discountModalOpen = true)}>
              <span class="ms !text-[13px]" aria-hidden="true">sell</span>
              <span>{language.t('addDiscount')}</span>
            </button>
            <span class="discount-err-msg">{promoResult.message}</span>
          </div>
        {:else}
          <button class="discount-trigger {promoLoading ? 'discount-trigger--loading' : ''}" onclick={() => (discountModalOpen = true)}>
            <span class="ms !text-[13px]" aria-hidden="true">sell</span>
            <span>{promoLoading ? language.t('checking') : language.t('addDiscount')}</span>
          </button>
        {/if}
      </div>
    {/if}
    {#if addTo}
      <div class="order-summary">
        <div class="summary-row"><span>{language.t('obPrev')}</span><span>{formatRupiah(addTo.total_amount)}</span></div>
        <div class="summary-row"><span>{language.t('obAddedSum')}</span><span>{formatRupiah(addTotal - addTo.total_amount)}</span></div>
        <div class="summary-total"><span>{language.t('total')}</span><span>{formatRupiah(addTotal)}</span></div>
      </div>
    {:else}
    <div class="order-summary">
      <div class="summary-row"><span>{language.t('subtotal')}</span><span>{formatRupiah(subtotal)}</span></div>
      {#if promoResult?.valid && promoResult.discount_amount > 0}
        <div class="summary-row summary-row--discount">
          <span>{language.t('discounts')} {appliedDiscountLabel ? `· ${appliedDiscountLabel}` : ''}</span>
          <span>−{formatRupiah(promoResult.discount_amount)}</span>
        </div>
      {/if}
      {#if serviceFee > 0}<div class="summary-row"><span>{language.t('serviceLabel')}</span><span>{formatRupiah(serviceFee)}</span></div>{/if}
      {#if pb1Fee > 0}<div class="summary-row"><span>{language.t('pb1Label')}</span><span>{formatRupiah(pb1Fee)}</span></div>{/if}
      <div class="summary-total"><span>{language.t('total')}</span><span>{formatRupiah(totalDue)}</span></div>
    </div>
    {/if}
    {#if error && addTo}<div class="menu-error" role="alert">{error}</div>{/if}
    {#if addTo}
      <div class="footer-actions">
        <button class="ob-save" onclick={cancelAdd}>{language.t('obCancelAdd')}</button>
        <button class="charge-btn" disabled={cart.length === 0 || checkingOut} onclick={saveAdd}>{checkingOut ? language.t('processing') : `${language.t('obSaveAdd')} ${formatRupiah(addTotal - addTo.total_amount)}`}</button>
      </div>
    {:else}
    <div class="footer-actions">
      {#if !onlineMode}
        <button class="ob-save" disabled={cart.length === 0 || checkingOut} onclick={saveOpenBill}><span class="ms !text-[20px]" aria-hidden="true">receipt_long</span>{language.t('obSave')}</button>
      {/if}
      <button class="charge-btn" disabled={cart.length === 0 || checkingOut || (onlineMode && !onlineValid)} onclick={handleCharge}>
        {checkingOut ? language.t('processing') : `${language.t(onlineMode ? 'onlineSend' : 'charge')} ${formatRupiah(totalDue)}`}
      </button>
    </div>
    {/if}
  </div>
{/snippet}

<div class="pos-shell">
  <!-- Main menu section -->
  <section class="menu-section">

    <!-- Category chips + search + view toggle -->
    <div class="pos-top">
      <div class="cat-strip no-scrollbar">
        <button
          class="cat-chip {activeCategoryId === 'all' ? 'cat-chip--active' : ''}"
          onclick={() => activeCategoryId = 'all'}
        >{language.t('all')}</button>
        {#each categories as category}
          <button
            class="cat-chip {activeCategoryId === category.id ? 'cat-chip--active' : ''}"
            onclick={() => activeCategoryId = category.id}
          >{category.icon ?? ''} {category.name}</button>
        {/each}
      </div>

      <div class="pos-tools">
        <label class="search-box">
          <span class="ms !text-[18px]" aria-hidden="true">search</span>
          <input placeholder={language.t('searchMenu')} bind:value={search} />
        </label>
        <div class="view-toggle" role="group" aria-label={language.t('menu')}>
          <button class="view-btn {viewMode === 'grid' ? 'view-btn--active' : ''}" aria-pressed={viewMode === 'grid'} aria-label="Grid" onclick={() => setViewMode('grid')}><span class="ms !text-[20px]" aria-hidden="true">grid_view</span></button>
          <button class="view-btn {viewMode === 'list' ? 'view-btn--active' : ''}" aria-pressed={viewMode === 'list'} aria-label="List" onclick={() => setViewMode('list')}><span class="ms !text-[20px]" aria-hidden="true">format_list_bulleted</span></button>
        </div>
      </div>
    </div>

    {#if error}
      <div class="menu-error">{error}</div>
    {/if}

    <!-- Section heading -->
    <div class="menu-heading">
      <h1 class="display-font menu-title">{activeCategoryName}</h1>
      {#if onlineMode && channel}<span class="menu-count">· {language.t('onlinePriceNote')} {CHANNEL_META[channel].label}</span>{/if}
      <span class="menu-count">{filteredItems.length} {filteredItems.length === 1 ? language.t('item') : language.t('items')}</span>
    </div>

    <!-- Grid view -->
    {#if viewMode === 'grid'}
      <div class="item-grid">
        {#each filteredItems as item}
          {@const qty = itemQuantity(item)}
          {@const oos = item.stock === 0}
          {@const tracked = item.stock !== null && item.stock !== undefined}
          <button
            class="item-card {oos ? 'item-card--oos' : ''} {qty && !oos ? 'item-card--selected' : ''}"
            disabled={oos}
            onclick={() => addItem(item)}
          >
            <div class="item-img-wrap">
              {#if item.icon}
                <div class="item-emoji">{item.icon}</div>
              {:else}
                {#if item.image_url}
                  <img src={mediaUrl(item.image_url)} alt={item.name} class="item-img object-cover" />
                {:else}
                  <div class="img-placeholder" aria-hidden="true"><CupcakeIcon size={110} /></div>
                {/if}
              {/if}
              {#if qty && !oos}<span class="qty-badge">{qty}</span>{/if}
              {#if oos}<span class="oos-badge">{language.t('stockOut')}</span>{/if}
            </div>
            <div class="item-info">
              <div class="item-name">{item.name}</div>
              <div class="item-meta">
                <span class="item-price">{itemPrice(item) > 0 ? formatRupiah(itemPrice(item)) : ''}</span>
                {#if hasItemModifiers(item)}<span class="item-opt">{language.t('pickOptions')}</span>{/if}
              </div>
              {#if tracked && !oos}<div class="item-stock">{language.t('stockRemaining')} {item.stock}</div>{/if}
            </div>
          </button>
        {:else}
          <div class="menu-empty">{loading ? language.t('loading') : language.t('noItemsFound')}</div>
        {/each}
      </div>

    <!-- List view -->
    {:else}
      <div class="item-list-wrap">
        {#each filteredItems as item}
          {@const qty = itemQuantity(item)}
          {@const oos = item.stock === 0}
          {@const tracked = item.stock !== null && item.stock !== undefined}
          <button
            class="list-row {oos ? 'list-row--oos' : ''} {qty && !oos ? 'list-row--selected' : ''}"
            disabled={oos}
            onclick={() => addItem(item)}
          >
            <div class="list-info">
              <div class="list-name">{item.name}{#if oos}<span class="tag tag--oos">{language.t('stockOut')}</span>{/if}</div>
              <div class="list-tags">
                {#if hasItemModifiers(item)}<span class="item-opt">{language.t('pickOptions')}</span>{/if}
                {#if tracked && !oos}<span class="item-stock">{language.t('stockRemaining')} {item.stock}</span>{/if}
              </div>
            </div>
            <span class="list-price">{itemPrice(item) > 0 ? formatRupiah(itemPrice(item)) : ''}</span>
            {#if qty}<span class="qty-pill">{qty}</span>{/if}
          </button>
        {:else}
          <div class="menu-empty">{loading ? language.t('loading') : language.t('noItemsFound')}</div>
        {/each}
      </div>
    {/if}

    <!-- Mobile cart bar -->
    {#if cart.length > 0}
      <button class="mobile-cart-btn" onclick={() => mobileCartOpen = true}>
        <span class="mobile-cart-count">{totalItems}</span>
        <span class="mobile-cart-lbl">{language.t('order')}</span>
        <span class="mobile-cart-total">{formatRupiah(subtotal)}</span>
        <span class="ms !text-[18px]" aria-hidden="true">shopping_cart</span>
      </button>
    {/if}
  </section>

  <!-- Desktop cart panel -->
  <aside class="cart-panel">
    {@render cartPanel(false)}
  </aside>
</div>

<!-- Mobile cart sheet -->
{#if mobileCartOpen}
  <div class="sheet-backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) mobileCartOpen = false; }}>
    <div class="cart-sheet" role="dialog" aria-modal="true" aria-label="Cart" tabindex="-1">
      {@render cartPanel(true)}
    </div>
  </div>
{/if}

<!-- Receipt modal -->
{#if receiptOrder}
  <div class="sheet-backdrop receipt-backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) closeReceipt(); }}>
    <section class="receipt-modal" role="dialog" aria-modal="true">
      <div class="flex justify-end px-3 pt-3 print:hidden">
        <button class="icon-btn" onclick={closeReceipt} aria-label={language.t('close')}><span class="ms !text-[16px]" aria-hidden="true">close</span></button>
      </div>
      <div class="receipt-body">
        <ReceiptView lines={receiptLines} paper={receiptOpts.paper} />
      </div>

      {#if btError}
        <div class="receipt-bt-error">{btError}</div>
      {/if}
      <div class="receipt-actions print:hidden">
        <button class="btn-outline flex-1" onclick={() => window.print()}>{language.t('printReceipt')}</button>
        {#if canPrint()}
          <button class="btn-primary flex-1" onclick={handleBtPrint} disabled={btPrinting}>
            {btPrinting ? language.t('processing') : language.t('bluetooth')}
          </button>
        {/if}
      </div>
    </section>
  </div>
{/if}

<!-- Discount modal -->
{#if discountModalOpen}
  <div
    class="sheet-backdrop"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) discountModalOpen = false; }}
  >
    <section class="discount-modal-shell" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font flex-1 text-2xl font-bold text-[var(--espresso)]">{language.t('chooseDiscount')}</h2>
        <button class="icon-btn" onclick={() => discountModalOpen = false} aria-label={language.t('close')}><span class="ms !text-[18px]" aria-hidden="true">close</span></button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto p-5 space-y-5">

        <!-- Code-based discounts -->
        {#if codeDiscounts.length > 0}
          <div>
            <div class="discount-section-label">{language.t('availablePromoCodes')}</div>
            <div class="grid grid-cols-2 gap-2">
              {#each codeDiscounts as d}
                <button
                  class="discount-option-card {promoResult?.valid && appliedDiscountLabel === d.name ? 'discount-option-card--active' : ''}"
                  onclick={() => selectDiscountFromModal(d)}
                  disabled={cart.length === 0}
                >
                  <div class="flex flex-col items-start gap-1.5">
                    <div class="min-w-0">
                      <div class="discount-option-name">{d.name}</div>
                      <div class="discount-option-desc">{discountSummary(d)}{d.min_order_amount ? ` · Min. ${formatRupiah(d.min_order_amount)}` : ''}</div>
                    </div>
                    <div class="discount-option-code-badge">{d.code}</div>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Auto discounts (info only) -->
        {#if autoDiscounts.length > 0}
          <div>
            <div class="discount-section-label">{language.t('automatic')}</div>
            <div class="grid grid-cols-2 gap-2">
              {#each autoDiscounts as d}
                <div class="discount-auto-card">
                  <div class="flex flex-col items-start gap-1.5">
                    <div class="min-w-0">
                      <div class="discount-option-name">{d.name}</div>
                      <div class="discount-option-desc">{discountSummary(d)}{d.min_order_amount ? ` · Min. ${formatRupiah(d.min_order_amount)}` : ''}</div>
                    </div>
                    <span class="discount-auto-badge">{language.t('automatic')}</span>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if discounts.length === 0}
          <div class="py-6 text-center text-sm text-[var(--text-muted)]">{language.t('noDiscountsAvailable')}</div>
        {/if}
      </div>
    </section>
  </div>
{/if}

<!-- Modifier modal -->
{#if modifierItem}
  <div class="sheet-backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) closeModifierModal(); }}>
    <section class="modifier-modal" role="dialog" aria-modal="true" aria-label={modifierItem.name} tabindex="-1">
      <div class="modifier-header">
        <div class="modifier-thumb">
          {#if modifierItem.image_url}
            <img src={mediaUrl(modifierItem.image_url)} alt="" class="h-full w-full object-cover" />
          {:else}
            <div class="img-placeholder" aria-hidden="true"><CupcakeIcon size={28} /></div>
          {/if}
        </div>
        <div class="modifier-info"><h2 class="modifier-name">{modifierItem.name}</h2></div>
        <button class="icon-btn" onclick={closeModifierModal} aria-label={language.t('close')}><span class="ms !text-[20px]" aria-hidden="true">close</span></button>
      </div>

      <div class="modifier-body">
        {#each modifierItem.option_groups ?? [] as group}
          {#if getGroupChoices(group).length}
            <div class="modifier-group">
              <div class="group-label">{getGroupLabel(group)}{#if group.is_required ?? group.required}<span class="group-required">{language.t('required')}</span>{/if}</div>
              <div class="choice-wrap">
                {#each getGroupChoices(group) as choice}
                  <button
                    class="choice-btn {selectedOptionChoiceIds[group.id] === choice.id ? 'choice-btn--active' : ''}"
                    aria-pressed={selectedOptionChoiceIds[group.id] === choice.id}
                    onclick={() => selectedOptionChoiceIds = { ...selectedOptionChoiceIds, [group.id]: choice.id }}
                  >
                    {getChoiceLabel(choice)}
                    {#if mk(getChoicePrice(choice)) > 0}<span class="choice-price">+{formatRupiah(mk(getChoicePrice(choice)))}</span>{/if}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        {/each}

        {#each modifierItem.addon_groups ?? [] as group}
          {#if getGroupChoices(group).length}
            <div class="modifier-group">
              <div class="group-label">{getGroupLabel(group)}{#if group.is_required || (group.min_select ?? 0) > 0}<span class="group-required">{language.t('required')}</span>{/if}</div>
              <div class="choice-wrap">
                {#each getGroupChoices(group) as choice}
                  <button
                    class="choice-btn {selectedAddonChoiceIds.includes(choice.id) ? 'choice-btn--active' : ''}"
                    aria-pressed={selectedAddonChoiceIds.includes(choice.id)}
                    onclick={() => toggleAddon(choice.id)}
                  >
                    {getChoiceLabel(choice)}
                    {#if mk(getChoicePrice(choice)) > 0}<span class="choice-price">+{formatRupiah(mk(getChoicePrice(choice)))}</span>{/if}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        {/each}

        <div class="modifier-group">
          <div class="group-label">{language.t('lineNote')}</div>
          <div class="choice-wrap">
            <button class="choice-btn {modifierNoteOn ? 'choice-btn--active' : ''}" aria-pressed={modifierNoteOn} onclick={() => (modifierNoteOn = !modifierNoteOn)}>
              <span class="ms !text-[20px]" aria-hidden="true">edit_note</span>{language.t('noteCustom')}
            </button>
          </div>
          {#if modifierNoteOn}
            <input class="field note-field" maxlength="80" aria-label={language.t('lineNote')} placeholder={language.t('lineNotePlaceholder')} bind:value={modifierNote} use:focusEl />
            <span class="note-hint">{language.t('noteHint')}</span>
          {/if}
        </div>
      </div>

      <div class="modifier-footer">
        <button class="charge-btn modifier-add-btn" disabled={!canAddModifierItem} onclick={addModifierItemToCart}>
          {language.t('addShort')}{modifierUnitPrice > 0 ? ` · ${formatRupiah(modifierUnitPrice)}` : ''}
        </button>
      </div>
    </section>
  </div>
{/if}

<style>
  .cart-line-note { font-size: 12px; color: #6a4400; font-weight: 500; }
  .detail-wrap { padding: 8px 16px 0; display: flex; flex-direction: column; gap: 8px; }
  .detail-summary { display: flex; align-items: center; gap: 6px; min-height: 44px; padding: 0 6px 0 10px; border: 1px solid var(--border); border-radius: 10px; background: var(--white); font-size: 14px; text-align: left; min-width: 0; }
  .detail-summary:hover { background: var(--cream); }
  .detail-chips { flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; overflow: hidden; white-space: nowrap; }
  .detail-chip { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; color: var(--text-muted); }
  .detail-chip--on { color: var(--espresso); font-weight: 600; }
  .detail-chip--shrink { flex-shrink: 1; min-width: 0; }
  .detail-body { display: flex; flex-direction: column; gap: 8px; }
  .detail-row { display: flex; gap: 8px; }
  .detail-field { flex: 1 1 0; min-width: 0; display: flex; align-items: center; gap: 8px; height: var(--om-tap, 44px); padding: 0 10px; border: 1px solid var(--border); border-radius: 10px; background: var(--white); font-size: 16px; color: var(--espresso); }
  .detail-field--stepper { justify-content: space-between; padding: 0; }
  .detail-step { width: var(--om-tap, 44px); height: 100%; display: grid; place-items: center; color: var(--text-muted); border-radius: 10px; }
  .detail-step:hover { background: var(--cream); color: var(--espresso); }
  /* ─── Shell ─── */
  .pos-shell {
    position: relative;
    display: flex;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    background: var(--background);
  }

  /* ─── Menu Section ─── */
  .menu-section {
    display: flex;
    flex: 1;
    min-width: 0;
    flex-direction: column;
    background: var(--background);
  }

  /* Top bar: chips + search + view toggle */
  .pos-top {
    display: flex;
    flex-wrap: wrap-reverse;
    align-items: flex-end;
    gap: 10px;
    padding: var(--om-page-pad) var(--om-page-pad) 6px;
    flex-shrink: 0;
  }
  .pos-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    min-width: 0;
  }
  .search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    height: var(--om-tap);
    padding: 0 12px;
    width: 240px;
    max-width: 100%;
    min-width: 0;
    border: 1px solid var(--om-border);
    border-radius: 10px;
    background: var(--om-surface);
    color: var(--om-text-secondary);
  }
  .search-box:focus-within { border-color: var(--om-ink); }
  .search-box input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--om-ink);
    font-size: 16px;
  }
  .view-toggle {
    display: flex;
    gap: 4px;
    padding: 3px;
    border-radius: 12px;
    background: var(--om-fill-muted);
    flex-shrink: 0;
  }
  .view-btn {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border: none;
    border-radius: 9px;
    background: transparent;
    color: var(--om-ink);
    cursor: pointer;
  }
  .view-btn--active { background: var(--om-surface); box-shadow: 0 1px 2px rgba(16, 20, 15, 0.12); }

  .menu-error {
    margin: 12px 14px 0;
    padding: 10px 14px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 10px;
    color: #b91c1c;
    font-size: 0.825rem;
    flex-shrink: 0;
  }

  /* Category chips */
  .cat-strip {
    display: flex;
    flex: 1 1 240px;
    min-width: 0;
    gap: 6px;
    overflow-x: auto;
  }

  .cat-chip {
    flex-shrink: 0;
    padding: 7px 15px;
    min-height: var(--om-tap);
    border-radius: var(--om-r-pill);
    border: 2px solid var(--om-border);
    background: var(--om-surface);
    color: var(--om-ink-2);
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.15s;
  }
  .cat-chip:hover { border-color: var(--om-ink); }
  .cat-chip--active { background: var(--om-brand-tint); border-color: var(--om-brand); color: var(--om-ink); }

  /* Section heading */
  .menu-heading {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 14px var(--om-page-pad) 8px;
    flex-shrink: 0;
  }
  .menu-title { font-size: 16px; font-weight: 600; color: var(--espresso); margin: 0; }
  .menu-count { font-size: 12px; font-weight: 400; color: var(--text-muted); }

  /* ─── Grid ─── */
  .item-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
    padding: 4px 16px 16px;
    overflow-y: auto;
    flex: 1;
    align-content: start;
    grid-auto-rows: max-content;
  }
  @media (min-width: 768px) { .item-grid { grid-template-columns: repeat(auto-fill, minmax(156px, 1fr)); } }

  .item-card {
    display: flex;
    flex-direction: column;
    border-radius: var(--om-r-card);
    overflow: hidden;
    border: 1.5px solid var(--om-border);
    background: var(--om-surface);
    text-align: left;
    cursor: pointer;
    align-self: start;
    transition: border-color 0.15s;
  }
  .item-card:hover:not(:disabled) { border-color: var(--om-ink); }
  .item-card--selected { border-color: var(--om-brand); }
  .item-card--oos { opacity: 0.45; cursor: not-allowed; }

  .item-img-wrap {
    position: relative;
    aspect-ratio: 4 / 3;
    flex-shrink: 0;
    background: var(--om-fill-image);
    overflow: hidden;
  }
  .item-img { position: absolute; inset: 0; width: 100%; height: 100%; display: block; object-fit: cover; }
  .item-emoji { position: absolute; inset: 0; display: grid; place-items: center; font-size: 4rem; line-height: 1; overflow: hidden; }

  .oos-badge {
    background: var(--om-danger-tint);
    color: var(--om-danger);
    padding: 3px 9px;
    border-radius: var(--om-r-pill);
    font-size: 12px;
    font-weight: 600;
  }
  .qty-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    min-width: 26px;
    height: 26px;
    padding: 0 6px;
    background: var(--om-ink);
    color: var(--om-brand-on-dark);
    border-radius: var(--om-r-pill);
    font-size: 12px;
    font-weight: 700;
    display: grid;
    place-items: center;
  }

  .item-info {
    padding: 10px 12px 12px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 6px;
  }
  .item-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--dark);
    line-height: 1.3;
    display: -webkit-box;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .item-price { font-size: 12px; font-weight: 500; color: var(--om-text-secondary); }

  .menu-empty {
    grid-column: 1/-1;
    padding: 3rem 0;
    text-align: center;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  /* ─── List View ─── */
  .item-list-wrap {
    flex: 1;
    overflow-y: auto;
    padding: 4px 16px 16px;
    display: grid;
    grid-template-columns: 1fr;
    align-content: start;
    gap: 8px;
  }
  @media (min-width: 768px) {
    .item-list-wrap { grid-template-columns: 1fr 1fr; }
  }

  .list-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px 10px 10px;
    border-radius: 14px;
    border: 1.5px solid var(--border);
    background: var(--white);
    text-align: left;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  .list-row:hover:not(:disabled) { border-color: var(--mid-brown); background: var(--cream); }
  .list-row--selected { border-color: var(--warm-brown); background: var(--cream); }
  .list-row--oos { opacity: 0.5; cursor: not-allowed; }

  .list-info { flex: 1; min-width: 0; }
  .list-name { font-size: 0.9rem; font-weight: 700; color: var(--dark); }
  .list-tags { display: flex; flex-wrap: wrap; gap: 4px; margin: 3px 0; }
  .list-price { font-size: 0.85rem; font-weight: 800; color: var(--warm-brown); }

  .tag { padding: 2px 8px; border-radius: 99px; font-size: 0.65rem; font-weight: 800; }
  .tag--oos { background: #fee2e2; color: #b91c1c; }

  .qty-pill {
    display: grid;
    place-items: center;
    min-width: 28px;
    height: 28px;
    padding: 0 6px;
    border-radius: 99px;
    background: var(--primary);
    color: white;
    font-size: 0.78rem;
    font-weight: 800;
    flex-shrink: 0;
  }

  /* ─── Mobile Cart Bar ─── */
  .mobile-cart-btn {
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: 12px;
    z-index: 5;
    display: flex;
    align-items: center;
    gap: 12px;
    height: 58px;
    padding: 0 14px 0 12px;
    border-radius: 16px;
    border: none;
    background: var(--om-brand);
    color: white;
    font-weight: 600;
    box-shadow: 0 10px 24px rgba(16, 20, 15, 0.28);
    cursor: pointer;
  }
  .mobile-cart-count {
    display: grid;
    place-items: center;
    min-width: 30px;
    height: 30px;
    padding: 0 8px;
    border-radius: 15px;
    background: var(--om-brand-on-dark);
    color: var(--om-ink);
    font-size: 12px;
    font-weight: 800;
  }
  .mobile-cart-lbl { flex: 1; text-align: left; }
  .mobile-cart-total { font-weight: 700; font-variant-numeric: tabular-nums; }
  @media (min-width: 768px) {
    .mobile-cart-btn { display: none; }
  }

  /* ─── Cart Panel ─── */
  .cart-panel {
    display: none;
    flex-direction: column;
    width: 340px;
    flex-shrink: 0;
    background: var(--white);
    border-left: 1px solid var(--border);
  }
  @media (min-width: 768px) {
    .cart-panel { display: flex; }
  }

  .cart-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .sheet-header { border-bottom: 1px solid var(--border); }
  .cart-title { font-size: 1.5rem; font-weight: 700; color: var(--espresso); margin: 0; }
  .cart-badge {
    display: grid;
    place-items: center;
    min-width: 28px;
    height: 28px;
    padding: 0 6px;
    border-radius: 99px;
    background: var(--primary);
    color: white;
    font-size: 0.78rem;
    font-weight: 800;
  }

  .cart-lines {
    flex: 1;
    overflow-y: auto;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .cart-line {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    border-radius: 12px;
    background: var(--cream);
  }
  .cart-line-body { flex: 1; min-width: 0; }
  .cart-line-name { font-size: 0.875rem; font-weight: 700; color: var(--dark); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cart-line-mods { font-size: 0.72rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 1px; }
  .cart-line-limit { font-size: 0.7rem; font-weight: 700; color: #dc2626; margin-top: 1px; }
  .cart-line-price { font-size: 0.875rem; font-weight: 800; color: var(--warm-brown); margin-top: 4px; }

  .qty-stepper { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .step-btn {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    border: 1.5px solid var(--border);
    background: white;
    color: var(--espresso);
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  .step-btn:hover:not(:disabled) { background: var(--primary); border-color: var(--primary); color: white; }
  .step-btn:disabled { opacity: 0.35; cursor: not-allowed; }
  .step-num { width: 22px; text-align: center; font-size: 0.9rem; font-weight: 800; color: var(--dark); }

  .cart-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 0.875rem;
    min-height: 120px;
  }
  .cart-empty-icon { font-size: 2.5rem; opacity: 0.4; }

  /* ─── Cart Footer ─── */
  .cart-footer {
    flex-shrink: 0;
    padding: 12px 14px 16px;
    border-top: 1px solid var(--border);
  }

  /* ─── Order Meta ─── */
  .meta-clear {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 1.5px solid var(--border);
    background: var(--white);
    color: var(--text-muted);
    font-size: 1rem;
    font-weight: 700;
    display: grid;
    place-items: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
  }
  .meta-clear:hover { border-color: var(--primary); color: var(--espresso); }


  /* ─── Cash Modal ─── */
  .cash-backdrop { z-index: 55; }




  /* Calculator internals */



  .order-summary { margin-bottom: 12px; }
  .summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
    color: var(--text-muted);
    padding: 2px 0;
  }
  .charge-btn {
    display: block;
    width: 100%;
    padding: 16px;
    border-radius: 14px;
    border: none;
    background: var(--primary);
    color: white;
    font-size: 1rem;
    font-weight: 800;
    cursor: pointer;
    transition: background 0.15s, transform 0.1s;
    letter-spacing: 0.02em;
  }
  .charge-btn:hover:not(:disabled) { background: var(--dark); }
  .charge-btn:active:not(:disabled) { transform: scale(0.98); }
  .charge-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ─── Sheets & Modals ─── */
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    background: rgba(20, 13, 4, 0.65);
    backdrop-filter: blur(4px);
  }
  @media (min-width: 768px) { .sheet-backdrop { align-items: center; } }

  .cart-sheet {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-height: 88vh;
    overflow: hidden;
    border-radius: 24px 24px 0 0;
    background: var(--white);
  }
  @media (min-width: 768px) {
    .cart-sheet { max-width: 420px; border-radius: 24px; max-height: 90vh; }
  }

  /* Receipt */
  .receipt-backdrop { z-index: 50; }
  .receipt-modal {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 360px;
    max-height: 90vh;
    overflow: hidden;
    border-radius: 20px;
    background: white;
    box-shadow: 0 24px 64px rgba(0,0,0,0.4);
  }
  .receipt-body { flex: 1; overflow-y: auto; padding: 20px 24px; }
  .receipt-bt-error {
    margin: 0 16px;
    padding: 8px 12px;
    border-radius: 8px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #dc2626;
    font-size: 0.75rem;
  }
  .receipt-actions {
    display: flex;
    gap: 10px;
    padding: 14px 16px 18px;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }

  /* Modifier modal */
  .modifier-modal {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 600px;
    max-height: 88vh;
    overflow: hidden;
    border-radius: 24px 24px 0 0;
    background: var(--white);
  }
  @media (min-width: 768px) { .modifier-modal { border-radius: 24px; max-height: 85vh; } }

  .modifier-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px 20px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .modifier-thumb {
    width: 60px;
    height: 60px;
    flex-shrink: 0;
    border-radius: 14px;
    overflow: hidden;
    background: linear-gradient(135deg, var(--light-brown), #d4b896);
  }
  .modifier-info { flex: 1; min-width: 0; }
  .modifier-name { font-size: 1.35rem; font-weight: 700; color: var(--espresso); margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .modifier-body { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 20px; }
  .group-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 10px;
  }
  .group-required {
    background: var(--light-brown);
    color: var(--warm-brown);
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.65rem;
    text-transform: none;
    letter-spacing: 0;
  }
  .choice-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
  .choice-btn {
    padding: 9px 16px;
    border-radius: 10px;
    border: 1.5px solid var(--border);
    background: var(--cream);
    color: var(--dark);
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
  }
  .choice-btn:hover { border-color: var(--warm-brown); }
  .choice-btn--active { background: var(--primary); border-color: var(--primary); color: white; }
  .choice-price { opacity: 0.6; font-weight: 600; }

  .modifier-footer {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 20px 20px;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }
  .modifier-add-btn { flex: 1; }

  /* ─── Discount row ─── */
  .discount-row {
    margin-bottom: 10px;
  }

  .discount-trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: 999px;
    border: 1.5px dashed var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s, background 0.15s;
    width: 100%;
    justify-content: center;
  }
  .discount-trigger:hover:not(:disabled) {
    border-color: var(--warm-brown);
    color: var(--espresso);
    background: var(--cream);
  }
  .discount-trigger:disabled { opacity: 0.4; cursor: not-allowed; }
  .discount-trigger--loading { opacity: 0.65; }

  .discount-chip {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 7px 10px 7px 12px;
    border-radius: 999px;
    background: #dcfce7;
    border: 1.5px solid #86efac;
    color: #15803d;
    font-size: 0.8rem;
    font-weight: 700;
    width: 100%;
  }
  .discount-chip-label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .discount-chip-savings {
    font-weight: 600;
    opacity: 0.8;
  }
  .discount-chip-clear {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: none;
    background: rgba(21,128,61,0.15);
    color: #15803d;
    font-size: 0.9rem;
    font-weight: 700;
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: background 0.12s;
    line-height: 1;
  }
  .discount-chip-clear:hover { background: rgba(21,128,61,0.3); }

  .discount-err-row {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .discount-err-msg {
    font-size: 0.72rem;
    font-weight: 700;
    color: #b91c1c;
    padding: 0 4px;
  }

  /* ─── Discount modal ─── */
  .discount-modal-shell {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 560px;
    max-height: 80vh;
    overflow: hidden;
    border-radius: 24px 24px 0 0;
    background: var(--white);
  }
  @media (min-width: 768px) { .discount-modal-shell { border-radius: 24px; max-height: 82vh; } }

  .discount-section-label {
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .discount-option-card {
    display: block;
    width: 100%;
    padding: 12px 14px;
    border-radius: 14px;
    border: 1.5px solid var(--border);
    background: var(--white);
    text-align: left;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  .discount-option-card:hover:not(:disabled) {
    border-color: var(--warm-brown);
    background: var(--cream);
  }
  .discount-option-card--active {
    border-color: #22c55e;
    background: #f0fdf4;
  }
  .discount-option-card:disabled { opacity: 0.5; cursor: not-allowed; }

  .discount-auto-card {
    padding: 12px 14px;
    border-radius: 14px;
    border: 1.5px solid var(--border);
    background: var(--cream);
  }

  .discount-option-name {
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--dark);
    margin-bottom: 2px;
  }
  .discount-option-desc {
    font-size: 0.72rem;
    color: var(--text-muted);
  }
  .discount-option-code-badge {
    flex-shrink: 0;
    padding: 3px 10px;
    border-radius: 8px;
    background: var(--light-brown);
    color: var(--espresso);
    font-size: 0.7rem;
    font-weight: 800;
    font-family: monospace;
    letter-spacing: 0.05em;
  }
  .discount-auto-badge {
    flex-shrink: 0;
    padding: 3px 10px;
    border-radius: 8px;
    background: #e0f2fe;
    color: #0369a1;
    font-size: 0.65rem;
    font-weight: 800;
  }

  .summary-row--discount { color: #16a34a; font-weight: 700; }

  /* ─── Discount display ─── */

  /* ─── Utilities ─── */
  .no-scrollbar { scrollbar-width: none; }
  .no-scrollbar::-webkit-scrollbar { display: none; }

  /* ─── Print ─── */
  @media print {
    :global(*) { visibility: hidden; }
    :global(.receipt-modal), :global(.receipt-modal *) { visibility: visible; }
    :global(.receipt-modal) {
      position: fixed; inset: 0; width: 100%; max-height: none;
      border-radius: 0; box-shadow: none; overflow: visible; font-size: 11px;
    }
    :global(.receipt-modal .receipt-body) { overflow: visible; }
  }

  /* ─── Online platform form ─── */
  .online-form { display: flex; flex-direction: column; gap: 8px; padding: 0 0 10px; }
  .online-channels { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
  .online-ch {
    display: grid;
    place-items: center;
    height: var(--om-tap);
    padding: 0 6px;
    border: 2px solid var(--om-border);
    border-radius: 10px;
    background: var(--om-surface);
    cursor: pointer;
  }
  .online-ch--active { border-color: var(--om-brand); background: var(--om-brand-tint); }
  .online-ch img { max-width: 72px; max-height: 24px; width: auto; height: auto; }
  .online-lbl { display: block; margin-bottom: 2px; font-size: 12px; font-weight: 500; color: var(--om-text-secondary); }
  .online-warn { padding: 8px 10px; border-radius: 10px; background: var(--om-warning-tint); color: var(--om-warning); font-size: 12px; }
  .online-tax { font-size: 12px; color: var(--om-text-secondary); }

  /* ─── open bill ─── */
  .ob-open { position: relative; width: var(--om-tap, 44px); height: var(--om-tap, 44px); flex-shrink: 0; display: grid; place-items: center; border: 1px solid var(--border); border-radius: 10px; background: var(--white); color: var(--espresso); }
  .ob-open:hover { border-color: var(--om-ink); }
  .ob-open-badge { position: absolute; top: -7px; right: -7px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: #8e1a14; color: #fff; font-size: 12px; font-weight: 700; display: grid; place-items: center; }
  .footer-actions { display: flex; gap: 8px; margin-top: 6px; }
  .footer-actions .charge-btn { flex: 1; min-width: 0; width: auto; }
  .ob-save { flex: none; height: 50px; padding: 0 14px; border-radius: 12px; border: 1px solid var(--om-brand); background: var(--white); color: var(--om-brand); font-size: 16px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
  .ob-save:disabled { opacity: 0.4; cursor: not-allowed; }
  .ob-modal { display: flex; flex-direction: column; width: 100%; max-width: 540px; max-height: 88vh; background: var(--white); border-radius: 22px 22px 0 0; overflow: hidden; box-shadow: 0 20px 60px rgba(16, 20, 15, 0.25); }
  @media (min-width: 768px) { .ob-modal { border-radius: 22px; } }
  .ob-head { display: flex; align-items: flex-start; gap: 12px; padding: 18px 20px 12px; border-bottom: 1px solid #f0eee9; }
  .ob-search { display: flex; align-items: center; gap: 8px; margin: 12px 20px 0; height: var(--om-tap, 44px); padding: 0 12px; border: 1px solid #d7d5ce; border-radius: 10px; color: var(--text-muted); }
  .ob-search input { flex: 1; min-width: 0; border: none; outline: none; background: transparent; font-size: 16px; color: var(--espresso); }
  .ob-list { flex: 1; overflow: auto; padding: 4px 20px calc(16px + env(safe-area-inset-bottom)); }
  .ob-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f0eee9; }
  .ob-add { height: var(--om-tap, 44px); padding: 0 14px; border-radius: 10px; border: 1px solid var(--om-brand); background: var(--white); color: var(--om-brand); font-weight: 600; flex-shrink: 0; }
  .line-void { flex-shrink: 0; height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid #fecaca; background: #fef2f2; color: var(--om-danger); font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; }
  .line-void:hover:not(:disabled) { background: #fee2e2; }
  .line-void:disabled { opacity: 0.4; cursor: not-allowed; }
  .void-modal { display: flex; flex-direction: column; gap: 16px; width: 100%; max-width: 440px; padding: 20px; background: var(--white); border-radius: 22px 22px 0 0; box-shadow: 0 20px 60px rgba(16, 20, 15, 0.25); }
  @media (min-width: 768px) { .void-modal { border-radius: 22px; } }
  .cart-line--locked { opacity: 0.65; gap: 8px; }
  .ob-pay { height: var(--om-tap, 44px); padding: 0 16px; border-radius: 10px; background: var(--om-brand); color: #fff; font-weight: 600; flex-shrink: 0; }
  .ob-empty { padding: 36px 12px; display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center; color: var(--text-muted); font-size: 12px; }
  .ob-empty strong { color: var(--espresso); font-size: 14px; }
  .pos-toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 90; max-width: calc(100vw - 40px); padding: 12px 18px; border-radius: 12px; background: var(--om-ink); color: #fff; box-shadow: 0 10px 30px rgba(16, 20, 15, 0.25); }

  /* ─── new-ui layout overrides ─── */
  .img-placeholder { position: absolute; inset: 0; display: grid; place-items: center; background: var(--white); color: var(--om-text-secondary); opacity: 0.6; }
  .cart-panel { width: 360px; }
  .cart-header { align-items: center; justify-content: flex-start; gap: 8px; padding: 12px 16px 10px; border-bottom: none; }
  .cart-title { font-size: 16px; font-weight: 600; flex: 1; min-width: 0; }
  .cart-badge { background: var(--om-ink); color: #7ed76a; }
  .cart-types { padding: 0 16px 8px; }
  .type-seg { display: flex; gap: 0; padding: 4px; background: #f1f0ec; border-radius: 11px; }
  .type-btn { flex: 1; min-width: 0; height: var(--om-tap, 44px); border-radius: 8px; font-size: 14px; font-weight: 600; color: var(--text-muted); }
  .type-btn--active { background: var(--white); color: var(--espresso); box-shadow: 0 1px 2px rgba(16, 20, 15, 0.12); }
  .cart-lines { padding: 0 16px; }
  .cart-line { padding: 8px 0; border-bottom: 1px solid #f0eee9; align-items: center; }
  .cart-line-body { cursor: pointer; min-height: 44px; display: flex; flex-direction: column; justify-content: center; }
  .cart-line-name { font-size: 14px; font-weight: 600; }
  .cart-line-price { font-size: 14px; font-weight: 600; color: var(--espresso); margin-top: 2px; }
  .qty-stepper { gap: 0; border: 1px solid var(--border); border-radius: 10px; }
  .cart-footer { background: var(--cream); border-top: 1px solid var(--border); padding: 10px 16px calc(12px + env(safe-area-inset-bottom)); }
  .summary-total { display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px; padding-top: 6px; border-top: 1px dashed #dad8d1; font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .charge-btn { height: 50px; padding: 0 16px; border-radius: 12px; font-size: 16px; font-weight: 600; letter-spacing: 0; background: var(--om-brand); }
  .charge-btn:hover:not(:disabled) { background: var(--om-brand); filter: brightness(0.92); }

  .item-card { border-radius: 14px; border: 1.5px solid var(--border); background: var(--white); text-align: left; }
  .item-img-wrap { padding-top: 75%; background: #eef0ea; }
  .qty-badge { position: absolute; top: 10px; right: 10px; left: auto; bottom: auto; min-width: 26px; height: 26px; padding: 0 7px; border-radius: 13px; background: var(--om-ink); color: #7ed76a; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
  .oos-badge { position: absolute; top: 10px; left: 10px; padding: 3px 8px; border-radius: 6px; background: #fce9e6; color: #8e1a14; font-size: 12px; font-weight: 600; }
  .item-info { padding: 11px 13px 13px; gap: 4px; }
  .item-name { font-size: 16px; font-weight: 600; line-height: 1.3; }
  .item-meta { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
  .item-price { font-size: 12px; font-weight: 400; color: #3b3f38; font-variant-numeric: tabular-nums; }
  .item-opt { font-size: 12px; color: var(--om-brand); }
  .item-stock { font-size: 12px; color: var(--text-muted); }
  .list-row { min-height: 56px; border-radius: 12px; padding: 10px 14px; gap: 12px; align-items: center; }
  .list-row--selected { border-color: var(--om-brand); background: var(--white); }
  .list-name { font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
  .list-tags { margin: 0; align-items: center; gap: 8px; }
  .list-price { font-size: 16px; font-weight: 600; color: var(--espresso); white-space: nowrap; font-variant-numeric: tabular-nums; }
  .qty-pill { background: var(--om-ink); color: #7ed76a; }

  .modifier-modal { max-width: 440px; }
  .modifier-header { padding: 18px 20px; gap: 14px; align-items: center; border-bottom: 1px solid #f0eee9; }
  .modifier-thumb { position: relative; overflow: hidden; width: 56px; height: 56px; border-radius: 12px; }
  .modifier-name { font-size: 16px; font-weight: 600; }
  .modifier-body { padding: 16px 20px; gap: 16px; }
  .group-label { font-size: 12px; font-weight: 400; color: var(--text-muted); text-transform: none; letter-spacing: 0; }
  .choice-btn { height: var(--om-tap, 44px); padding: 0 14px; border-radius: 10px; border: 2px solid var(--border); background: var(--white); color: var(--espresso); font-weight: 500; display: inline-flex; align-items: center; gap: 6px; }
  .choice-btn--active { background: var(--om-brand-tint); border-color: var(--om-brand); color: var(--espresso); }
  .note-field { margin-top: 8px; border-color: var(--om-brand); }
  .note-hint { display: block; margin-top: 4px; font-size: 12px; color: var(--text-muted); }
  .modifier-footer { padding: 14px 20px 20px; }

  .pay-modal { display: grid; grid-template-columns: 1fr; width: 100%; max-width: 800px; max-height: 92vh; overflow: auto; background: var(--white); border-radius: 22px 22px 0 0; box-shadow: 0 20px 60px rgba(16, 20, 15, 0.25); }
  @media (min-width: 768px) { .pay-modal { grid-template-columns: 300px 1fr; border-radius: 22px; } }
  .pay-sum { background: var(--om-ink); color: #eaf3e6; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
  .pay-sum-head { font-size: 12px; color: #7ed76a; }
  .pay-sum-lbl { font-size: 12px; color: #a9b3a5; }
  .pay-sum-total { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
  .pay-sum-save { font-size: 12px; color: #7ed76a; }
  .pay-sum-items { display: flex; flex-direction: column; gap: 9px; font-size: 12px; color: #c7cfc3; border-top: 1px solid #2a3027; padding-top: 14px; flex: 1; max-height: 260px; overflow: auto; }
  .pay-sum-line { display: flex; gap: 8px; }
  .pay-sum-qty { color: #7ed76a; font-variant-numeric: tabular-nums; }
  .pay-sum-sub { font-size: 12px; color: #a9b3a5; }
  .pay-main { padding: 24px; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .pay-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 8px; }
  .pay-tile { height: 70px; border-radius: 12px; border: 2px solid var(--border); background: var(--white); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; }
  .pay-tile--active { border-color: var(--om-brand); background: var(--om-brand-tint); }
  .pay-tile-icon { height: 24px; display: flex; align-items: center; justify-content: center; color: var(--om-brand); }
  .pay-tile-icon img { height: 20px; width: 52px; object-fit: contain; }
  .pay-tile-lbl { font-size: 12px; font-weight: 500; color: #3b3f38; max-width: 100%; padding: 0 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pay-panel { flex: 1; min-height: 180px; border: 1px solid var(--border); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 12px; background: var(--cream); }
  .pay-panel-lbl { display: block; margin-bottom: 6px; font-size: 12px; color: var(--text-muted); }
  .pay-cash-input { display: flex; align-items: center; gap: 8px; height: 48px; padding: 0 14px; border: 1.5px solid var(--om-ink); border-radius: 11px; background: var(--white); color: var(--text-muted); }
  .pay-cash-input input { flex: 1; min-width: 0; border: none; outline: none; background: transparent; font-size: 20px; font-weight: 700; color: var(--espresso); font-variant-numeric: tabular-nums; }
  .pay-quick { height: var(--om-tap, 44px); padding: 0 12px; border-radius: 9px; border: 1px solid var(--border); background: var(--white); font-size: 12px; font-variant-numeric: tabular-nums; }
  .pay-change { display: flex; justify-content: space-between; align-items: baseline; padding-top: 10px; border-top: 1px dashed #dad8d1; color: var(--text-muted); }
  .pay-change span:last-child { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .pay-hint { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; color: var(--text-muted); font-size: 12px; }
  .pay-hint .ms { color: var(--om-brand); }
  .pay-hint strong { color: var(--espresso); font-size: 14px; }
</style>
