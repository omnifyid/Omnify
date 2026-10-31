<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { ChannelSetting, Order, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import type { MessageKey } from '$lib/i18n/messages';
  import { session } from '$lib/stores/session.svelte';
  import { shiftState } from '$lib/stores/shift.svelte';
  import { formatDigits, parseAmount } from '$lib/utils/finance';
  import { CHANNEL_META } from '$lib/utils/channels';
  import Pagination from '$lib/components/Pagination.svelte';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { chip, CHIP_ROW, seg, SEG_GROUP } from '$lib/utils/ui';
  import { paymentText } from '$lib/utils/payment';
  import { PAGE_SIZE } from '$lib/utils/paging';

  type Period = 'today' | 'yday' | '7d' | '30d';
  type ChannelFilter = 'all' | 'dine' | 'take' | 'online';
  type StatusFilter = 'all' | 'verify' | 'kitchen' | 'ready' | 'confirmed' | 'done' | 'cancelled';
  type OrderState = { key: MessageKey; tint: string; fg: string };

  const VIEW_KEY = 'kasir.ordersView';

  const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const daysAgo = (n: number) => iso(new Date(Date.now() - n * 86400000));
  const hm = (v: string) => new Date(v).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', hour12: false }).replace('.', ':');

  const PERIODS: { id: Period; key: MessageKey }[] = [
    { id: 'today', key: 'finToday' },
    { id: 'yday', key: 'txYesterday' },
    { id: '7d', key: 'fin7d' },
    { id: '30d', key: 'fin30d' }
  ];
  const STATES = {
    verify: { key: 'txFVerify', tint: 'var(--om-warning-tint)', fg: 'var(--om-warning)' },
    new: { key: 'txStNew', tint: 'var(--om-info-tint)', fg: 'var(--om-info)' },
    cooking: { key: 'txStCooking', tint: 'var(--om-warning-tint)', fg: 'var(--om-warning)' },
    ready: { key: 'txFReady', tint: 'var(--om-brand-tint)', fg: 'var(--om-brand)' },
    confirmed: { key: 'txFConfirmed', tint: 'var(--om-info-tint)', fg: 'var(--om-info)' },
    done: { key: 'txFDone', tint: 'var(--om-fill-muted)', fg: 'var(--om-ink-2)' },
    cancelled: { key: 'txFCancelled', tint: 'var(--om-danger-tint)', fg: 'var(--om-danger)' }
  } satisfies Record<string, OrderState>;

  let orders = $state<Order[]>([]);
  let total = $state(0);
  let pageNo = $state(1);
  let pendingCount = $state(0);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  let channelSettings = $state<ChannelSetting[]>([]);
  let period = $state<Period>('today');
  let channelFilter = $state<ChannelFilter>('all');
  let statusFilter = $state<StatusFilter>('all');
  let query = $state('');
  let view = $state<'list' | 'grid'>('list');
  let selectedId = $state<string | null>(null);
  let confirmingId = $state<string | null>(null);
  let error = $state('');
  let loading = $state(false);

  let kitchenOn = $derived(!!session.selectedStore?.kitchen_enabled);
  let onlineOn = $derived(channelSettings.some((c) => c.enabled));
  let selected = $derived(orders.find((o) => o.id === selectedId) ?? null);

  function stateOf(o: Order): OrderState {
    if (o.status === 'PENDING') return STATES.verify;
    if (o.status === 'CANCELLED') return STATES.cancelled;
    if (o.status === 'COMPLETED') return STATES.done;
    if (o.kitchen_status === 'NEW') return STATES.new;
    if (o.kitchen_status === 'COOKING') return STATES.cooking;
    if (o.kitchen_status === 'READY') return STATES.ready;
    return STATES.confirmed;
  }

  const isQr = (o: Order) => !o.channel && !o.operator_id;
  const STATUS_FILTERS: { id: StatusFilter; key: MessageKey; kitchen?: boolean }[] = [
    { id: 'all', key: 'txAll' },
    { id: 'verify', key: 'txFVerify' },
    { id: 'kitchen', key: 'txFKitchen', kitchen: true },
    { id: 'ready', key: 'txFReady', kitchen: true },
    { id: 'confirmed', key: 'txFConfirmed' },
    { id: 'done', key: 'txFDone' },
    { id: 'cancelled', key: 'txFCancelled' }
  ];

  // Filters, search and paging are applied by the server; `orders` is only the current page.
  let shown = $derived(orders);
  let legend = $derived([...new Map(shown.map((o) => [stateOf(o).key, stateOf(o)])).values()]);

  const whereOf = (o: Order) =>
    o.channel ? CHANNEL_META[o.channel as keyof typeof CHANNEL_META]?.label ?? o.channel : o.order_type === 'DINE_IN' ? `${language.t('txDineIn')}${o.table_number ? ` · ${o.table_number}` : ''}` : language.t('txTakeAway');
  const customerOf = (o: Order) => o.customer_name || (isQr(o) ? language.t('txSrcQr') : '—');
  const itemsOf = (o: Order) => (o.items ?? []).map((i) => (i.quantity > 1 ? `${i.quantity}× ` : '') + i.item_name_snapshot).join(', ');
  const payOf = (o: Order) => (o.channel ? CHANNEL_META[o.channel as keyof typeof CHANNEL_META]?.label ?? o.channel : o.payment_method);
  const sourceIcon = (o: Order) => (o.channel ? 'delivery_dining' : isQr(o) ? 'qr_code_2' : 'point_of_sale');
  const sourceLabel = (o: Order) => (o.channel ? payOf(o) : isQr(o) ? language.t('txSrcQr') : language.t('txSrcPos'));
  const timeOf = (o: Order) => (o.created_at ? (period === 'today' ? hm(o.created_at) : formatDateTime(o.created_at)) : '');

  async function load(silent = false) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    if (!silent) loading = true;
    try {
      const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((pageNo - 1) * PAGE_SIZE) });
      // Orders waiting for verification are shown regardless of the period.
      if (statusFilter !== 'verify') {
        q.set('date_from', period === 'today' ? daysAgo(0) : period === 'yday' ? daysAgo(1) : period === '7d' ? daysAgo(6) : daysAgo(29));
        q.set('date_to', period === 'yday' ? daysAgo(1) : daysAgo(0));
      }
      if (channelFilter !== 'all') q.set('kind', channelFilter);
      if (statusFilter !== 'all') q.set('state', statusFilter);
      if (query.trim()) q.set('search', query.trim());
      const [res, pend] = await Promise.all([
        api.get<PaginatedResponse<Order>>(`/stores/${storeId}/orders?${q}`),
        api.get<PaginatedResponse<Order>>(`/stores/${storeId}/orders?status=PENDING&limit=1`)
      ]);
      orders = paginatedItems(res);
      total = res.total;
      pendingCount = pend.total;
      if (!orders.length && pageNo > 1) pageNo = Math.max(1, Math.ceil(total / PAGE_SIZE));
      error = '';
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  async function loadChannels() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    channelSettings = await api.get<ChannelSetting[]>(`/stores/${storeId}/channels`).catch(() => []);
  }

  let cancelArmed = $state<string | null>(null);

  // Void / refund dialog (Owner and Manager only)
  const REASONS = ['Salah input', 'Pelanggan komplain', 'Item habis', 'Kelebihan bayar', 'Lain-lain'];
  let dialog = $state<{ kind: 'refund' | 'void'; order: Order } | null>(null);
  let dAmount = $state('');
  let dMethod = $state<'CASH' | 'TRANSFER'>('CASH');
  let dReason = $state('');
  let dNote = $state('');
  let dLine = $state('');
  let dQty = $state('1');
  let dError = $state('');
  let dSaving = $state(false);

  let canManage = $derived(['OWNER', 'MANAGER'].includes(session.selectedStore?.role ?? ''));
  const remaining = (o: Order) => o.total_amount - (o.refunded_amount ?? 0);
  const canRefund = (o: Order) => canManage && !o.channel && (o.status === 'CONFIRMED' || o.status === 'COMPLETED') && remaining(o) > 0;
  const leftOf = (i: NonNullable<Order['items']>[number]) => i.quantity - (i.void_qty ?? 0);
  let hasShift = $derived(!!shiftState.current?.shift);

  function openDialog(kind: 'refund' | 'void', o: Order) {
    dialog = { kind, order: o };
    dAmount = kind === 'refund' ? remaining(o).toLocaleString('id-ID') : '';
    dMethod = hasShift ? 'CASH' : 'TRANSFER';
    dReason = '';
    dNote = '';
    dLine = (o.items ?? []).find((i) => leftOf(i) > 0)?.id ?? '';
    dQty = '1';
    dError = '';
    void shiftState.load();
  }

  async function submitDialog() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !dialog) return;
    const o = dialog.order;
    if (!dReason) return void (dError = language.t('txErrReason'));
    if (dReason === 'Lain-lain' && !dNote.trim()) return void (dError = language.t('txErrNote'));
    const reason = dReason + (dNote.trim() ? ` · ${dNote.trim()}` : '');
    dSaving = true;
    dError = '';
    try {
      if (dialog.kind === 'refund') {
        const amount = parseAmount(dAmount);
        if (amount <= 0) return void (dError = language.t('finErrAmount'));
        await api.post(`/stores/${storeId}/orders/${o.id}/refund`, { amount, method: dMethod, reason });
      } else {
        await api.post(`/stores/${storeId}/orders/${o.id}/items/${dLine}/void`, { quantity: parseInt(dQty, 10) || 0, method: dMethod, reason });
      }
      dialog = null;
      await load(true);
      void shiftState.load();
    } catch (err) {
      dError = err instanceof Error ? err.message : language.t('error');
    } finally {
      dSaving = false;
    }
  }

  const select = (id: string) => {
    selectedId = id;
    cancelArmed = null;
  };
  const formatDate = (d: string) => new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium' }).format(new Date(`${d}T00:00:00`));

  async function updateStatus(o: Order, status: 'CONFIRMED' | 'COMPLETED' | 'CANCELLED') {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    confirmingId = o.id;
    try {
      await api.patch(`/stores/${storeId}/orders/${o.id}/status`, { status });
      cancelArmed = null;
      await load(true);
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      confirmingId = null;
    }
  }

  // Progress bar under the drawer header: label sets and reached level depend on the order's source.
  function steps(o: Order): { label: MessageKey; on: boolean }[] {
    const k = o.kitchen_status;
    const done = o.status === 'COMPLETED';
    let labels: MessageKey[];
    let level: number;
    if (o.status === 'CANCELLED') {
      labels = o.channel ? ['txStepReceived', 'txStepPrep', 'txFReady', 'txStepPicked', 'txFDone'] : ['txStepCreated', 'txStepProcessing', 'txFReady', 'txFDone'];
      level = 0;
    } else if (isQr(o)) {
      labels = ['txStepSent', 'txStepVerified', 'txStepProcessing', 'txFReady', 'txFDone'];
      level = o.status === 'PENDING' ? 1 : done ? 5 : k === 'COOKING' ? 3 : k === 'READY' || k === 'SERVED' ? 4 : 2;
    } else if (o.channel) {
      labels = ['txStepReceived', 'txStepPrep', 'txFReady', 'txStepPicked', 'txFDone'];
      level = done ? 5 : k === 'COOKING' ? 2 : k === 'READY' ? 3 : k === 'SERVED' ? 4 : 1;
    } else {
      labels = ['txStepCreated', 'txStepProcessing', 'txFReady', 'txFDone'];
      level = done ? 4 : k === 'COOKING' ? 2 : k === 'READY' || k === 'SERVED' ? 3 : 1;
    }
    return labels.map((label, i) => ({ label, on: level > i }));
  }

  function modifiers(snapshot: unknown[] | null | undefined) {
    return (snapshot ?? [])
      .map((e) => (typeof e === 'string' ? e : e && typeof e === 'object' ? String((e as Record<string, unknown>).name ?? (e as Record<string, unknown>).choice_name ?? '') : ''))
      .filter(Boolean)
      .join(', ');
  }

  function setView(v: 'list' | 'grid') {
    view = v;
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* storage unavailable */
    }
  }

  $effect(() => {
    try {
      const v = localStorage.getItem(VIEW_KEY);
      if (v === 'list' || v === 'grid') view = v;
    } catch {
      /* storage unavailable */
    }
  });

  $effect(() => {
    void session.selectedStore?.id;
    void period;
    void channelFilter;
    void statusFilter;
    void pageNo;
    void query;
    untrack(() => {
      selectedId = null;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => void load(), query.trim() ? 350 : 0);
    });
  });

  $effect(() => {
    void session.selectedStore?.id;
    untrack(() => void loadChannels());
  });

  $effect(() => {
    const t = setInterval(() => void load(true), 30_000);
    return () => clearInterval(t);
  });

  const viewBtn = (on: boolean) =>
    `grid h-11 w-11 place-items-center rounded-[9px] text-[var(--om-ink)] ${on ? 'bg-white shadow-[0_1px_2px_rgba(16,20,15,.12)]' : ''}`;
  const channelFilters = $derived([
    { id: 'all' as const, key: 'txAll' as MessageKey },
    { id: 'dine' as const, key: 'txChDine' as MessageKey },
    { id: 'take' as const, key: 'txChTake' as MessageKey },
    ...(onlineOn ? [{ id: 'online' as const, key: 'txChOnline' as MessageKey }] : [])
  ]);
