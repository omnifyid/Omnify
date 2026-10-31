<script lang="ts">
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

  type CartLine = {
    lineId: string;
    item: Item;
    quantity: number;
    optionChoiceIds: string[];
    addonChoiceIds: string[];
  };

  const payments: Array<{ value: PaymentMethod; icon: string }> = [
    { value: 'CASH', icon: '💵' },
    { value: 'CARD', icon: '💳' },
    { value: 'QRIS', icon: '▦' },
    { value: 'TRANSFER', icon: '↗' }
  ];

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
  let discountCode = $state('');
  let loading = $state(false);
  let checkingOut = $state(false);
  let error = $state('');
  let receiptOrder = $state<Order | null>(null);
  let modifierItem = $state<Item | null>(null);
  let modifierQty = $state(1);
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

  function addonTotal(item: Item, ids: string[]) {
    return (item.addon_groups ?? []).reduce(
      (sum, group) => sum + getGroupChoices(group).reduce((gs, c) => gs + (ids.includes(c.id) ? mk(getChoicePrice(c)) : 0), 0),
      0
    );
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

  let cashAmount = $state('0');
  let cashModalOpen = $state(false);
  let itemDiscountTotal = $derived(receiptOrder ? (receiptOrder.items ?? []).reduce((sum, i) => sum + (i.item_discount_amount ?? 0), 0) : 0);
  let receiptCashPaid = $state(0);
  let cashPaid = $derived(parseInt(cashAmount) || 0);
  let change = $derived(cashPaid - totalDue);

  let discounts = $state<Discount[]>([]);
  let discountModalOpen = $state(false);
  let manualCode = $state('');
  let appliedDiscountLabel = $state('');
  let autoPromoTimer: ReturnType<typeof setTimeout> | null = null;

  let autoDiscounts = $derived(discounts.filter((d) => d.is_automatic && d.is_active));
  let codeDiscounts = $derived(discounts.filter((d) => !d.is_automatic && d.is_active && !!d.code));

  function cashAppend(digits: string) {
    cashAmount = cashAmount === '0' ? digits : cashAmount + digits;
  }
  function cashBackspace() {
    cashAmount = cashAmount.length <= 1 ? '0' : cashAmount.slice(0, -1);
  }

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
    } else if (paymentMethod === 'CASH') {
      cashAmount = '0';
      mobileCartOpen = false;
      cashModalOpen = true;
    } else {
      void checkout();
    }
  }
  let totalItems = $derived(cart.reduce((sum, line) => sum + line.quantity, 0));
  let activeCategoryName = $derived(activeCategoryId === 'all' ? language.t('allMenu') : categories.find((category) => category.id === activeCategoryId)?.name ?? language.t('menu'));
  let modifierUnitPrice = $derived(modifierItem ? itemPrice(modifierItem) + addonTotal(modifierItem, selectedAddonChoiceIds) : 0);
  let canAddModifierItem = $derived(
    modifierItem
      ? (modifierItem.option_groups ?? []).every((group) => !group.required || Boolean(selectedOptionChoiceIds[group.id]))
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
    } catch (err) { error = err instanceof Error ? err.message : language.t('error'); }
    finally { loading = false; }
  }

  function sameChoices(left: string[], right: string[]) {
    return left.length === right.length && [...left].sort().every((value, index) => value === [...right].sort()[index]);
  }

  function lineFor(item: Item, optionChoiceIds: string[] = [], addonChoiceIds: string[] = []) {
    return cart.find(
      (line) =>
        line.item.id === item.id &&
        sameChoices(line.optionChoiceIds, optionChoiceIds) &&
        sameChoices(line.addonChoiceIds, addonChoiceIds)
    );
  }

  function itemQuantity(item: Item) {
    return cart.reduce((sum, line) => sum + (line.item.id === item.id ? line.quantity : 0), 0);
  }

  function getLineUnitPrice(line: CartLine) {
    return itemPrice(line.item) + addonTotal(line.item, line.addonChoiceIds);
  }

  function addItem(item: Item) {
    if (hasItemModifiers(item)) {
      openModifierModal(item);
      return;
    }
    addConfiguredItem(item, 1, [], []);
  }

  function addConfiguredItem(item: Item, quantity: number, optionChoiceIds: string[], addonChoiceIds: string[]) {
    if (item.stock !== null && item.stock !== undefined) {
      const remaining = item.stock - itemQuantity(item);
      if (remaining <= 0) return;
      quantity = Math.min(quantity, remaining);
    }
    const existing = lineFor(item, optionChoiceIds, addonChoiceIds);
    if (existing) existing.quantity += quantity;
    else cart.push({ lineId: Math.random().toString(36).slice(2), item, quantity, optionChoiceIds, addonChoiceIds });
    schedulePromoCheck();
  }

  function openModifierModal(item: Item) {
    modifierItem = item;
    modifierQty = 1;
    selectedOptionChoiceIds = {};
    selectedAddonChoiceIds = [];
  }

  function closeModifierModal() {
    modifierItem = null;
  }

  function toggleAddon(choiceId: string) {
    selectedAddonChoiceIds = selectedAddonChoiceIds.includes(choiceId)
      ? selectedAddonChoiceIds.filter((id) => id !== choiceId)
      : [...selectedAddonChoiceIds, choiceId];
  }

  function addModifierItemToCart() {
    if (!modifierItem || !canAddModifierItem) return;
    addConfiguredItem(modifierItem, modifierQty, Object.values(selectedOptionChoiceIds), selectedAddonChoiceIds);
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

  function snapshotNames(snapshot: unknown[] | null | undefined) {
    if (!snapshot?.length) return '';
    return snapshot
      .map((entry) => {
        if (typeof entry === 'string') return entry;
        if (entry && typeof entry === 'object') {
          const record = entry as Record<string, unknown>;
          return record.name ?? record.label ?? record.choice_name ?? record.item_name;
        }
        return '';
      })
      .filter(Boolean)
      .join(', ');
  }

  function cartItemsPayload() {
    return cart.map((line) => ({
      item_id: line.item.id,
      quantity: line.quantity,
      selected_option_choice_ids: line.optionChoiceIds,
      selected_addon_choice_ids: line.addonChoiceIds
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
    if (onlineMode) { promoResult = null; return; }
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

  async function applyManualCode() {
    if (!manualCode.trim() || cart.length === 0) return;
    discountCode = manualCode.trim();
    appliedDiscountLabel = manualCode.trim();
    discountModalOpen = false;
    manualCode = '';
    await checkPromo();
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
          addonChoiceIds: line.addonChoiceIds
        })),
        orderType: posDineInEnabled && !online ? orderType : null,
        tableNumber: posTableEnabled && !online ? posTableNumber : null,
        customerName: online ? onlineCustomer.trim() : posCustomerNameEnabled && customerName ? customerName : null,
      }));
      cart = [];
      discountCode = '';
      appliedDiscountLabel = '';
      promoResult = null;
      resetOrderMeta();
      resetOnlineForm();
      receiptCashPaid = paymentMethod === 'CASH' ? cashPaid : 0;
      cashAmount = '0';
      cashModalOpen = false;
      receiptOrder = order;
      mobileCartOpen = false;
      await load();
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
      const apiBase = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').replace('/api/v1', '');
      const rawLogo = store?.show_logo !== false ? (store?.logo_url ?? null) : null;
      const logoUrl = rawLogo
        ? (rawLogo.startsWith('http') ? rawLogo : apiBase + rawLogo)
        : null;
      const bytes = await buildReceiptBytes(receiptOrder, store?.name ?? 'Kasir', receiptCashPaid, {
        header: store?.receipt_header,
        footer: store?.receipt_footer,
        logoUrl,
      });
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

  function resetOrderMeta() {
    orderType = null;
    posTableNumber = null;
    customerName = '';
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

<!-- Cash payment modal -->
{#if cashModalOpen}
  <div
    class="sheet-backdrop cash-backdrop"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) cashModalOpen = false; }}
  >
    <section class="cash-modal" role="dialog" aria-modal="true">
      <div class="cash-modal-header">
        <button class="icon-btn" onclick={() => cashModalOpen = false}><span class="ms !text-[18px]" aria-hidden="true">close</span></button>
        <div style="text-align: right;">
          <div class="cash-modal-label">{language.t('payment')} CASH</div>
          <div class="cash-modal-total">{formatRupiah(totalDue)}</div>
          {#if promoResult?.valid && promoResult.discount_amount > 0}
            <div class="cash-modal-subtotal-note">{language.t('discountSavings')} {formatRupiah(promoResult.discount_amount)}</div>
          {/if}
        </div>
      </div>

      <div class="cash-display">
        <button class="calc-back-btn" onclick={() => cashAmount = '0'} aria-label={language.t('clear')}>
          <span class="ms !text-[16px]" aria-hidden="true">undo</span>
        </button>
        <div style="text-align: right;">
          <div class="cash-lbl">{language.t('amountPaid')}</div>
          <div class="cash-val">{formatRupiah(cashPaid)}</div>
        </div>
      </div>

      <div class="calc-grid">
        {#each [1,2,3,4,5,6,7,8,9] as d}
          <button class="calc-key" onclick={() => cashAppend(String(d))}>{d}</button>
        {/each}
        <button class="calc-key" onclick={() => cashAppend('0')}>0</button>
        <button class="calc-key" onclick={() => cashAppend('000')}>000</button>
        <button class="calc-key calc-key--clear" onclick={cashBackspace} aria-label="backspace">⌫</button>
      </div>

      {#if cashPaid >= totalDue && cashPaid > 0}
        <div class="cash-change cash-change--ok">
          <span>{language.t('change')}</span>
          <span>{formatRupiah(change)}</span>
        </div>
      {:else if cashPaid > 0}
        <div class="cash-change cash-change--short">
          <span>{language.t('short')}</span>
          <span>{formatRupiah(totalDue - cashPaid)}</span>
        </div>
      {:else}
        <div class="cash-change cash-change--hint">
          <span>{language.t('enterCashAmount')}</span>
        </div>
      {/if}

      <div class="cash-modal-footer">
        <button
          class="charge-btn cash-confirm-btn"
          disabled={cashPaid < totalDue || checkingOut}
          onclick={checkout}
        >
          {checkingOut ? language.t('processing') : language.t('confirm')}
        </button>
      </div>
    </section>
  </div>
{/if}

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
  <div class="flex flex-wrap gap-1.5">
    {#if posDineInEnabled}
      <button class="meta-type-btn {!onlineMode && orderType === 'DINE_IN' ? 'meta-type-btn--active' : ''}" onclick={() => pickType('DINE_IN')}>{language.t('dineIn')}</button>
      <button class="meta-type-btn {!onlineMode && orderType === 'TAKE_AWAY' ? 'meta-type-btn--active' : ''}" onclick={() => pickType('TAKE_AWAY')}>{language.t('takeAway')}</button>
    {/if}
    {#if hasOnline}
      <button class="meta-type-btn {onlineMode ? 'meta-type-btn--active' : ''}" onclick={() => setOnline(!onlineMode)}>{language.t('online')}</button>
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
                <img
                  src={mediaUrl(item.image_url) ?? '/images/product-placeholder.svg'}
                  alt={item.name}
                  class="item-img {item.image_url ? 'object-cover' : 'object-contain p-6'}"
                />
              {/if}
              {#if oos}
                <div class="item-oos-overlay">
                  <span class="oos-badge">{language.t('stockOut')}</span>
                </div>
              {:else}
                {#if qty}
                  <span class="qty-badge">{qty}</span>
                {/if}
                {#if tracked}
                  <span class="stock-badge">{language.t('stockRemaining')} {item.stock}</span>
                {/if}
              {/if}
              {#if hasItemModifiers(item)}
                <span class="options-badge">{language.t('options')}</span>
              {/if}
            </div>
            <div class="item-info">
              <div class="item-name">{item.name}</div>
              <div class="item-price">{formatRupiah(itemPrice(item))}</div>
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
            <div class="list-thumb">
              {#if item.icon}
                <div class="list-thumb-emoji">{item.icon}</div>
              {:else}
                <img
                  src={mediaUrl(item.image_url) ?? '/images/product-placeholder.svg'}
                  alt={item.name}
                  class="list-thumb-img {item.image_url ? 'object-cover' : 'object-contain p-2'}"
                />
              {/if}
            </div>
            <div class="list-info">
              <div class="list-name">{item.name}</div>
              <div class="list-tags">
                {#if hasItemModifiers(item)}<span class="tag tag--opt">{language.t('options')}</span>{/if}
                {#if oos}<span class="tag tag--oos">{language.t('stockOut')}</span>{/if}
                {#if tracked && !oos}<span class="tag tag--stock">{language.t('stockRemaining')} {item.stock}</span>{/if}
              </div>
              <div class="list-price">{formatRupiah(itemPrice(item))}</div>
            </div>
            {#if qty}
              <span class="qty-pill">{qty}</span>
            {/if}
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
    <div class="cart-header">
      <div class="flex min-w-0 flex-1 flex-col gap-1.5">
        {#if posDineInEnabled || hasOnline}{@render typeTabs()}{/if}
        {#if posTableEnabled && !onlineMode}
          <div class="flex items-center gap-2">
            <button
              class="meta-table-btn {posTableNumber ? 'meta-table-btn--selected' : ''}"
              onclick={() => tableModalOpen = true}
            >{posTableNumber ? `${language.t('table')} ${posTableNumber}` : language.t('selectTable')}</button>
            {#if posTableNumber}
              <button class="meta-clear" onclick={() => posTableNumber = null}>×</button>
            {/if}
          </div>
        {/if}
        {#if !posDineInEnabled && !posTableEnabled && !hasOnline}
          <h2 class="display-font cart-title">{language.t('order')}</h2>
        {/if}
      </div>
      {#if totalItems > 0}
        <span class="cart-badge">{totalItems}</span>
      {/if}
    </div>

    <div class="cart-lines">
      {#each cart as line}
        {@const atLimit = line.item.stock !== null && line.item.stock !== undefined && line.quantity >= line.item.stock}
        <div class="cart-line">
          <div class="cart-line-body">
            <div class="cart-line-name">{line.item.name}</div>
            {#if choiceNames(line)}<div class="cart-line-mods">{choiceNames(line)}</div>{/if}
            {#if atLimit}<div class="cart-line-limit">{language.t('maxStockReached')}</div>{/if}
            <div class="cart-line-price">{formatRupiah(getLineUnitPrice(line) * line.quantity)}</div>
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
    </div>

    <div class="cart-footer">
      {@render onlineForm()}
      {#if posCustomerNameEnabled && !onlineMode}
        <div class="order-meta">
          <div class="meta-row">
            <input
              class="field text-sm"
              placeholder={language.t('customerNamePlaceholder')}
              bind:value={customerName}
            />
          </div>
        </div>
      {/if}

      {#if !onlineMode}

      <!-- Discount row -->
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
            <button class="discount-trigger" onclick={() => discountModalOpen = true}>
              <span class="ms !text-[13px]" aria-hidden="true">sell</span>
              <span>{language.t('addDiscount')}</span>
            </button>
            <span class="discount-err-msg">{promoResult.message}</span>
          </div>
        {:else}
          <button
            class="discount-trigger {promoLoading ? 'discount-trigger--loading' : ''}"
            onclick={() => discountModalOpen = true}
          >
            <span class="ms !text-[13px]" aria-hidden="true">sell</span>
            <span>{promoLoading ? language.t('checking') : language.t('addDiscount')}</span>
          </button>
        {/if}
      </div>

      <div class="pay-grid">
        {#each payments as p}
          <button
            class="pay-btn {paymentMethod === p.value ? 'pay-btn--active' : ''}"
            onclick={() => paymentMethod = p.value}
          >
            <span class="pay-icon">{p.icon}</span>
            <span class="pay-lbl">{paymentLabel(p.value)}</span>
          </button>
        {/each}
      </div>

      {/if}

      <div class="order-summary">
        <div class="summary-row">
          <span>{language.t('subtotal')}</span>
          <span>{formatRupiah(subtotal)}</span>
        </div>
        {#if promoResult?.valid && promoResult.discount_amount > 0}
          <div class="summary-row summary-row--discount">
            <span>{language.t('discounts')} {appliedDiscountLabel ? `· ${appliedDiscountLabel}` : ''}</span>
            <span>−{formatRupiah(promoResult.discount_amount)}</span>
          </div>
        {/if}
        {#if serviceFee > 0}
          <div class="summary-row"><span>{language.t('serviceLabel')}</span><span>{formatRupiah(serviceFee)}</span></div>
        {/if}
        {#if pb1Fee > 0}
          <div class="summary-row"><span>{language.t('pb1Label')}</span><span>{formatRupiah(pb1Fee)}</span></div>
        {/if}
      </div>

      <button
        class="charge-btn"
        disabled={cart.length === 0 || checkingOut || (onlineMode && !onlineValid)}
        onclick={handleCharge}
      >
        {checkingOut ? language.t('processing') : `${language.t(onlineMode ? 'onlineSend' : 'charge')} ${formatRupiah(totalDue)}`}
      </button>
    </div>
  </aside>
</div>

<!-- Mobile cart sheet -->
{#if mobileCartOpen}
  <div
    class="sheet-backdrop"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) mobileCartOpen = false; }}
  >
    <div class="cart-sheet" role="dialog" aria-modal="true" aria-label="Cart" tabindex="-1">
      <div class="cart-header sheet-header">
        <div class="flex min-w-0 flex-1 flex-col gap-1.5">
          {#if posDineInEnabled || hasOnline}{@render typeTabs()}{/if}
          {#if posTableEnabled && !onlineMode}
            <div class="flex items-center gap-2">
              <button
                class="meta-table-btn {posTableNumber ? 'meta-table-btn--selected' : ''}"
                onclick={() => tableModalOpen = true}
              >{posTableNumber ? `${language.t('table')} ${posTableNumber}` : language.t('selectTable')}</button>
              {#if posTableNumber}
                <button class="meta-clear" onclick={() => posTableNumber = null}>×</button>
              {/if}
            </div>
          {/if}
          {#if !posDineInEnabled && !posTableEnabled && !hasOnline}
            <h2 class="display-font cart-title">{language.t('order')}</h2>
          {/if}
        </div>
        <div class="flex items-center gap-3">
          {#if totalItems > 0}<span class="cart-badge">{totalItems}</span>{/if}
          <button class="icon-btn" onclick={() => mobileCartOpen = false}><span class="ms !text-[18px]" aria-hidden="true">close</span></button>
        </div>
      </div>

      <div class="cart-lines">
        {#each cart as line}
          {@const atLimit = line.item.stock !== null && line.item.stock !== undefined && line.quantity >= line.item.stock}
          <div class="cart-line">
            <div class="cart-line-body">
              <div class="cart-line-name">{line.item.name}</div>
              {#if choiceNames(line)}<div class="cart-line-mods">{choiceNames(line)}</div>{/if}
              {#if atLimit}<div class="cart-line-limit">{language.t('maxStockReached')}</div>{/if}
              <div class="cart-line-price">{formatRupiah(getLineUnitPrice(line) * line.quantity)}</div>
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
      </div>

      <div class="cart-footer">
        {@render onlineForm()}
      {#if posCustomerNameEnabled && !onlineMode}
          <div class="order-meta">
            <div class="meta-row">
              <input
                class="field text-sm"
                placeholder={language.t('customerNamePlaceholder')}
                bind:value={customerName}
              />
            </div>
          </div>
        {/if}

        <!-- Discount row (mobile) -->
        {#if !onlineMode}
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
              <button class="discount-trigger" onclick={() => discountModalOpen = true}>
                <span class="ms !text-[13px]" aria-hidden="true">sell</span>
                <span>{language.t('addDiscount')}</span>
              </button>
              <span class="discount-err-msg">{promoResult.message}</span>
            </div>
          {:else}
            <button
              class="discount-trigger {promoLoading ? 'discount-trigger--loading' : ''}"
              onclick={() => discountModalOpen = true}
            >
              <span class="ms !text-[13px]" aria-hidden="true">sell</span>
              <span>{promoLoading ? language.t('checking') : language.t('addDiscount')}</span>
            </button>
          {/if}
        </div>
        <div class="pay-grid">
          {#each payments as p}
            <button
              class="pay-btn {paymentMethod === p.value ? 'pay-btn--active' : ''}"
              onclick={() => paymentMethod = p.value}
            >
              <span class="pay-icon">{p.icon}</span>
              <span class="pay-lbl">{paymentLabel(p.value)}</span>
            </button>
          {/each}
        </div>
        {/if}
        <div class="order-summary">
          <div class="summary-row"><span>{language.t('subtotal')}</span><span>{formatRupiah(subtotal)}</span></div>
          {#if promoResult?.valid && promoResult.discount_amount > 0}
            <div class="summary-row summary-row--discount">
              <span>{language.t('discounts')} {appliedDiscountLabel ? `· ${appliedDiscountLabel}` : ''}</span>
              <span>−{formatRupiah(promoResult.discount_amount)}</span>
            </div>
          {/if}
          {#if serviceFee > 0}
            <div class="summary-row"><span>{language.t('serviceLabel')}</span><span>{formatRupiah(serviceFee)}</span></div>
          {/if}
          {#if pb1Fee > 0}
            <div class="summary-row"><span>{language.t('pb1Label')}</span><span>{formatRupiah(pb1Fee)}</span></div>
          {/if}
        </div>
        <button class="charge-btn" disabled={cart.length === 0 || checkingOut || (onlineMode && !onlineValid)} onclick={handleCharge}>
          {checkingOut ? language.t('processing') : `${language.t(onlineMode ? 'onlineSend' : 'charge')} ${formatRupiah(totalDue)}`}
        </button>
      </div>
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
      <div class="receipt-head">
        {#if session.selectedStore?.show_logo !== false && session.selectedStore?.logo_url}
          <img src={session.selectedStore.logo_url} alt="logo" class="receipt-logo" />
        {/if}
        <div class="receipt-store">{session.selectedStore?.name ?? 'Kasir'}</div>
        <div class="receipt-date">{formatDateTime(receiptOrder.created_at)}</div>
        <div class="receipt-num">#{receiptOrder.order_number ?? receiptOrder.id}</div>
        {#if session.selectedStore?.receipt_header?.trim()}
          <div class="receipt-header-text">{session.selectedStore.receipt_header}</div>
        {/if}
      </div>

      <div class="receipt-body">
        <div class="receipt-items">
          {#each receiptOrder.items ?? [] as item}
            {@const mods = [snapshotNames(item.options_snapshot), snapshotNames(item.addons_snapshot)].filter(Boolean).join(', ')}
            <div class="receipt-item">
              <div class="receipt-item-row">
                <span>{item.item_name_snapshot} <span class="receipt-qty">×{item.quantity}</span></span>
                <span>{formatRupiah(item.line_total ?? 0)}</span>
              </div>
              {#if mods}<div class="receipt-mods">{mods}</div>{/if}
            {#if (item.item_discount_amount ?? 0) > 0}
              <div class="receipt-item-discount">−{formatRupiah(item.item_discount_amount ?? 0)} {language.t('discounts')}</div>
            {/if}
            </div>
          {/each}
        </div>

        <div class="receipt-totals">
          {#if (receiptOrder.discount_amount ?? 0) > 0 || itemDiscountTotal > 0 || (receiptOrder.service_amount ?? 0) > 0 || (receiptOrder.pb1_amount ?? 0) > 0}
            <div class="receipt-total-row">
              <span>{language.t('subtotal')}</span><span>{formatRupiah(receiptOrder.subtotal ?? 0)}</span>
            </div>
          {/if}
          {#if itemDiscountTotal > 0}
            <div class="receipt-total-row receipt-total-row--discount">
              <span>{language.t('discounts')}</span>
              <span>−{formatRupiah(itemDiscountTotal)}</span>
            </div>
          {/if}
          {#if (receiptOrder.discount_amount ?? 0) > 0}
            <div class="receipt-total-row receipt-total-row--discount">
              <span>{language.t('discounts')}{receiptOrder.discount_code_snapshot ? ` (${receiptOrder.discount_code_snapshot})` : ''}</span>
              <span>−{formatRupiah(receiptOrder.discount_amount ?? 0)}</span>
            </div>
          {/if}
          {#if (receiptOrder.service_amount ?? 0) > 0}
            <div class="receipt-total-row"><span>{language.t('serviceLabel')}</span><span>{formatRupiah(receiptOrder.service_amount ?? 0)}</span></div>
          {/if}
          {#if (receiptOrder.pb1_amount ?? 0) > 0}
            <div class="receipt-total-row"><span>{language.t('pb1Label')}</span><span>{formatRupiah(receiptOrder.pb1_amount ?? 0)}</span></div>
          {/if}
          <div class="receipt-total-row receipt-total-row--grand display-font">
            <span>{language.t('total')}</span><span>{formatRupiah(receiptOrder.total_amount)}</span>
          </div>
          <div class="receipt-total-row">
            <span>{language.t('payment')}</span><span class="font-bold">{receiptOrder.payment_method}</span>
          </div>
          {#if receiptCashPaid > 0}
            <div class="receipt-total-row">
              <span>{language.t('cash')}</span><span>{formatRupiah(receiptCashPaid)}</span>
            </div>
            <div class="receipt-total-row receipt-total-row--change">
              <span>{language.t('change')}</span><span class="font-bold">{formatRupiah(receiptCashPaid - receiptOrder.total_amount)}</span>
            </div>
          {/if}
        </div>

        {#if session.selectedStore?.receipt_footer?.trim()}
          <div class="receipt-thanks receipt-footer-text">{session.selectedStore.receipt_footer}</div>
        {:else}
          <div class="receipt-thanks">{language.t('thankYou')}</div>
        {/if}
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

        <!-- Manual code input -->
        <div>
          <div class="discount-section-label">{language.t('enterCode')}</div>
          <div class="flex gap-2">
            <input
              class="field flex-1 text-sm"
              placeholder={language.t('promoCode')}
              bind:value={manualCode}
              onkeydown={(e) => { if (e.key === 'Enter') void applyManualCode(); }}
            />
            <button
              class="promo-btn"
              disabled={!manualCode.trim() || cart.length === 0 || promoLoading}
              onclick={applyManualCode}
            >{promoLoading ? '...' : language.t('apply')}</button>
          </div>
          {#if cart.length === 0}
            <p class="mt-1.5 text-xs text-[var(--text-muted)]">{language.t('addItemsBeforeDiscount')}</p>
          {/if}
        </div>

        <!-- Code-based discounts -->
        {#if codeDiscounts.length > 0}
          <div>
            <div class="discount-section-label">{language.t('availablePromoCodes')}</div>
            <div class="space-y-2">
              {#each codeDiscounts as d}
                <button
                  class="discount-option-card {promoResult?.valid && appliedDiscountLabel === d.name ? 'discount-option-card--active' : ''}"
                  onclick={() => selectDiscountFromModal(d)}
                  disabled={cart.length === 0}
                >
                  <div class="flex items-start justify-between gap-3">
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
            <div class="space-y-2">
              {#each autoDiscounts as d}
                <div class="discount-auto-card">
                  <div class="flex items-start justify-between gap-3">
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
  <div class="sheet-backdrop" role="presentation">
    <section class="modifier-modal" role="dialog" aria-modal="true" tabindex="-1">
      <div class="modifier-header">
        <div class="modifier-thumb">
          <img
            src={mediaUrl(modifierItem.image_url) ?? '/images/product-placeholder.svg'}
            alt={modifierItem.name}
            class="h-full w-full {modifierItem.image_url ? 'object-cover' : 'object-contain p-3'}"
          />
        </div>
        <div class="modifier-info">
          <h2 class="display-font modifier-name">{modifierItem.name}</h2>
          <p class="modifier-base">{language.t('base')} {formatRupiah(itemPrice(modifierItem))}</p>
        </div>
        <button class="icon-btn" onclick={closeModifierModal}><span class="ms !text-[18px]" aria-hidden="true">close</span></button>
      </div>

      <div class="modifier-body">
        {#each modifierItem.option_groups ?? [] as group}
          {#if getGroupChoices(group).length}
            <div class="modifier-group">
              <div class="group-label">
                {getGroupLabel(group)}
                {#if group.required}<span class="group-required">{language.t('required')}</span>{/if}
              </div>
              <div class="choice-wrap">
                {#each getGroupChoices(group) as choice}
                  <button
                    class="choice-btn {selectedOptionChoiceIds[group.id] === choice.id ? 'choice-btn--active' : ''}"
                    onclick={() => selectedOptionChoiceIds = { ...selectedOptionChoiceIds, [group.id]: choice.id }}
                  >{getChoiceLabel(choice)}</button>
                {/each}
              </div>
            </div>
          {/if}
        {/each}

        {#each modifierItem.addon_groups ?? [] as group}
          {#if getGroupChoices(group).length}
            <div class="modifier-group">
              <div class="group-label">{getGroupLabel(group)}</div>
              <div class="choice-wrap">
                {#each getGroupChoices(group) as choice}
                  <button
                    class="choice-btn {selectedAddonChoiceIds.includes(choice.id) ? 'choice-btn--active' : ''}"
                    onclick={() => toggleAddon(choice.id)}
                  >
                    {getChoiceLabel(choice)}
                    <span class="choice-price">+{formatRupiah(mk(getChoicePrice(choice)))}</span>
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        {/each}
      </div>

      <div class="modifier-footer">
        <div class="qty-stepper-lg">
          <button class="step-btn-lg" onclick={() => modifierQty = Math.max(1, modifierQty - 1)}>−</button>
          <span class="step-num-lg">{modifierQty}</span>
          <button
            class="step-btn-lg"
            disabled={modifierItem?.stock !== null && modifierItem?.stock !== undefined && modifierQty >= modifierItem.stock - itemQuantity(modifierItem)}
            onclick={() => modifierQty += 1}
          >+</button>
        </div>
        <button
          class="charge-btn modifier-add-btn"
          disabled={!canAddModifierItem}
          onclick={addModifierItemToCart}
        >{language.t('add')} · {formatRupiah(modifierUnitPrice * modifierQty)}</button>
      </div>
    </section>
  </div>
{/if}

<style>
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
    grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
    gap: 12px;
    padding: 4px 16px 16px;
    overflow-y: auto;
    flex: 1;
    align-content: start;
    grid-auto-rows: max-content;
  }
  @media (min-width: 768px) { .item-grid { grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); } }

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

  .item-oos-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0,0,0,0.4);
    display: flex;
    align-items: center;
    justify-content: center;
  }
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
  .stock-badge {
    position: absolute;
    bottom: 6px;
    right: 6px;
    background: var(--om-warning-tint);
    color: var(--om-warning);
    padding: 2px 8px;
    border-radius: var(--om-r-pill);
    font-size: 12px;
    font-weight: 600;
  }
  .options-badge {
    position: absolute;
    top: 8px;
    left: 8px;
    background: rgba(255,255,255,0.95);
    color: var(--om-ink);
    padding: 3px 9px;
    border-radius: var(--om-r-pill);
    font-size: 12px;
    font-weight: 600;
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

  .list-thumb {
    width: 52px;
    height: 52px;
    flex-shrink: 0;
    border-radius: 10px;
    overflow: hidden;
    background: linear-gradient(135deg, var(--light-brown), #d4b896);
  }
  .list-thumb-img { width: 100%; height: 100%; }
  .list-thumb-emoji { width: 100%; height: 100%; display: grid; place-items: center; font-size: 2rem; line-height: 1; }
  .list-info { flex: 1; min-width: 0; }
  .list-name { font-size: 0.9rem; font-weight: 700; color: var(--dark); }
  .list-tags { display: flex; flex-wrap: wrap; gap: 4px; margin: 3px 0; }
  .list-price { font-size: 0.85rem; font-weight: 800; color: var(--warm-brown); }

  .tag { padding: 2px 8px; border-radius: 99px; font-size: 0.65rem; font-weight: 800; }
  .tag--opt { background: var(--light-brown); color: var(--warm-brown); }
  .tag--oos { background: #fee2e2; color: #b91c1c; }
  .tag--stock { background: var(--cream); color: var(--text-muted); }

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
  .order-meta {
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .meta-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .meta-type-btn {
    flex: 1;
    border-radius: 999px;
    border: 1.5px solid var(--border);
    background: var(--white);
    color: var(--text-muted);
    font-size: 0.78rem;
    font-weight: 700;
    padding: 7px 10px;
    transition: all 0.15s;
    cursor: pointer;
  }
  .meta-type-btn:hover { background: var(--cream); }
  .meta-type-btn--active {
    border-color: var(--primary);
    background: var(--primary);
    color: var(--white);
  }
  .meta-type-btn--active:hover { background: var(--dark); border-color: var(--dark); }
  .meta-table-btn {
    flex: 1;
    border-radius: 999px;
    border: 1.5px solid var(--border);
    background: var(--white);
    color: var(--text-muted);
    font-size: 0.78rem;
    font-weight: 700;
    padding: 7px 14px;
    text-align: left;
    transition: all 0.15s;
    cursor: pointer;
  }
  .meta-table-btn:hover { background: var(--cream); }
  .meta-table-btn--selected {
    border-color: var(--primary);
    background: var(--primary);
    color: var(--white);
  }
  .meta-table-btn--selected:hover { background: var(--dark); border-color: var(--dark); }
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

  .pay-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 10px; }

  /* ─── Cash Modal ─── */
  .cash-backdrop { z-index: 55; }

  .cash-modal {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-height: 95vh;
    overflow-y: auto;
    border-radius: 24px 24px 0 0;
    background: var(--white);
    box-shadow: 0 -8px 40px rgba(0,0,0,0.15);
  }
  @media (min-width: 768px) {
    .cash-modal {
      max-width: 340px;
      max-height: 90vh;
      border-radius: 24px;
      box-shadow: 0 24px 64px rgba(0,0,0,0.22);
    }
  }

  .cash-modal-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 18px 18px 16px;
    border-bottom: 1px solid var(--border);
  }
  .cash-modal-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 3px;
  }
  .cash-modal-total {
    font-size: 1.65rem;
    font-weight: 700;
    color: var(--espresso);
    line-height: 1.1;
  }

  .cash-modal-footer {
    display: flex;
    gap: 10px;
    padding: 14px 16px 18px;
    border-top: 1px solid var(--border);
  }
  .cash-confirm-btn { flex: 1; }

  /* Calculator internals */
  .cash-display {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--primary);
    color: white;
  }
  .cash-lbl {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.5);
    margin-bottom: 3px;
  }
  .cash-val {
    font-size: 1.65rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .calc-back-btn {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    border: none;
    background: rgba(255,255,255,0.12);
    color: white;
    font-size: 1rem;
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.12s;
  }
  .calc-back-btn:hover { background: rgba(255,255,255,0.22); }

  .calc-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
    background: var(--border);
  }
  .calc-key {
    padding: 13px 0;
    border: none;
    background: var(--white);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--espresso);
    cursor: pointer;
    transition: background 0.1s;
    letter-spacing: 0.02em;
  }
  .calc-key:hover { background: var(--cream); }
  .calc-key:active { background: var(--light-brown); }
  .calc-key--clear { display: grid; place-items: center; color: var(--text-muted); }
  .calc-key--clear:hover { background: #fef2f2; color: #b91c1c; }
  .calc-key--clear:active { background: #fee2e2; }

  .cash-change {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 9px 14px;
    font-size: 0.82rem;
    font-weight: 700;
  }
  .cash-change--ok { background: #dcfce7; color: #15803d; }
  .cash-change--short { background: #fef2f2; color: #b91c1c; }
  .cash-change--hint { background: var(--cream); color: var(--text-muted); font-weight: 400; }
  .pay-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    padding: 8px 4px;
    border-radius: 12px;
    border: 1.5px solid var(--border);
    background: white;
    cursor: pointer;
    transition: all 0.15s;
  }
  .pay-btn:hover { border-color: var(--warm-brown); background: var(--cream); }
  .pay-btn--active { background: var(--primary); border-color: var(--primary); color: white; }
  .pay-btn--active:hover { background: var(--dark); border-color: var(--dark); }
  .pay-icon { font-size: 1.15rem; line-height: 1; }
  .pay-lbl { font-size: 0.65rem; font-weight: 800; letter-spacing: 0.04em; }

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
  .receipt-head {
    padding: 24px 24px 20px;
    text-align: center;
    border-bottom: 2px dashed #e5e7eb;
  }
  .receipt-logo { display: block; max-height: 64px; max-width: 160px; object-fit: contain; margin: 0 auto 10px; }
  .receipt-store { font-weight: 800; font-size: 1rem; color: var(--espresso); }
  .receipt-date { font-size: 0.72rem; color: var(--text-muted); margin-top: 3px; }
  .receipt-num { font-family: monospace; font-size: 0.82rem; font-weight: 700; margin-top: 6px; color: var(--dark); }
  .receipt-body { flex: 1; overflow-y: auto; padding: 20px 24px; }
  .receipt-items { display: flex; flex-direction: column; gap: 8px; }
  .receipt-item-row { display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 700; }
  .receipt-qty { font-weight: 400; color: var(--text-muted); }
  .receipt-mods { font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; }
  .receipt-totals { margin-top: 16px; padding-top: 16px; border-top: 2px dashed #e5e7eb; display: flex; flex-direction: column; gap: 6px; }
  .receipt-total-row { display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--text-muted); }
  .receipt-total-row--grand { font-size: 1.25rem; font-weight: 800; color: var(--espresso); padding-top: 8px; margin-top: 4px; border-top: 2px dashed #e5e7eb; }
  .receipt-total-row--change { color: #15803d; }
  .receipt-thanks { text-align: center; font-size: 0.78rem; color: var(--text-muted); margin-top: 20px; }
  .receipt-header-text { font-size: 0.75rem; color: var(--text-muted); margin-top: 8px; white-space: pre-line; }
  .receipt-footer-text { white-space: pre-line; }
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
  .modifier-base { font-size: 0.82rem; color: var(--text-muted); margin: 3px 0 0; }

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
  .qty-stepper-lg {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    border-radius: 12px;
    border: 1.5px solid var(--border);
    background: var(--cream);
    flex-shrink: 0;
  }
  .step-btn-lg {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    border: none;
    background: white;
    color: var(--espresso);
    font-size: 1.2rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.12s;
  }
  .step-btn-lg:hover:not(:disabled) { background: var(--primary); color: white; }
  .step-btn-lg:disabled { opacity: 0.3; cursor: not-allowed; }
  .step-num-lg { width: 28px; text-align: center; font-size: 1rem; font-weight: 800; }
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

  .promo-btn {
    flex-shrink: 0;
    padding: 0 14px;
    height: 40px;
    border-radius: 10px;
    border: 1.5px solid var(--border);
    background: var(--cream);
    color: var(--espresso);
    font-size: 0.8rem;
    font-weight: 800;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s, border-color 0.15s;
  }
  .promo-btn:hover:not(:disabled) { background: var(--primary); border-color: var(--primary); color: white; }
  .promo-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ─── Discount modal ─── */
  .discount-modal-shell {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 480px;
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
  .receipt-item-discount { font-size: 0.7rem; color: #16a34a; margin-top: 2px; font-weight: 700; }
  .receipt-total-row--discount { color: #16a34a; }
  .cash-modal-subtotal-note { font-size: 0.68rem; color: #16a34a; font-weight: 700; margin-top: 2px; }

  /* ─── Utilities ─── */
  .no-scrollbar { scrollbar-width: none; }
  .no-scrollbar::-webkit-scrollbar { display: none; }

  /* ─── Print ─── */
  @media print {
    @page { size: 58mm auto; margin: 4mm 2mm; }
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
</style>
