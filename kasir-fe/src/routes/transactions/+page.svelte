<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Order, PaginatedResponse, PaymentMethod, OrderStatus } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';

  let orders = $state<Order[]>([]);
  let pendingOrders = $state<Order[]>([]);
  let confirmingId = $state<string | null>(null);
  let error = $state('');
  let loading = $state(false);
  let page = $state(1);
  const limit = 20;
  let total = $state(0);
  let totalPages = $derived(Math.max(1, Math.ceil(total / limit)));

  // Filters
  let filterDate = $state('');
  let filterPayment = $state<PaymentMethod | ''>('');
  let filterStatus = $state<OrderStatus | ''>('');

  const paymentOptions: PaymentMethod[] = ['CASH', 'CARD', 'QRIS', 'TRANSFER'];
  const statusOptions: OrderStatus[] = ['PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED'];

  let hasActiveFilter = $derived(!!filterDate || !!filterPayment || !!filterStatus);

  function buildQuery() {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('offset', String((page - 1) * limit));
    if (filterStatus) params.set('status', filterStatus);
    if (filterPayment) params.set('payment_method', filterPayment);
    if (filterDate) {
      params.set('date_from', filterDate);
      params.set('date_to', filterDate);
    }
    return params.toString();
  }

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    error = '';
    try {
      const [res, pendingRes] = await Promise.all([
        api.get<PaginatedResponse<Order>>(`/stores/${storeId}/orders?${buildQuery()}`),
        api.get<PaginatedResponse<Order>>(`/stores/${storeId}/orders?status=PENDING&limit=50&offset=0`),
      ]);
      orders = paginatedItems(res);
      total = res.total;
      pendingOrders = paginatedItems(pendingRes);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load transactions';
    } finally {
      loading = false;
    }
  }

  async function confirmPending(order: Order) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    confirmingId = order.id;
    try {
      await api.patch(`/stores/${storeId}/orders/${order.id}/status`, { status: 'CONFIRMED' });
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to confirm order';
    } finally {
      confirmingId = null;
    }
  }

  async function applyFilters() {
    page = 1;
    await load();
  }

  async function clearFilters() {
    filterDate = '';
    filterPayment = '';
    filterStatus = '';
    await applyFilters();
  }

  async function goToPage(newPage: number) {
    page = newPage;
    await load();
  }

  function statusBadgeClass(status: string) {
    if (status === 'COMPLETED') return 'bg-[var(--om-brand-tint)] text-[var(--om-brand)]';
    if (status === 'CANCELLED') return 'bg-[var(--om-danger-tint)] text-[var(--om-danger)]';
    if (status === 'PENDING') return 'bg-[var(--om-warning-tint)] text-[var(--om-warning)]';
    return 'bg-[var(--om-info-tint)] text-[var(--om-info)]';
  }

  function paymentBadgeClass(_method: string) {
    return 'bg-[var(--om-grey-tint)] text-[var(--om-ink-2)]';
  }

  $effect(() => {
    if (session.selectedStore?.id) { page = 1; untrack(() => void load()); }
  });
</script>

<svelte:head><title>{language.t('transactions')} | Omnify</title></svelte:head>

<p class="mb-3 text-[14px] text-[var(--om-text-secondary)]">{language.t('transactionsSubtitle')}</p>

