<script lang="ts">
  import { api } from '$lib/api/client';
  import type { DashboardReport, PaymentReport, SalesReport, TopItemReport } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { formatRupiah } from '$lib/utils/format';

  const now = new Date();
  let selectedMonth = $state(now.getMonth() + 1);
  let selectedYear = $state(now.getFullYear());

  const MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  let monthLabels = $derived(
    Array.from({ length: 12 }, (_, i) =>
      new Intl.DateTimeFormat(language.current === 'id' ? 'id-ID' : 'en-US', { month: 'long' }).format(new Date(2024, i, 1))
    )
  );

  const YEARS = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);

  function dateRange() {
    const pad = (n: number) => String(n).padStart(2, '0');
    const lastDay = new Date(selectedYear, selectedMonth, 0).getDate();
    return {
      from_date: `${selectedYear}-${pad(selectedMonth)}-01`,
      to_date: `${selectedYear}-${pad(selectedMonth)}-${pad(lastDay)}`
    };
  }

  function withDateRange(path: string) {
    const { from_date, to_date } = dateRange();
    return `${path}?from_date=${from_date}&to_date=${to_date}`;
  }

  let sales = $state<SalesReport | null>(null);
  let topItems = $state<TopItemReport[]>([]);
  let payments = $state<PaymentReport[]>([]);
  let loading = $state(false);
  let error = $state('');
  let loadedStoreId = $state<string | null>(null);

  function normalizeTopItems(response: TopItemReport[] | { items: TopItemReport[] }) {
    return Array.isArray(response) ? response : response.items;
  }

  function normalizePayments(response: PaymentReport[] | { breakdown: PaymentReport[] }) {
    return Array.isArray(response) ? response : response.breakdown;
  }

  async function loadDashboard(storeId: string) {
    try {
      const dashboard = await api.get<DashboardReport>(withDateRange(`/stores/${storeId}/reports/dashboard`));
      sales = dashboard.sales;
      topItems = dashboard.top_items;
      payments = dashboard.payments;
    } catch {
      const [salesReport, topItemsReport, paymentReport] = await Promise.all([
        api.get<SalesReport>(withDateRange(`/stores/${storeId}/reports/sales`)),
        api.get<TopItemReport[] | { items: TopItemReport[] }>(withDateRange(`/stores/${storeId}/reports/top-items`)),
        api.get<PaymentReport[] | { breakdown: PaymentReport[] }>(withDateRange(`/stores/${storeId}/reports/by-payment`))
      ]);
      sales = salesReport;
      topItems = normalizeTopItems(topItemsReport);
      payments = normalizePayments(paymentReport);
    }
  }

  async function load(storeId = session.selectedStore?.id) {
    if (!storeId) return;
    loadedStoreId = storeId;
    loading = true;
    error = '';
    try {
      await loadDashboard(storeId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load dashboard';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const storeId = session.selectedStore?.id;
    if (storeId && storeId !== loadedStoreId) void load(storeId);
  });

  function applyFilter() {
    loadedStoreId = null;
    void load();
  }

  let revenue = $derived(sales?.total_revenue ?? 0);
  let orderCount = $derived(sales?.order_count ?? sales?.total_orders ?? 0);
  let average = $derived(sales?.avg_order_value ?? (orderCount ? Math.round(revenue / orderCount) : 0));

  let maxItemRevenue = $derived(
    topItems.length ? Math.max(...topItems.map(i => i.total_revenue ?? i.revenue ?? 0)) : 1
  );

  let totalPaymentRevenue = $derived(
    payments.reduce((sum, p) => sum + (p.total_revenue ?? p.revenue ?? 0), 0) || 1
  );

  const PAY_DOT: Record<string, string> = {
    CASH: 'var(--om-brand-bright)',
    CARD: 'var(--om-info)',
    QRIS: 'var(--om-warning-solid)',
    TRANSFER: 'var(--om-text-secondary)'
  };
  let totalPaymentOrders = $derived(payments.reduce((sum, p) => sum + (p.order_count ?? 0), 0));
  let totalPaymentAmount = $derived(payments.reduce((sum, p) => sum + (p.total_revenue ?? p.revenue ?? 0), 0));
</script>

<svelte:head><title>{language.t('dashboard')} | Omnify</title></svelte:head>

<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
  <p class="text-[14px] text-[var(--om-text-secondary)]">{monthLabels[selectedMonth - 1]} {selectedYear}</p>
  <div class="flex items-center gap-2">
    <select class="field w-auto rounded-[10px] py-2 text-[14px] font-semibold" bind:value={selectedMonth} onchange={applyFilter} disabled={loading} aria-label={language.t('period')}>
      {#each monthLabels as month, i}<option value={i + 1}>{month}</option>{/each}
    </select>
    <select class="field w-auto rounded-[10px] py-2 text-[14px] font-semibold" bind:value={selectedYear} onchange={applyFilter} disabled={loading} aria-label={language.t('period')}>
      {#each YEARS as year}<option value={year}>{year}</option>{/each}
    </select>
    <button class="btn-outline grid w-11 place-items-center px-0" onclick={() => load()} disabled={loading} title={language.t('refresh')} aria-label={language.t('refresh')}>
      <span class="ms {loading ? 'animate-spin' : ''}">refresh</span>
    </button>
  </div>
</div>

{#if error}
  <div role="alert" class="mb-4 flex items-center gap-2 rounded-[12px] border border-[var(--om-danger-tint)] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)]">
    <span class="ms">error</span>{error}
  </div>
{/if}

<div class="grid gap-3.5" style="grid-auto-rows: max-content">
  <section class="grid gap-3 sm:gap-3.5" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr))">
    {#each [
      { label: language.t('totalRevenue'), icon: 'payments', value: formatRupiah(revenue) },
      { label: language.t('orders'), icon: 'receipt_long', value: String(orderCount) },
      { label: `Avg ${language.t('order')}`, icon: 'avg_pace', value: formatRupiah(average) }
    ] as kpi}
      <div class="card p-[18px] max-sm:p-3.5">
        <div class="flex items-center justify-between text-[12px] text-[var(--om-text-secondary)]">
          <span>{kpi.label}</span><span class="ms !text-[20px]">{kpi.icon}</span>
        </div>
        <div class="mt-1.5 text-[24px] font-bold tracking-[-0.02em] max-sm:text-[20px] {loading && !sales ? 'opacity-40' : ''}">{kpi.value}</div>
      </div>
    {/each}
  </section>

  <section class="grid gap-3.5" style="grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr))">
    <div class="card p-5">
      <div class="mb-3 flex items-baseline justify-between">
        <h2 class="text-[16px] font-semibold">{language.t('topItems')}</h2>
        <span class="text-[12px] text-[var(--om-text-secondary)]">{topItems.length} menu</span>
      </div>
      {#each topItems as item, i}
        {@const itemRevenue = item.total_revenue ?? item.revenue ?? 0}
        {@const barPct = maxItemRevenue > 0 ? (itemRevenue / maxItemRevenue) * 100 : 0}
        <div class="flex items-center gap-3 border-t border-[var(--om-divider)] py-2.5 first:border-0">
          <span class="grid h-10 w-10 shrink-0 place-items-center rounded-[10px] bg-[var(--om-fill-muted)] text-[14px] font-semibold">{i + 1}</span>
          <div class="min-w-0 flex-1">
            <div class="truncate text-[16px] font-medium">{item.item_name ?? item.name ?? 'Item'}</div>
            <div class="mt-1.5 h-[5px] overflow-hidden rounded-full bg-[var(--om-fill-image)]">
              <div class="h-full rounded-full bg-[var(--om-brand-bright)]" style="width:{barPct}%"></div>
            </div>
          </div>
          <div class="text-right">
            <div class="text-[14px] font-semibold">{formatRupiah(itemRevenue)}</div>
            <div class="text-[12px] text-[var(--om-text-secondary)]">{item.quantity_sold ?? item.quantity ?? 0} sold</div>
          </div>
        </div>
      {:else}
        <p class="text-[16px] text-[var(--om-text-secondary)]">{language.t('noTopItemData')}</p>
      {/each}
    </div>

    <div class="card overflow-hidden">
      <div class="flex items-baseline justify-between p-5 pb-3">
        <h2 class="text-[16px] font-semibold">By {language.t('payment')}</h2>
        <span class="text-[12px] text-[var(--om-text-secondary)]">{payments.length} methods</span>
      </div>
      {#if payments.length}
        <div class="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 border-y border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-5 py-2.5 text-[12px] text-[var(--om-text-secondary)]">
          <span>{language.t('payment')}</span><span class="text-right">{language.t('orders')}</span><span class="text-right">%</span><span class="text-right">Total</span>
        </div>
        {#each payments as payment}
          {@const payRevenue = payment.total_revenue ?? payment.revenue ?? 0}
          {@const pct = Math.round((payRevenue / totalPaymentRevenue) * 100)}
          <div class="grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 border-b border-[var(--om-divider)] px-5 py-3 text-[14px] hover:bg-[var(--om-bg)]">
            <span class="flex items-center gap-2 font-medium">
              <span class="h-2.5 w-2.5 rounded-full" style="background:{PAY_DOT[payment.payment_method?.toUpperCase()] ?? 'var(--om-text-secondary)'}"></span>
              {payment.payment_method}
            </span>
            <span class="text-right">{payment.order_count ?? 0}</span>
            <span class="text-right text-[var(--om-text-secondary)]">{pct}%</span>
            <span class="text-right font-semibold">{formatRupiah(payRevenue)}</span>
          </div>
        {/each}
        <div class="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 bg-[var(--om-surface-sunk)] px-5 py-3 text-[14px] font-semibold">
          <span>Total</span><span class="text-right">{totalPaymentOrders}</span><span class="text-right">100%</span><span class="text-right">{formatRupiah(totalPaymentAmount)}</span>
        </div>
      {:else}
        <p class="px-5 pb-5 text-[16px] text-[var(--om-text-secondary)]">{language.t('noPaymentData')}</p>
      {/if}
    </div>
  </section>
</div>
