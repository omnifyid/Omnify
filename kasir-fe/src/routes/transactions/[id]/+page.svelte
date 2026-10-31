<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { api } from '$lib/api/client';
  import type { Order, OrderStatus } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { printEscPos, canPrint } from '$lib/utils/bluetooth-printer';
  import { buildKitchenTicketBytes, buildReceiptBytes } from '$lib/utils/escpos';

  let order = $state<Order | null>(null);
  let error = $state('');
  let success = $state('');
  let loading = $state(false);
  let savingStatus = $state<OrderStatus | null>(null);
  let loadedKey = $state('');

  let receiptOpen = $state(false);
  let ticketOpen = $state(false);
  let btPrinting = $state(false);
  let btError = $state('');

  let orderId = $derived($page.params.id);
  let subtotal = $derived(order?.subtotal ?? order?.items?.reduce((sum, item) => sum + (item.line_total ?? 0), 0) ?? 0);
  let discountAmount = $derived(order?.discount_amount ?? 0);
  let itemDiscountTotal = $derived(order ? (order.items ?? []).reduce((sum, i) => sum + (i.item_discount_amount ?? 0), 0) : 0);

  function statusBadgeClass(status: string) {
    if (status === 'COMPLETED') return 'bg-green-100 text-green-700';
    if (status === 'CANCELLED') return 'bg-red-100 text-red-600';
    return 'bg-amber-100 text-amber-700';
  }

  function paymentBadgeClass(method: string) {
    if (method === 'CASH') return 'bg-[var(--light-brown)] text-[var(--espresso)]';
    if (method === 'QRIS') return 'bg-blue-100 text-blue-700';
    if (method === 'CARD') return 'bg-purple-100 text-purple-700';
    return 'bg-gray-100 text-gray-600';
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

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !orderId) return;
    loadedKey = `${storeId}:${orderId}`;
    loading = true;
    error = '';
    try {
      order = await api.get<Order>(`/stores/${storeId}/orders/${orderId}`);
      if ($page.url.searchParams.get('receipt') === '1') openReceipt();
      if ($page.url.searchParams.get('ticket') === '1') openTicket();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('transactionNotFound');
    } finally {
      loading = false;
    }
  }

  async function updateStatus(status: 'CONFIRMED' | 'COMPLETED' | 'CANCELLED') {
    const storeId = session.selectedStore?.id;
    if (!storeId || !order) return;
    savingStatus = status;
    error = '';
    success = '';
    try {
      order = await api.patch<Order>(`/stores/${storeId}/orders/${order.id}/status`, { status });
      success = `${language.t('orderMarkedAs')} ${status.toLowerCase()}.`;
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      savingStatus = null;
    }
  }

  function openReceipt() { btError = ''; receiptOpen = true; }
  function closeReceipt() { receiptOpen = false; }
  function openTicket() { btError = ''; ticketOpen = true; }
  function closeTicket() { ticketOpen = false; }

  const whereLabel = (o: Order) =>
    o.channel ? o.channel : o.order_type === 'DINE_IN' ? `${language.t('txDineIn')}${o.table_number ? ` · ${o.table_number}` : ''}` : language.t('txTakeAway');

  async function handleTicketBtPrint() {
    if (!order) return;
    btPrinting = true;
    btError = '';
    try {
      await printEscPos(buildKitchenTicketBytes(order, session.selectedStore?.name ?? 'Kasir', whereLabel(order)));
    } catch (err) {
      btError = err instanceof Error ? err.message : language.t('error');
    } finally {
      btPrinting = false;
    }
  }

  async function handleBtPrint() {
    if (!order) return;
    btPrinting = true;
    btError = '';
    try {
      const store = session.selectedStore;
      const rawLogo = store?.show_logo !== false ? (store?.logo_url ?? null) : null;
      const bytes = await buildReceiptBytes(order, store?.name ?? 'Kasir', 0, {
        header: store?.receipt_header,
        footer: store?.receipt_footer,
        logoUrl: rawLogo
      });
      await printEscPos(bytes);
    } catch (err) {
      btError = err instanceof Error ? err.message : language.t('error');
    } finally {
      btPrinting = false;
    }
  }

  $effect(() => {
    const storeId = session.selectedStore?.id;
    const key = storeId && orderId ? `${storeId}:${orderId}` : '';
    if (key && key !== loadedKey) void load();
  });
