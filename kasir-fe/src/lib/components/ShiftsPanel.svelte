<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { PaginatedResponse, Shift, ShiftDetail, ShiftStatus, ShiftSummary } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import type { MessageKey } from '$lib/i18n/messages';
  import { session } from '$lib/stores/session.svelte';
  import { shiftState } from '$lib/stores/shift.svelte';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { PAGE_SIZE } from '$lib/utils/paging';
  import { chip, CHIP_ROW, seg, SEG_GROUP } from '$lib/utils/ui';
  import Pagination from './Pagination.svelte';

  const PERIODS: { id: number; key: MessageKey }[] = [
    { id: 0, key: 'finToday' },
    { id: 7, key: 'fin7d' },
    { id: 30, key: 'fin30d' },
    { id: 60, key: 'fin60d' }
  ];
  const STATUS: Record<ShiftStatus, { key: MessageKey; cls: string }> = {
    OPEN: { key: 'shiftStatusOpen', cls: 'bg-blue-100 text-blue-800' },
    CLOSED: { key: 'shiftStatusClosed', cls: 'bg-amber-100 text-amber-800' },
    REVIEWED: { key: 'shiftStatusReviewed', cls: 'bg-[var(--light-brown)] text-[var(--om-brand)]' }
  };

  const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const daysAgo = (n: number) => iso(new Date(Date.now() - n * 86400000));
  const signed = (n: number) => (n > 0 ? '+' : n < 0 ? '−' : '') + formatRupiah(Math.abs(n));

  let period = $state(30);
  let filter = $state<'all' | ShiftStatus | 'big'>('all');
  let rows = $state<Shift[]>([]);
  let error = $state('');
  let loading = $state(false);
  let detail = $state<ShiftDetail | null>(null);
  let reviewNote = $state('');
  let saving = $state(false);

  let threshold = $derived(shiftState.current?.variance_threshold ?? 0);
  let page = $state(1);
  let summary = $state<ShiftSummary | null>(null);
  let total = $state(0);
  let kpis = $derived([
    { label: language.t('shiftKpiShifts'), value: String(summary?.count ?? 0), cls: '' },
    { label: language.t('shiftKpiVariance'), value: signed(summary?.total_variance ?? 0), cls: '' },
    { label: language.t('shiftKpiBig'), value: String(summary?.big_count ?? 0), cls: 'text-red-700' },
    { label: language.t('shiftKpiReview'), value: String(summary?.review_count ?? 0), cls: 'text-amber-700' }
  ]);

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    try {
      const from = daysAgo(period);
      const q = new URLSearchParams({ date_from: from, limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
      if (filter === 'big') q.set('big_variance', 'true');
      else if (filter !== 'all') q.set('status', filter);
      const [res, sum] = await Promise.all([
        api.get<PaginatedResponse<Shift>>(`/stores/${storeId}/shifts?${q}`),
        api.get<ShiftSummary>(`/stores/${storeId}/shifts/summary?date_from=${from}`)
      ]);
      rows = paginatedItems(res);
      total = res.total;
      summary = sum;
      if (!rows.length && page > 1) page = Math.max(1, Math.ceil(total / PAGE_SIZE));
      error = '';
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void session.selectedStore?.id;
    void period;
    void filter;
    void page;
    untrack(() => {
      void load();
      void shiftState.load();
    });
  });

  async function open(s: Shift) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      detail = await api.get<ShiftDetail>(`/stores/${storeId}/shifts/${s.id}`);
      reviewNote = detail.review_note ?? '';
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    }
  }

  async function review() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !detail) return;
    saving = true;
    try {
      await api.post(`/stores/${storeId}/shifts/${detail.id}/review`, { note: reviewNote.trim() || null });
      detail = null;
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  const varCls = (v: number | null) =>
    !v ? '' : Math.abs(v) > threshold ? 'text-red-700' : v < 0 ? 'text-amber-700' : 'text-[var(--om-brand)]';
  const FILTERS: { id: typeof filter; key: MessageKey }[] = [
    { id: 'all', key: 'shiftFilterAll' },
    { id: 'OPEN', key: 'shiftStatusOpen' },
    { id: 'CLOSED', key: 'shiftStatusClosed' },
    { id: 'REVIEWED', key: 'shiftStatusReviewed' },
    { id: 'big', key: 'shiftBigVar' }
  ];
</script>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}