<!-- Toolbar: status segmented control + filters -->
<div class="mb-4 flex flex-wrap items-center gap-3">
  <div class="flex max-w-full overflow-x-auto rounded-[11px] bg-[var(--om-fill-muted)] p-1" role="group" aria-label={language.t('status')}>
    {#each ['', ...statusOptions] as s}
      {@const active = filterStatus === s}
      <button
        class="shrink-0 rounded-[8px] px-3.5 text-[14px] transition-colors {active ? 'bg-[var(--om-brand-tint)] font-semibold shadow-[inset_0_0_0_2px_var(--om-brand)]' : 'font-medium text-[var(--om-ink-2)] hover:bg-[var(--om-fill-hover)]'}"
        style="min-height: calc(var(--om-tap) - 8px)"
        aria-pressed={active}
        onclick={() => { filterStatus = s as OrderStatus | ''; applyFilters(); }}
      >{s === '' ? language.t('allStatuses') : s}</button>
    {/each}
  </div>
  <select class="field w-auto rounded-[10px] text-[14px] font-semibold" bind:value={filterPayment} onchange={applyFilters} aria-label={language.t('paymentType')}>
    <option value="">{language.t('allPaymentTypes')}</option>
    {#each paymentOptions as p}<option value={p}>{p}</option>{/each}
  </select>
  <input class="field w-auto rounded-[10px] text-[14px] font-semibold" type="date" bind:value={filterDate} onchange={applyFilters} aria-label={language.t('date')} />
  {#if hasActiveFilter}
    <button class="rounded-[10px] px-3 text-[14px] font-semibold text-[var(--om-brand)] hover:text-[var(--om-ink)]" style="min-height: var(--om-tap)" onclick={clearFilters}>{language.t('clearAll')}</button>
  {/if}
</div>

{#if error}
  <div role="alert" class="mb-4 flex items-center gap-2 rounded-[12px] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)]">
    <span class="ms">error</span>{error}
  </div>
{/if}

<!-- Pending queue -->
{#if pendingOrders.length > 0}
  <div class="mb-4 overflow-hidden rounded-[14px] border border-[var(--om-warning-solid)]/40 bg-[var(--om-warning-tint)]">
    <div class="flex items-center gap-2 border-b border-[var(--om-warning-solid)]/30 px-4 py-3">
      <span class="ms !text-[20px] text-[var(--om-warning)]">warning</span>
      <span class="text-[14px] font-semibold text-[var(--om-warning)]">Pesanan Menunggu Konfirmasi ({pendingOrders.length})</span>
    </div>
    {#each pendingOrders as order}
      <div class="flex flex-wrap items-center gap-3 border-b border-[var(--om-warning-solid)]/20 px-4 py-3 last:border-0">
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-[14px] font-semibold">{order.order_number ?? order.id.slice(0, 8)}</span>
            {#if order.notes}
              <span class="rounded-[20px] bg-white px-2 py-0.5 text-[12px] font-semibold text-[var(--om-warning)]">{order.notes}</span>
            {/if}
          </div>
          <div class="mt-0.5 text-[12px] text-[var(--om-text-secondary)]">{formatDateTime(order.created_at)} · {formatRupiah(order.total_amount)}</div>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <button
            class="btn-primary flex items-center gap-1.5 px-4 text-[14px]"
            disabled={confirmingId === order.id}
            onclick={() => confirmPending(order)}
          >
            <span class="ms !text-[18px]">check_circle</span>
            {confirmingId === order.id ? '…' : 'Konfirmasi'}
          </button>
          <a href={`/transactions/${order.id}`} class="btn-outline flex items-center px-4 text-[14px]">{language.t('detail')}</a>
        </div>
      </div>
    {/each}
  </div>
{/if}

<div class="card overflow-hidden">
  <div class="hidden grid-cols-[160px_1fr_120px_130px_140px_28px] border-b border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-[18px] py-3 text-[12px] text-[var(--om-text-secondary)] lg:grid">
    <div>{language.t('order')}</div>
    <div>{language.t('date')}</div>
    <div>{language.t('payment')}</div>
    <div>{language.t('status')}</div>
    <div class="text-right">{language.t('total')}</div>
    <div></div>
  </div>

  {#each orders as order}
    <a
      href={`/transactions/${order.id}`}
      class="group flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-[var(--om-divider)] px-[18px] py-3 transition-colors last:border-0 hover:bg-[var(--om-bg)] lg:grid lg:grid-cols-[160px_1fr_120px_130px_140px_28px]"
      style="min-height: var(--om-tap)"
      aria-label={`View transaction ${order.order_number ?? order.id}`}
    >
      <div class="min-w-0 flex-1 lg:flex-none">
        <div class="truncate text-[14px] font-semibold">{order.order_number ?? order.id.slice(0, 8)}</div>
        <div class="text-[12px] text-[var(--om-text-secondary)] lg:hidden">{formatDateTime(order.created_at)}</div>
      </div>
      <div class="hidden text-[14px] text-[var(--om-ink-2)] lg:block">{formatDateTime(order.created_at)}</div>
      <div class="order-3 flex w-full items-center gap-1.5 lg:contents">
        <span class="inline-flex w-fit items-center rounded-[20px] px-[9px] py-[3px] text-[12px] font-semibold {paymentBadgeClass(order.payment_method)}">{order.payment_method}</span>
        <span class="inline-flex w-fit items-center rounded-[20px] px-[9px] py-[3px] text-[12px] font-semibold {statusBadgeClass(order.status)}">{order.status}</span>
      </div>
      <div class="text-right text-[16px] font-semibold lg:text-[14px]">{formatRupiah(order.total_amount)}</div>
      <span class="ms hidden text-[var(--om-text-secondary)] opacity-40 transition-opacity group-hover:opacity-100 lg:block">chevron_right</span>
    </a>
  {:else}
    <div class="p-8 text-center text-[16px] text-[var(--om-text-secondary)]">
      {loading ? 'Loading…' : hasActiveFilter ? 'No transactions match the current filter.' : 'No transactions found.'}
    </div>
  {/each}
</div>

{#if totalPages > 1}
  <div class="mt-4 flex items-center justify-between gap-3 text-[14px]">
    <span class="text-[var(--om-text-secondary)]">{language.t('page')} {page} {language.t('of')} {totalPages}</span>
    <div class="flex gap-2">
      <button class="btn-outline px-4" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>{language.t('previous')}</button>
      <button class="btn-outline px-4" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>{language.t('next')}</button>
    </div>
  </div>
{/if}