</script>

<svelte:head><title>{language.t('transactions')} | Omnify</title></svelte:head>

<div class="flex h-full min-h-0">
<div class="min-w-0 flex-1 overflow-auto" style="padding: var(--om-page-pad)">
{#if pendingCount > 0 && statusFilter !== 'verify'}
  <div class="mb-4 flex flex-wrap items-center gap-3 rounded-[12px] border border-[#F4CFC9] bg-[var(--om-danger-tint)] px-4 py-3">
    <span class="ms text-[var(--om-danger)]">qr_code_2</span>
    <span class="min-w-[200px] flex-1 leading-snug text-[#7A1C16]"><strong>{pendingCount} {language.t('txBannerSuffix')}</strong></span>
    <button class="rounded-[9px] bg-[var(--om-danger)] px-4 font-semibold text-white" style="min-height: var(--om-tap)" onclick={() => { statusFilter = 'verify'; pageNo = 1; }}>{language.t('txVerify')}</button>
  </div>
{/if}

{#if error}
  <div role="alert" class="mb-4 flex items-center gap-2 rounded-[12px] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)]"><span class="ms">error</span>{error}</div>
{/if}

<div class="mb-3 flex flex-wrap items-center gap-2.5">
  <div class={SEG_GROUP} role="group">
    {#each PERIODS as p (p.id)}
      <button class={seg(period === p.id)} style="height: var(--om-tap)" aria-pressed={period === p.id} onclick={() => { period = p.id; pageNo = 1; }}>{language.t(p.key)}</button>
    {/each}
  </div>
  <div class="min-w-0 flex-[1_1_300px] {CHIP_ROW}">
    {#each channelFilters as c (c.id)}
      <button class={chip(channelFilter === c.id)} style="height: var(--om-tap)" onclick={() => { channelFilter = c.id; pageNo = 1; }}>{language.t(c.key)}</button>
    {/each}
  </div>
  <label class="flex w-full items-center gap-2 rounded-[10px] border border-[var(--om-border)] bg-white px-3 md:w-[220px]" style="height: var(--om-tap)">
    <span class="ms !text-[20px] text-[var(--om-text-secondary)]">search</span>
    <input class="min-w-0 flex-1 bg-transparent text-[16px] text-[var(--om-ink)] outline-none" placeholder={language.t('txSearch')} bind:value={query} oninput={() => (pageNo = 1)} />
  </label>
  <div class="flex shrink-0 gap-1 rounded-[12px] bg-[#EDECE7] p-[3px]" role="group" aria-label="View">
    <button class={viewBtn(view === 'list')} aria-pressed={view === 'list'} aria-label={language.t('txViewList')} title={language.t('txViewList')} onclick={() => setView('list')}><span class="ms !text-[24px]">view_list</span></button>
    <button class={viewBtn(view === 'grid')} aria-pressed={view === 'grid'} aria-label={language.t('txViewGrid')} title={language.t('txViewGrid')} onclick={() => setView('grid')}><span class="ms !text-[24px]">grid_view</span></button>
  </div>
</div>

<div class="mb-3.5 {CHIP_ROW}">
  {#each STATUS_FILTERS.filter((f) => !f.kitchen || kitchenOn) as f (f.id)}
    <button class="{chip(statusFilter === f.id)} !px-3.5" style="height: var(--om-tap)" onclick={() => { statusFilter = f.id; pageNo = 1; }}>{language.t(f.key)}</button>
  {/each}
</div>

<div class:opacity-60={loading}>
  {#if view === 'grid'}
    <div class="grid gap-2.5" style="grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr))">
      {#each shown as o (o.id)}
        {@const st = stateOf(o)}
        <div
          class="flex cursor-pointer flex-col gap-2.5 rounded-[14px] border-[1.5px] bg-white p-3.5 transition-colors active:bg-[var(--om-surface-sunk)] {selectedId === o.id ? 'border-[var(--om-ink)]' : o.status === 'PENDING' ? 'border-[#F4CFC9]' : 'border-[var(--om-border)]'}"
          style="min-height: var(--om-tap)"
          role="button"
          tabindex="0"
          onclick={() => select(o.id)}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(o.id); } }}
        >
          <div class="flex items-center gap-2">
            <span class="text-[16px] font-bold tabular-nums">#{o.order_number}</span>
            {#if o.channel}<img src={CHANNEL_META[o.channel as keyof typeof CHANNEL_META]?.logo} alt={payOf(o)} class="h-[22px] w-auto max-w-[57px]" />{/if}
            <span class="flex min-w-0 flex-1 items-center gap-1 text-[12px] text-[var(--om-text-secondary)]"><span class="ms !text-[16px]">{sourceIcon(o)}</span><span class="truncate">{sourceLabel(o)} · {timeOf(o)}</span></span>
            <span class="whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] font-semibold" style="background:{st.tint};color:{st.fg}">{language.t(st.key)}</span>
          </div>
          <div class="flex items-end gap-3">
            <div class="flex min-w-0 flex-1 flex-col gap-0.5">
              <span class="font-medium">{customerOf(o)} · {whereOf(o)}</span>
              <span class="truncate text-[12px] text-[var(--om-text-secondary)]">{itemsOf(o)}</span>
            </div>
            <div class="flex shrink-0 flex-col items-end gap-0.5"><span class="font-bold tabular-nums">{formatRupiah(o.total_amount)}</span><span class="text-[12px] text-[var(--om-text-secondary)]">{payOf(o)}</span></div>
          </div>
        </div>
      {/each}
    </div>
    {#if !shown.length && !loading}<div class="p-10 text-center text-[var(--om-text-secondary)]">{language.t('txEmpty')}</div>{/if}
  {:else}
    {#if legend.length}
      <div class="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-[var(--om-text-secondary)]">
        {#each legend as l (l.key)}<span class="flex items-center gap-1.5"><span class="h-3.5 w-3.5 rounded-[4px]" style="background:{l.tint};box-shadow: inset 3px 0 0 {l.fg}, inset 0 0 0 1px #D7D5CE"></span>{language.t(l.key)}</span>{/each}
      </div>
    {/if}
    <div class="card overflow-auto">
      <div class="min-w-[820px]">
        <div class="grid grid-cols-[108px_100px_72px_120px_minmax(0,1.2fr)_minmax(0,1.4fr)_110px] gap-3 border-b border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-[18px] py-3 text-[12px] text-[var(--om-text-secondary)]">
          <span>{language.t('order')}</span><span>{language.t('txPay')}</span><span>{language.t('txTime')}</span><span>{language.t('txSource')}</span><span>{language.t('txCustomer')}</span><span>{language.t('txItems')}</span><span class="text-right">{language.t('total')}</span>
        </div>
        {#each shown as o (o.id)}
          {@const st = stateOf(o)}
          <div
            class="grid cursor-pointer grid-cols-[108px_100px_72px_120px_minmax(0,1.2fr)_minmax(0,1.4fr)_110px] items-center gap-3 border-b border-[var(--om-divider)] px-[18px] py-[13px] transition hover:brightness-[0.97]"
            style="min-height: var(--om-tap); background:{st.tint}; box-shadow: {selectedId === o.id ? 'inset 0 0 0 2px var(--om-ink), ' : ''}inset 4px 0 0 {st.fg}"
            title={language.t(st.key)}
            role="button"
            tabindex="0"
            onclick={() => select(o.id)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(o.id); } }}
          >
            <span class="font-bold tabular-nums">#{o.order_number}</span>
            <span class="flex items-center">{#if o.channel}<img src={CHANNEL_META[o.channel as keyof typeof CHANNEL_META]?.logo} alt={payOf(o)} class="h-[22px] w-auto max-w-[57px]" />{:else}<span class="text-[12px] font-medium text-[var(--om-ink-2)]">{o.payment_method}</span>{/if}</span>
            <span class="tabular-nums text-[var(--om-ink-2)]">{timeOf(o)}</span>
            <span class="flex items-center gap-1.5 text-[var(--om-ink-2)]"><span class="ms !text-[16px] text-[var(--om-text-secondary)]">{sourceIcon(o)}</span>{sourceLabel(o)}</span>
            <div class="flex min-w-0 flex-col"><span class="truncate font-medium">{customerOf(o)}</span><span class="text-[12px] text-[var(--om-text-secondary)]">{whereOf(o)}</span></div>
            <span class="truncate text-[var(--om-ink-2)]">{itemsOf(o)}</span>
            <span class="text-right font-semibold tabular-nums">{formatRupiah(o.total_amount)}</span>
          </div>
        {/each}
        {#if !shown.length && !loading}<div class="p-10 text-center text-[var(--om-text-secondary)]">{language.t('txEmpty')}</div>{/if}
      </div>
    </div>
  {/if}
  <Pagination page={pageNo} {total} {loading} onPage={(p) => (pageNo = p)} />
</div>
</div>

{#if selected}
  {@const o = selected}
  {@const st = stateOf(o)}
  {@const busy = confirmingId === o.id}
  <aside
    class="fixed inset-y-0 right-0 z-40 flex w-full shrink-0 flex-col bg-white shadow-[-12px_0_40px_rgba(16,20,15,.15)] md:w-[370px] xl:static xl:z-auto xl:shadow-none xl:border-l xl:border-[var(--om-border)]"
    aria-label={`#${o.order_number}`}
  >
    <div class="flex items-start justify-between border-b border-[var(--om-divider)] px-5 py-[18px]">
      <div class="flex min-w-0 flex-col gap-1">
        <span class="text-[20px] font-bold tabular-nums">#{o.order_number}</span>
        <span class="text-[12px] text-[var(--om-text-secondary)]">{customerOf(o)} · {whereOf(o)} · {o.created_at ? formatDateTime(o.created_at) : ''}</span>
      </div>
      <a href={`/transactions/${o.id}`} class="inline-flex shrink-0 items-center justify-center rounded-[8px] text-[var(--om-text-secondary)] hover:bg-[var(--om-fill-muted)]" style="min-width: var(--om-tap); min-height: var(--om-tap)" aria-label={language.t('detail')} title={language.t('detail')}><span class="ms">open_in_new</span></a>
      <button class="inline-flex shrink-0 items-center justify-center rounded-[8px] text-[var(--om-text-secondary)] hover:bg-[var(--om-fill-muted)]" style="min-width: var(--om-tap); min-height: var(--om-tap)" aria-label={language.t('close')} onclick={() => (selectedId = null)}><span class="ms">close</span></button>
    </div>

    <div class="grid min-h-0 flex-1 content-start gap-4 overflow-y-auto px-5 py-4" style="grid-auto-rows: max-content">
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="rounded-full px-2.5 py-1 text-[12px] font-semibold" style="background:{st.tint};color:{st.fg}">{language.t(st.key)}</span>
        {#if o.channel}
          <span class="flex items-center gap-1.5 rounded-full bg-[var(--om-fill-muted)] py-[3px] pl-[3px] pr-2.5 text-[12px] font-bold">
            <img src={CHANNEL_META[o.channel as keyof typeof CHANNEL_META]?.logo} alt="" class="h-5 w-[52px] object-contain" />{payOf(o)}
          </span>
        {/if}
      </div>

      {#if o.channel}
        <div class="flex flex-col gap-2 rounded-[12px] border border-[var(--om-border)] bg-[var(--om-surface-sunk)] p-3.5">
          <div class="flex justify-between gap-2.5"><span class="text-[var(--om-ink-2)]">{language.t('txPlatformId')}</span><span class="font-bold tabular-nums">{o.channel_order_id ?? '—'}</span></div>
          {#if o.driver_name}<div class="flex justify-between gap-2.5"><span class="text-[var(--om-ink-2)]">{language.t('txDriver')}</span><span class="font-medium">{o.driver_name}</span></div>{/if}
          {#if o.notes}<div class="text-[12px] text-[var(--om-ink-2)]">“{o.notes}”</div>{/if}
          <div class="h-px bg-[var(--om-border)]"></div>
          <div class="flex justify-between gap-2.5"><span class="text-[var(--om-ink-2)]">{language.t('txGrossApp')}</span><span class="font-semibold tabular-nums">{formatRupiah(o.total_amount)}</span></div>
          <div class="flex justify-between gap-2.5"><span class="text-[var(--om-ink-2)]">{language.t('txCommission')}</span><span class="tabular-nums text-[var(--om-danger)]">−{formatRupiah(o.commission_amount ?? 0)}</span></div>
          <div class="flex justify-between gap-2.5 font-bold"><span>{language.t('txExpectedPayout')}</span><span class="tabular-nums">{formatRupiah(o.expected_payout ?? 0)}</span></div>
          {#if o.tax_amount}<div class="flex justify-between gap-2.5 text-[12px]"><span class="text-[var(--om-ink-2)]">{language.t('txTaxIncluded')}</span><span class="tabular-nums">{formatRupiah(o.tax_amount)}</span></div>{/if}
          <div class="text-[12px] font-medium {o.settlement_id ? 'text-[var(--om-brand)]' : 'text-[var(--om-text-secondary)]'}">
            {o.settlement_id ? language.t('txPaidOut') : o.status === 'CANCELLED' ? '' : `${language.t('txEstPayoutOn')} ${o.expected_payout_date ? formatDate(o.expected_payout_date) : '—'}`}
          </div>
          {#if o.app_total && o.app_total !== o.total_amount}
            <div class="text-[12px] font-semibold text-[var(--om-warning)]">{language.t('txAppTotal')} {formatRupiah(o.app_total)} · {language.t('txAppDiff')} {o.app_total - o.total_amount > 0 ? '+' : '−'}{formatRupiah(Math.abs(o.app_total - o.total_amount))}</div>
          {/if}
        </div>
      {/if}

      <div class="flex gap-1.5">
        {#each steps(o) as step (step.label)}
          <div class="flex flex-1 flex-col gap-1.5">
            <div class="h-1 rounded-[3px] {step.on ? 'bg-[var(--om-brand-bright)]' : 'bg-[var(--om-border)]'}"></div>
            <span class="text-[12px] font-medium {step.on ? 'text-[var(--om-ink)]' : 'text-[var(--om-text-secondary)]'}">{language.t(step.label)}</span>
          </div>
        {/each}
      </div>

      {#if isQr(o)}
        <div class="flex items-start gap-2.5 rounded-[12px] bg-[var(--om-bg)] p-3">
          <span class="ms text-[var(--om-brand)]">qr_code_2</span>
          <div class="flex flex-col gap-[3px]"><span class="font-semibold">{language.t('txSelfOrderFrom')}</span>{#if o.notes}<span class="text-[12px] text-[var(--om-ink-2)]">“{o.notes}”</span>{/if}</div>
        </div>
      {:else if o.notes && !o.channel}
        <div class="rounded-[12px] bg-[var(--om-bg)] p-3 text-[14px] text-[var(--om-ink-2)]">“{o.notes}”</div>
      {/if}

      <div class="flex flex-col">
        {#each o.items ?? [] as i (i.id)}
          {@const mods = [modifiers(i.options_snapshot), modifiers(i.addons_snapshot)].filter(Boolean).join(' · ')}
          <div class="flex gap-2.5 border-b border-[var(--om-divider)] py-2.5">
            <span class="w-[26px] font-bold tabular-nums">{i.quantity}×</span>
            <div class="flex flex-1 flex-col gap-0.5"><span class="font-medium {leftOf(i) <= 0 ? 'line-through' : ''}">{i.item_name_snapshot}</span>{#if i.void_qty}<span class="text-[12px] text-[var(--om-danger)]">{i.void_qty} {language.t('txVoided')}</span>{/if}{#if mods}<span class="text-[12px] text-[var(--om-warning)]">{mods}</span>{/if}</div>
            <span class="text-[12px] tabular-nums">{formatRupiah(i.line_total ?? i.unit_price_snapshot * i.quantity)}</span>
          </div>
        {/each}
      </div>

      <div class="flex flex-col gap-[7px] text-[var(--om-text-secondary)]">
        <div class="flex justify-between"><span>{language.t('txSubtotal')}</span><span class="tabular-nums">{formatRupiah(o.subtotal ?? o.total_amount)}</span></div>
        {#if o.service_amount}<div class="flex justify-between"><span>{language.t('serviceLabel')}</span><span class="tabular-nums">{formatRupiah(o.service_amount)}</span></div>{/if}
        {#if o.pb1_amount}<div class="flex justify-between"><span>{language.t('pb1Label')}</span><span class="tabular-nums">{formatRupiah(o.pb1_amount)}</span></div>{/if}
        {#if o.discount_amount}<div class="flex justify-between text-[var(--om-brand)]"><span>{language.t('txDiscount')}{o.discount_code_snapshot ? ` · ${o.discount_code_snapshot}` : ''}</span><span class="tabular-nums">−{formatRupiah(o.discount_amount)}</span></div>{/if}
        <div class="flex justify-between border-t border-dashed border-[#DAD8D1] pt-2 font-semibold text-[var(--om-ink)]"><span>{language.t('total')}</span><span class="text-[20px] tabular-nums">{formatRupiah(o.total_amount)}</span></div>
      </div>

      {#if o.refunds?.length}
        <div class="flex flex-col gap-0.5 rounded-[12px] border border-[#F4CFC9] bg-[#FFFAF8] px-3.5 py-3">
          <span class="pb-1 text-[12px] font-semibold text-[var(--om-danger)]">{language.t('txRefundsTitle')}</span>
          {#each o.refunds as r (r.id)}
            <div class="flex gap-2.5 border-t border-[#F4E2DE] py-2">
              <div class="flex min-w-0 flex-1 flex-col gap-0.5">
                <span class="text-[12px] font-semibold">{language.t(r.type === 'VOID' ? 'txRefundTypeVoid' : 'txRefundTypeRefund')}{r.quantity ? ` ×${r.quantity}` : ''}</span>
                <span class="text-[12px] text-[var(--om-text-secondary)]">{formatDateTime(r.refunded_at)} · {language.t(r.method === 'CASH' ? 'txMethodCash' : 'txMethodTransfer')}</span>
                <span class="text-[12px] text-[var(--om-ink-2)]">{r.reason}</span>
              </div>
              <span class="whitespace-nowrap font-bold tabular-nums text-[var(--om-danger)]">−{formatRupiah(r.amount)}</span>
            </div>
          {/each}
          <div class="flex justify-between border-t border-[#F4E2DE] pt-2 font-bold"><span>{language.t('txNetValue')}</span><span class="tabular-nums">{formatRupiah(remaining(o))}</span></div>
        </div>
      {/if}

      {#if !o.channel && (o.status === 'CONFIRMED' || o.status === 'COMPLETED')}
        <div class="flex items-center gap-2.5 rounded-[12px] border border-[var(--om-border)] p-3">
          <span class="ms text-[var(--om-brand)]">verified</span>
          <span>{language.t('txPaidWith')} {formatRupiah(o.total_amount)} {language.t('txWith')} {paymentText(o)}</span>
        </div>
      {/if}
    </div>

    <div class="flex flex-wrap gap-2 border-t border-[var(--om-border)] px-5 pt-3.5" style="padding-bottom: calc(14px + env(safe-area-inset-bottom))">
      <div class="flex w-full gap-2">
        <button class="flex h-[46px] flex-1 items-center justify-center gap-1.5 rounded-[10px] border border-[var(--om-border)] bg-white px-3 font-semibold hover:border-[var(--om-brand)]" onclick={() => goto(`/transactions/${o.id}?receipt=1`)}><span class="ms !text-[20px]">print</span>{language.t('txPrintReceipt')}</button>
        <button class="flex h-[46px] flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-[10px] border border-[var(--om-border)] bg-white px-3 font-semibold hover:border-[var(--om-brand)]" onclick={() => goto(`/transactions/${o.id}?ticket=1`)}><span class="ms !text-[20px]">skillet</span>{language.t('txTicket')}</button>
      </div>
      {#if canRefund(o)}
        <div class="flex w-full gap-2">
          <button class="flex h-[46px] flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-[10px] border border-[var(--om-border)] bg-white px-3 font-semibold hover:border-[var(--om-brand)]" onclick={() => openDialog('void', o)}><span class="ms !text-[20px]">remove_shopping_cart</span>{language.t('txVoidItem')}</button>
          <button class="flex h-[46px] flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-[10px] border border-[var(--om-border)] bg-white px-3 font-semibold hover:border-[var(--om-brand)]" onclick={() => openDialog('refund', o)}><span class="ms !text-[20px]">currency_exchange</span>{language.t('txRefund')}</button>
        </div>
      {/if}
      {#if o.status === 'PENDING' || o.status === 'CONFIRMED'}
        <button
          class="flex h-[46px] flex-1 items-center justify-center gap-1.5 rounded-[10px] border bg-white px-3 font-semibold whitespace-nowrap disabled:opacity-50 {cancelArmed === o.id ? 'border-[var(--om-danger)] bg-[var(--om-danger)] text-white' : 'border-[var(--om-border)] text-[var(--om-danger)]'}"
          disabled={busy}
          onclick={() => (cancelArmed === o.id ? updateStatus(o, 'CANCELLED') : (cancelArmed = o.id))}
        ><span class="ms !text-[20px]">cancel</span>{cancelArmed === o.id ? language.t('txCancelSure') : language.t(o.status === 'PENDING' ? 'txReject' : 'txCancelOrder')}</button>
        <button
          class="flex h-[46px] flex-[2] items-center justify-center gap-1.5 rounded-[10px] border border-[var(--om-brand)] bg-[var(--om-brand)] px-3 font-semibold whitespace-nowrap text-white disabled:opacity-50"
          disabled={busy}
          onclick={() => updateStatus(o, o.status === 'PENDING' ? 'CONFIRMED' : 'COMPLETED')}
        ><span class="ms !text-[20px]">{o.status === 'PENDING' ? 'task_alt' : 'done_all'}</span>{busy ? '…' : language.t(o.status === 'PENDING' ? 'txConfirmOrder' : 'txComplete')}</button>
      {/if}
    </div>
  </aside>
{/if}
</div>

{#if dialog}
  {@const o = dialog.order}
  {@const label = 'mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--om-text-secondary)]'}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) dialog = null; }}>
    <section class="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-white md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--om-border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font truncate text-2xl font-bold">{language.t(dialog.kind === 'refund' ? 'txRefund' : 'txVoidItem')} #{o.order_number}</h2>
          <div class="text-xs text-[var(--om-text-secondary)]">{language.t('txRemaining')} {formatRupiah(remaining(o))}</div>
        </div>
        <button class="btn-outline px-4 py-2" onclick={() => (dialog = null)}>{language.t('close')}</button>
      </div>
      <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
        {#if dError}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{dError}</div>{/if}
        {#if dialog.kind === 'refund'}
          <label class="block">
            <span class={label}>{language.t('txRefundAmount')} (Rp)</span>
            <input class="field" type="text" inputmode="numeric" value={dAmount} oninput={(e) => { dAmount = formatDigits(e.currentTarget.value); e.currentTarget.value = dAmount; }} />
          </label>
        {:else}
          <label class="block">
            <span class={label}>{language.t('txPickLine')}</span>
            <select class="field" bind:value={dLine}>
              {#each (o.items ?? []).filter((i) => leftOf(i) > 0) as i (i.id)}<option value={i.id}>{i.item_name_snapshot} ({leftOf(i)}×)</option>{/each}
            </select>
          </label>
          <label class="block"><span class={label}>{language.t('txVoidQty')}</span><input class="field" type="text" inputmode="numeric" bind:value={dQty} /></label>
        {/if}
        <div>
          <span class={label}>{language.t('txRefundMethod')}</span>
          <div class="flex flex-wrap gap-1.5">
            <button class={chip(dMethod === 'CASH')} style="min-height: 40px" onclick={() => (dMethod = 'CASH')}>{language.t('txMethodCash')}</button>
            <button class={chip(dMethod === 'TRANSFER')} style="min-height: 40px" onclick={() => (dMethod = 'TRANSFER')}>{language.t('txMethodTransfer')}</button>
          </div>
          {#if dMethod === 'CASH' && !hasShift}<div class="mt-1 text-xs text-[var(--om-danger)]">{language.t('txNeedShift')}</div>{/if}
        </div>
        <div>
          <span class={label}>{language.t('txReason')}</span>
          <div class="flex flex-wrap gap-1.5">{#each REASONS as r}<button class={chip(dReason === r)} style="min-height: 40px" onclick={() => (dReason = r)}>{r}</button>{/each}</div>
        </div>
        {#if dReason}<input class="field" maxlength="150" placeholder={language.t('txRefundNote')} bind:value={dNote} />{/if}
      </div>
      <div class="flex items-center justify-end gap-3 border-t border-[var(--om-border)] p-5">
        <button class="btn-outline" onclick={() => (dialog = null)}>{language.t('cancel')}</button>
        <button class="btn-primary disabled:opacity-50" disabled={dSaving || (dMethod === 'CASH' && !hasShift)} onclick={submitDialog}>{dSaving ? language.t('saving') : language.t(dialog.kind === 'refund' ? 'txRefund' : 'txVoidItem')}</button>
      </div>
    </section>
  </div>
{/if}