<div class="mb-4 {SEG_GROUP}" role="group">
  {#each PERIODS as p (p.id)}<button class={seg(period === p.id)} style="height: var(--om-tap)" aria-pressed={period === p.id} onclick={() => { period = p.id; page = 1; }}>{language.t(p.key)}</button>{/each}
</div>

<div class="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
  {#each kpis as k (k.label)}
    <section class="card p-4"><div class="text-xs text-[var(--text-muted)]">{k.label}</div><div class="mt-1 text-2xl font-bold tabular-nums {k.cls}">{k.value}</div></section>
  {/each}
</div>

<div class="mb-3 {CHIP_ROW}">
  {#each FILTERS as f (f.id)}<button class="{chip(filter === f.id)} !px-3.5" style="height: var(--om-tap)" onclick={() => { filter = f.id; page = 1; }}>{language.t(f.key)}</button>{/each}
</div>

<div class="card overflow-hidden" class:opacity-60={loading}>
  <div class="hidden grid-cols-[1.2fr_1fr_1fr_120px_120px_120px_130px] gap-3 border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
    <div>{language.t('shiftCashier')}</div><div>{language.t('shiftOpenedAt')}</div><div>{language.t('shiftClosedAt')}</div><div class="text-right">{language.t('shiftOpeningBalance')}</div><div class="text-right">{language.t('shiftExpected')}</div><div class="text-right">{language.t('shiftCounted').replace(' (hitungan, Rp)', '').replace(' (counted, Rp)', '')}</div><div class="text-right">{language.t('shiftVariance')}</div>
  </div>
  {#each rows as s (s.id)}
    <div
      class="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 border-b border-[var(--border)] p-3 text-sm transition-colors last:border-0 hover:bg-[var(--cream)] md:grid md:grid-cols-[1.2fr_1fr_1fr_120px_120px_120px_130px] md:px-4"
      role="button"
      tabindex="0"
      onclick={() => open(s)}
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(s); } }}
    >
      <div><div class="font-semibold">{s.opened_by_name ?? '–'}</div><span class="rounded-full px-2 py-0.5 text-xs font-bold {STATUS[s.status].cls}">{language.t(STATUS[s.status].key)}</span></div>
      <div class="text-xs tabular-nums">{formatDateTime(s.opened_at)}</div>
      <div class="text-xs tabular-nums">{s.closed_at ? formatDateTime(s.closed_at) : '–'}</div>
      <div class="tabular-nums md:text-right">{formatRupiah(s.opening_cash)}</div>
      <div class="tabular-nums md:text-right">{s.expected_cash != null ? formatRupiah(s.expected_cash) : '–'}</div>
      <div class="tabular-nums md:text-right">{s.counted_cash != null ? formatRupiah(s.counted_cash) : '–'}</div>
      <div class="font-bold tabular-nums md:text-right {varCls(s.variance)}">{s.variance != null ? (s.variance ? signed(s.variance) : language.t('shiftExact')) : '–'}</div>
    </div>
  {/each}
  {#if !rows.length && !loading}<div class="p-9 text-center text-[var(--text-muted)]">{language.t('shiftNoShifts')}</div>{/if}
</div>
<Pagination {page} {total} {loading} onPage={(p) => (page = p)} />

{#if detail}
  {@const d = detail}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) detail = null; }}>
    <section class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font truncate text-2xl font-bold text-[var(--espresso)]">{d.opened_by_name ?? '–'}</h2>
          <div class="text-xs text-[var(--text-muted)]">{formatDateTime(d.opened_at)}{d.closed_at ? ` → ${formatDateTime(d.closed_at)}` : ''}</div>
        </div>
        <button class="btn-outline px-4 py-2" onclick={() => (detail = null)}>{language.t('close')}</button>
      </div>
      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 text-sm">
        <div class="space-y-1 rounded-xl bg-[var(--cream)] p-3">
          <div class="flex justify-between"><span class="text-[var(--text-muted)]">{language.t('shiftOpeningBalance')}</span><span class="tabular-nums">{formatRupiah(d.opening_cash)}</span></div>
          {#if d.carry_expected != null && d.carry_expected !== d.opening_cash}
            <div class="flex justify-between text-xs"><span class="text-[var(--text-muted)]">{language.t('shiftCarryGap')} ({language.t('shiftEstimate')} {formatRupiah(d.carry_expected)})</span><span class="tabular-nums {varCls(d.opening_cash - d.carry_expected)}">{signed(d.opening_cash - d.carry_expected)}</span></div>
          {/if}
          <div class="flex justify-between"><span class="text-[var(--text-muted)]">+ {language.t('shiftCashSales')}</span><span class="tabular-nums">{formatRupiah(d.cash_sales)}</span></div>
          {#if d.cash_refunds}<div class="flex justify-between"><span class="text-[var(--text-muted)]">− {language.t('shiftCashRefunds')}</span><span class="tabular-nums">{formatRupiah(d.cash_refunds)}</span></div>{/if}
          <div class="flex justify-between"><span class="text-[var(--text-muted)]">+ {language.t('shiftCashIn')}</span><span class="tabular-nums">{formatRupiah(d.cash_in)}</span></div>
          <div class="flex justify-between"><span class="text-[var(--text-muted)]">− {language.t('shiftCashOut')}</span><span class="tabular-nums">{formatRupiah(d.cash_out)}</span></div>
          <div class="flex justify-between border-t border-[var(--border)] pt-1 font-bold"><span>{language.t('shiftExpected')}</span><span class="tabular-nums">{formatRupiah(d.expected_cash ?? 0)}</span></div>
          {#if d.counted_cash != null}
            <div class="flex justify-between font-bold"><span>{language.t('shiftCashOnHand')}</span><span class="tabular-nums">{formatRupiah(d.counted_cash)}</span></div>
            <div class="flex justify-between font-bold {varCls(d.variance)}"><span>{language.t('shiftVariance')}</span><span class="tabular-nums">{d.variance ? signed(d.variance) : language.t('shiftExact')}</span></div>
          {/if}
        </div>
        {#if d.note}<div><div class="text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('shiftNoteOptional').replace(/ \(.*\)/, '')}</div><div>{d.note}</div></div>{/if}
        {#if d.non_cash.length}
          <div>
            <div class="mb-1 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('shiftNonCash')}</div>
            {#each d.non_cash as n (n.method)}<div class="flex justify-between"><span>{n.method} · {n.count}</span><span class="tabular-nums">{formatRupiah(n.total)}</span></div>{/each}
          </div>
        {/if}
        <div>
          <div class="mb-1 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('shiftMovements')}</div>
          {#each d.movements as m (m.id)}
            <div class="flex justify-between gap-3 border-b border-[var(--border)] py-1.5 last:border-0">
              <span class="min-w-0"><span class="font-medium">{m.category}</span> <span class="text-[var(--text-muted)]">{m.reason}</span></span>
              <span class="shrink-0 font-semibold tabular-nums {m.type === 'IN' ? 'text-[var(--om-brand)]' : 'text-red-700'}">{m.type === 'IN' ? '+' : '−'}{formatRupiah(m.amount)}</span>
            </div>
          {:else}
            <div class="text-[var(--text-muted)]">{language.t('shiftNoMovements')}</div>
          {/each}
        </div>
        {#if d.status === 'CLOSED'}
          <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('shiftReviewNote')}</span><input class="field" maxlength="300" bind:value={reviewNote} /></label>
        {:else if d.review_note}
          <div><div class="text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('shiftStatusReviewed')}</div><div>{d.review_note}</div></div>
        {/if}
      </div>
      {#if d.status === 'CLOSED'}
        <div class="flex justify-end border-t border-[var(--border)] p-5"><button class="btn-primary disabled:opacity-50" disabled={saving} onclick={review}>{saving ? language.t('saving') : language.t('shiftMarkReviewed')}</button></div>
      {/if}
    </section>
  </div>
{/if}