</script>

<svelte:head><title>{language.t('transactions')} | Kasir</title></svelte:head>

<!-- Back nav -->
<button
  class="mb-5 flex items-center gap-1.5 text-sm font-bold text-[var(--text-muted)] transition-colors hover:text-[var(--espresso)]"
  onclick={() => goto('/transactions')}
>
  <span class="ms !text-[16px]" aria-hidden="true">arrow_back</span>
  {language.t('transactions')}
</button>

<div class="mb-6">
  <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('transactions')}</h1>
  <p class="text-[var(--text-muted)]">{language.t('receipt')} · {language.t('status')}</p>
</div>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}
{#if success}
  <div class="mb-5 rounded-xl border border-green-200 bg-green-50 p-3 text-green-700">{success}</div>
{/if}

{#if order}
  <div class="grid gap-5 lg:grid-cols-[1fr_300px]">
    <!-- Left: order summary + items -->
    <div class="space-y-5">
      <!-- Order header card -->
      <div class="card px-4 py-3">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 class="display-font truncate text-2xl font-bold text-[var(--espresso)]">{order.order_number ?? order.id.slice(0, 8)}</h2>
            <p class="text-xs text-[var(--text-muted)]">{formatDateTime(order.created_at)}</p>
            <span class="mt-1.5 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold {statusBadgeClass(order.status)}">{order.status}</span>
          </div>
          <div class="shrink-0 text-right">
            <div class="font-bold text-[var(--warm-brown)]">{formatRupiah(order.total_amount)}</div>
            <span class="mt-1 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold {paymentBadgeClass(order.payment_method)}">{order.payment_method}</span>
          </div>
        </div>

        {#if order.notes || order.discount_code_snapshot}
          <div class="mt-3 border-t border-[var(--border)] pt-3 text-xs text-[var(--text-muted)]">
            {#if order.discount_code_snapshot}
              <span>{language.t('discounts')}: <span class="font-mono font-bold text-[var(--espresso)]">{order.discount_code_snapshot}</span></span>
            {/if}
            {#if order.notes}
              {#if order.discount_code_snapshot}<span class="mx-2">·</span>{/if}
              <span>{language.t('notes')}: <span class="text-[var(--espresso)]">{order.notes}</span></span>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Items card -->
      <div class="card overflow-hidden">
        <div class="border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('items')}</h2>
        </div>

        <div class="hidden grid-cols-[1fr_60px_120px_110px] border-b border-[var(--border)] px-4 py-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
          <div>{language.t('item')}</div>
          <div class="text-center">{language.t('quantity')}</div>
          <div class="text-right">{language.t('price')}</div>
          <div class="text-right">{language.t('total')}</div>
        </div>

        {#each order.items ?? [] as item}
          {@const modifiers = [snapshotNames(item.options_snapshot), snapshotNames(item.addons_snapshot)].filter(Boolean).join(' · ')}
          <div class="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3 last:border-0 md:grid md:grid-cols-[1fr_60px_120px_110px] md:items-center">
            <div class="min-w-0 flex-1">
              <div class="font-bold text-[var(--espresso)]">{item.item_name_snapshot}</div>
              {#if modifiers}
                <div class="mt-0.5 text-xs text-[var(--text-muted)]">{modifiers}</div>
              {/if}
              <div class="mt-1 text-xs text-[var(--text-muted)] md:hidden">
                ×{item.quantity} · {formatRupiah(item.unit_price_snapshot + (item.addon_total_snapshot ?? 0))} / {language.t('item')}
              </div>
            </div>
            <div class="hidden text-center text-sm font-bold text-[var(--text-muted)] md:block">×{item.quantity}</div>
            <div class="hidden text-right text-sm text-[var(--text-muted)] md:block">{formatRupiah(item.unit_price_snapshot + (item.addon_total_snapshot ?? 0))}</div>
            <div class="shrink-0 text-right font-bold text-[var(--warm-brown)]">{formatRupiah(item.line_total ?? 0)}</div>
          </div>
        {:else}
          <div class="p-5 text-sm text-[var(--text-muted)]">{language.t('noItemsFound')}</div>
        {/each}

        <!-- Totals footer -->
        <div class="space-y-2 border-t border-[var(--border)] bg-[var(--cream)] px-4 py-4">
          <div class="flex justify-between text-sm">
            <span class="text-[var(--text-muted)]">{language.t('subtotal')}</span>
            <span class="font-bold text-[var(--espresso)]">{formatRupiah(subtotal)}</span>
          </div>
          {#if discountAmount > 0}
            <div class="flex justify-between text-sm">
            <span class="text-[var(--text-muted)]">{language.t('discounts')}</span>
              <span class="font-bold text-red-600">–{formatRupiah(discountAmount)}</span>
            </div>
          {/if}
          <div class="flex justify-between border-t border-[var(--border)] pt-3">
            <span class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('total')}</span>
            <span class="display-font text-xl font-bold text-[var(--warm-brown)]">{formatRupiah(order.total_amount)}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: actions -->
    <div class="space-y-4">
      <!-- Print receipt -->
      <div class="card p-5">
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('receipt')}</h2>
        <p class="mt-1 text-sm text-[var(--text-muted)]">{language.t('printReceipt')}</p>
        <button
          class="btn-primary mt-4 flex w-full items-center justify-center gap-2"
          onclick={openReceipt}
        >
          <span class="ms !text-[16px]" aria-hidden="true">print</span>
          {language.t('printReceipt')}
        </button>
      </div>

      <!-- Status -->
      <div class="card p-5">
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('status')}</h2>
        <p class="mt-1 text-sm text-[var(--text-muted)]">
          {#if order.status === 'PENDING'}
            {language.t('updateStatusConfirmHelp')}
          {:else if order.status === 'CONFIRMED'}
            {language.t('updateStatusCompleteHelp')}
          {:else}
            {language.t('orderAlready')} {order.status.toLowerCase()}.
          {/if}
        </p>

        {#if order.status === 'PENDING' || order.status === 'CONFIRMED'}
          <div class="mt-4 space-y-3">
            {#if order.status === 'PENDING'}
              <button
                class="flex w-full items-center justify-center gap-2 rounded-full bg-amber-500 px-4 py-3 text-sm font-bold text-white transition hover:bg-amber-600 disabled:opacity-50"
                disabled={savingStatus !== null}
                onclick={() => updateStatus('CONFIRMED')}
              >
                <span class="ms !text-[16px]" aria-hidden="true">check_circle</span>
              {savingStatus === 'CONFIRMED' ? language.t('processing') : language.t('confirm')}
              </button>
            {/if}
            <button
              class="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-50"
              disabled={savingStatus !== null}
              onclick={() => updateStatus('COMPLETED')}
            >
              <span class="ms !text-[16px]" aria-hidden="true">check_circle</span>
              {savingStatus === 'COMPLETED' ? language.t('processing') : language.t('complete')}
            </button>
            <button
              class="flex w-full items-center justify-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
              disabled={savingStatus !== null}
              onclick={() => updateStatus('CANCELLED')}
            >
              <span class="ms !text-[16px]" aria-hidden="true">block</span>
              {savingStatus === 'CANCELLED' ? language.t('processing') : language.t('cancel')}
            </button>
          </div>
        {:else}
          <p class="mt-4 text-center text-xs text-[var(--text-muted)]">
            {language.t('orderAlready')} {order.status.toLowerCase()}.
          </p>
        {/if}
      </div>

      {#if order.staff_name}
        <div class="card px-4 py-3">
          <div class="text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('servedBy')}</div>
          <div class="mt-1 font-bold text-[var(--espresso)]">{order.staff_name}</div>
        </div>
      {/if}
    </div>
  </div>
{:else if loading}
  <div class="card p-8 text-center text-sm text-[var(--text-muted)]">{language.t('loading')}</div>
{:else}
  <div class="card p-8 text-center text-sm text-[var(--text-muted)]">{language.t('transactionNotFound')}</div>
{/if}

<!-- ─── Receipt modal ─────────────────────────────────────────────── -->
{#if receiptOpen && order}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeReceipt(); }}
  >
    <section
      class="receipt-modal flex max-h-[90vh] w-full max-w-xs flex-col overflow-hidden rounded-t-3xl bg-white md:rounded-3xl"
      role="dialog"
      aria-modal="true"
    >
      <div class="no-print flex justify-end px-3 pt-3">
        <button class="grid h-8 w-8 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeReceipt} aria-label={language.t('close')}><span class="ms !text-[16px]" aria-hidden="true">close</span></button>
      </div>
      <!-- Receipt content (printed) -->
      <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5 text-center font-mono text-sm">
        {#if session.selectedStore?.show_logo !== false && session.selectedStore?.logo_url}
          <img src={session.selectedStore.logo_url} alt="logo" class="mx-auto mb-2 h-12 w-auto object-contain" />
        {/if}
        <div class="text-base font-bold">{session.selectedStore?.name ?? 'Kasir'}</div>
        {#if session.selectedStore?.receipt_header?.trim()}
          <div class="mt-1 text-xs text-gray-500">{session.selectedStore.receipt_header}</div>
        {/if}
        <div class="mt-2 text-xs text-gray-500">{formatDateTime(order.created_at)}</div>
        <div class="text-xs font-bold">#{order.order_number ?? order.id}</div>

        <div class="my-3 border-t border-dashed border-gray-300"></div>

        <div class="space-y-1.5 text-left">
          {#each order.items ?? [] as item}
            {@const mods = [snapshotNames(item.options_snapshot), snapshotNames(item.addons_snapshot)].filter(Boolean).join(', ')}
            <div>
              <div class="flex justify-between gap-2">
                <span class="font-bold">{item.item_name_snapshot} <span class="font-normal text-gray-500">×{item.quantity}</span></span>
                <span class="shrink-0">{formatRupiah(item.line_total ?? 0)}</span>
              </div>
              {#if mods}<div class="text-xs text-gray-400">{mods}</div>{/if}
              {#if (item.item_discount_amount ?? 0) > 0}
                <div class="text-xs text-red-500">–{formatRupiah(item.item_discount_amount ?? 0)} {language.t('discounts')}</div>
              {/if}
            </div>
          {/each}
        </div>

        <div class="my-3 border-t border-dashed border-gray-300"></div>

        <div class="space-y-1 text-left text-xs">
          {#if discountAmount > 0 || itemDiscountTotal > 0 || (order.service_amount ?? 0) > 0 || (order.pb1_amount ?? 0) > 0}
            <div class="flex justify-between">
              <span class="text-gray-500">{language.t('subtotal')}</span>
              <span>{formatRupiah(subtotal)}</span>
            </div>
          {/if}
          {#if itemDiscountTotal > 0}
            <div class="flex justify-between text-red-500">
              <span>{language.t('discounts')}</span>
              <span>–{formatRupiah(itemDiscountTotal)}</span>
            </div>
          {/if}
          {#if discountAmount > 0}
            <div class="flex justify-between text-red-500">
              <span>{language.t('discounts')}{order.discount_code_snapshot ? ` (${order.discount_code_snapshot})` : ''}</span>
              <span>–{formatRupiah(discountAmount)}</span>
            </div>
          {/if}
          {#if (order.service_amount ?? 0) > 0}
            <div class="flex justify-between"><span class="text-gray-500">{language.t('serviceLabel')}</span><span>{formatRupiah(order.service_amount ?? 0)}</span></div>
          {/if}
          {#if (order.pb1_amount ?? 0) > 0}
            <div class="flex justify-between"><span class="text-gray-500">{language.t('pb1Label')}</span><span>{formatRupiah(order.pb1_amount ?? 0)}</span></div>
          {/if}
          <div class="flex justify-between border-t border-dashed border-gray-300 pt-1 text-base font-bold">
            <span>{language.t('total')}</span>
            <span>{formatRupiah(order.total_amount)}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">{language.t('payment')}</span>
            <span class="font-bold">{order.payment_method}</span>
          </div>
        </div>

        <div class="my-3 border-t border-dashed border-gray-300"></div>

        {#if session.selectedStore?.receipt_footer?.trim()}
          <div class="text-xs text-gray-500">{session.selectedStore.receipt_footer}</div>
        {:else}
          <div class="text-xs text-gray-500">{language.t('thankYou')}</div>
        {/if}
      </div>

      {#if btError}
        <div class="px-5 pb-2 text-center text-xs text-red-600">{btError}</div>
      {/if}

      <!-- Actions (hidden on print) -->
      <div class="no-print flex gap-2 border-t border-[var(--border)] p-4">
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

<!-- ─── Kitchen ticket modal ──────────────────────────────────────── -->
{#if ticketOpen && order}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) closeTicket(); }}>
    <section class="receipt-modal flex max-h-[90vh] w-full max-w-xs flex-col overflow-hidden rounded-t-3xl bg-white md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="no-print flex justify-end px-3 pt-3">
        <button class="grid h-8 w-8 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)]" onclick={closeTicket} aria-label={language.t('close')}><span class="ms !text-[16px]" aria-hidden="true">close</span></button>
      </div>
      <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5 font-mono text-sm">
        <div class="text-center">
          <div class="text-base font-bold">{language.t('txTicket').toUpperCase()}</div>
          <div class="text-xs text-gray-500">{session.selectedStore?.name ?? 'Kasir'}</div>
          <div class="my-1 text-2xl font-bold">#{order.order_number ?? order.id.slice(0, 8)}</div>
          <div class="text-xs text-gray-500">{formatDateTime(order.created_at)}</div>
        </div>
        <div class="my-3 border-t border-dashed border-gray-300"></div>
        <div class="font-bold">{whereLabel(order)}</div>
        {#if order.customer_name}<div>{order.customer_name}</div>{/if}
        <div class="my-3 border-t border-dashed border-gray-300"></div>
        <div class="space-y-2">
          {#each order.items ?? [] as item}
            {@const left = item.quantity - (item.void_qty ?? 0)}
            {@const mods = [snapshotNames(item.options_snapshot), snapshotNames(item.addons_snapshot)].filter(Boolean).join(', ')}
            {#if left > 0}
              <div><div class="font-bold">{left}× {item.item_name_snapshot}</div>{#if mods}<div class="pl-5 text-xs text-gray-500">{mods}</div>{/if}</div>
            {/if}
          {/each}
        </div>
        {#if order.notes?.trim()}
          <div class="my-3 border-t border-dashed border-gray-300"></div>
          <div class="text-xs"><span class="font-bold">{language.t('txTicketNote')}:</span> {order.notes}</div>
        {/if}
      </div>
      {#if btError}<div class="px-5 pb-2 text-center text-xs text-red-600">{btError}</div>{/if}
      <div class="no-print flex gap-2 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={() => window.print()}>{language.t('printReceipt')}</button>
        {#if canPrint()}
          <button class="btn-primary flex-1" onclick={handleTicketBtPrint} disabled={btPrinting}>{btPrinting ? language.t('processing') : language.t('bluetooth')}</button>
        {/if}
      </div>
    </section>
  </div>
{/if}

<style>
  @media print {
    :global(body > *:not(.receipt-modal)) { display: none !important; }
    .receipt-modal { box-shadow: none !important; border-radius: 0 !important; max-height: none !important; }
    .no-print { display: none !important; }
  }
</style>
