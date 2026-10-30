<script lang="ts">
  import { untrack } from 'svelte';
  import { Landmark, Check } from 'lucide-svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { ChannelOverview, OrderChannel, PaginatedResponse, PlatformSettlement, Receivable, ReceivableSelection, SettlementBatch } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { CHANNEL_META } from '$lib/utils/channels';
  import { formatRupiah } from '$lib/utils/format';
  import { chip } from '$lib/utils/ui';
  import Pagination from './Pagination.svelte';

  const META = CHANNEL_META;
  const REASONS = ['Penyesuaian komisi', 'Pesanan dibatalkan platform', 'Biaya promo merchant', 'Biaya iklan/layanan', 'Pembulatan', 'Lain-lain'];

  const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const today = () => iso(new Date());
  const digits = (v: string) => v.replace(/\D/g, '');
  const fmtDate = (d: string) =>
    new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium' }).format(new Date(`${d}T00:00:00`));
  const signed = (n: number) => (n > 0 ? '+' : n < 0 ? '−' : '') + formatRupiah(Math.abs(n));
  const dayDiff = (a: string, b: string) => Math.round((Date.parse(a) - Date.parse(b)) / 86400000);

  let overview = $state<ChannelOverview[]>([]);
  let channel = $state<OrderChannel>('GOFOOD');
  let batches = $state<SettlementBatch[]>([]);
  let batchTotal = $state(0);
  let history = $state<PlatformSettlement[]>([]);
  let historyTotal = $state(0);
  let historyPage = $state(1);
  let batchPage = $state(1);
  const HISTORY_SIZE = 10;
  const MODAL_SIZE = 10;
  let error = $state('');
  let loading = $state(false);

  let formOpen = $state(false);
  // Selection = server-computed base (all receivables up to a date) adjusted by per-row toggles.
  let base = $state<ReceivableSelection>({ ids: [], count: 0, expected: 0 });
  let baseSet = $derived(new Set(base.ids));
  let excluded = $state<Record<string, number>>({});
  let added = $state<Record<string, number>>({});
  let modalRows = $state<Receivable[]>([]);
  let modalTotal = $state(0);
  let modalPage = $state(1);
  let fAmount = $state('');
  let fDate = $state(today());
  let fReason = $state('');
  let fNote = $state('');
  let formError = $state('');
  let saving = $state(false);

  const sum = (m: Record<string, number>) => Object.values(m).reduce((a, n) => a + n, 0);
  let chosenIds = $derived([...base.ids.filter((id) => !(id in excluded)), ...Object.keys(added)]);
  let expected = $derived(base.expected - sum(excluded) + sum(added));
  let amount = $derived(parseInt(digits(fAmount) || '0', 10));
  let diff = $derived(fAmount === '' ? 0 : amount - expected);
  const isChecked = (id: string) => (baseSet.has(id) && !(id in excluded)) || id in added;

  async function loadOverview() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      overview = await api.get<ChannelOverview[]>(`/stores/${storeId}/settlements/overview`);
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    }
  }

  async function loadChannel() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    try {
      const [bat, hist] = await Promise.all([
        api.get<PaginatedResponse<SettlementBatch>>(`/stores/${storeId}/settlements/batches?channel=${channel}&limit=${HISTORY_SIZE}&offset=${(batchPage - 1) * HISTORY_SIZE}`),
        api.get<PaginatedResponse<PlatformSettlement>>(`/stores/${storeId}/settlements?channel=${channel}&limit=${HISTORY_SIZE}&offset=${(historyPage - 1) * HISTORY_SIZE}`)
      ]);
      batches = paginatedItems(bat);
      batchTotal = bat.total;
      history = paginatedItems(hist);
      historyTotal = hist.total;
      error = '';
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  async function loadModalRows() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      const res = await api.get<PaginatedResponse<Receivable>>(`/stores/${storeId}/settlements/receivables?channel=${channel}&limit=${MODAL_SIZE}&offset=${(modalPage - 1) * MODAL_SIZE}`);
      modalRows = paginatedItems(res);
      modalTotal = res.total;
    } catch (err) {
      formError = err instanceof Error ? err.message : language.t('error');
    }
  }

  async function selectUpTo(upTo: string | null) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      base = upTo === 'none'
        ? { ids: [], count: 0, expected: 0 }
        : await api.get<ReceivableSelection>(`/stores/${storeId}/settlements/receivables/selection?channel=${channel}${upTo ? `&up_to=${upTo}` : ''}`);
      excluded = {};
      added = {};
    } catch (err) {
      formError = err instanceof Error ? err.message : language.t('error');
    }
  }

  $effect(() => {
    void session.selectedStore?.id;
    untrack(() => void loadOverview());
  });

  $effect(() => {
    void session.selectedStore?.id;
    void channel;
    void historyPage;
    void batchPage;
    untrack(() => void loadChannel());
  });

  async function openForm(upTo: string | null) {
    fAmount = '';
    fDate = today();
    fReason = '';
    fNote = '';
    formError = '';
    modalPage = 1;
    formOpen = true;
    await Promise.all([selectUpTo(upTo), loadModalRows()]);
  }

  function toggleRow(r: Receivable, on: boolean) {
    if (baseSet.has(r.id)) {
      const { [r.id]: _, ...rest } = excluded;
      excluded = on ? rest : { ...excluded, [r.id]: r.expected_payout };
    } else {
      const { [r.id]: _, ...rest } = added;
      added = on ? { ...added, [r.id]: r.expected_payout } : rest;
    }
  }

  const fillAmount = () => (fAmount = expected ? expected.toLocaleString('id-ID') : '');

  async function save() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    if (!chosenIds.length) return void (formError = language.t('finErrOrders'));
    if (fAmount === '' || amount <= 0) return void (formError = language.t('finErrReceived'));
    if (diff !== 0 && !fReason) return void (formError = language.t('finErrReason'));
    if (fReason === 'Lain-lain' && !fNote.trim()) return void (formError = language.t('finErrNote'));
    saving = true;
    try {
      await api.post(`/stores/${storeId}/settlements`, {
        channel,
        received_date: fDate,
        amount,
        order_ids: chosenIds,
        reason: diff !== 0 ? fReason + (fNote.trim() ? ` · ${fNote.trim()}` : '') : null
      });
      formOpen = false;
      await Promise.all([loadOverview(), loadChannel()]);
    } catch (err) {
      formError = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  function batchStatus(date: string) {
    const d = dayDiff(today(), date);
    if (d > 0) return { label: `${language.t('finLate')} ${d} ${language.t('finDays')}`, cls: 'bg-red-100 text-red-800' };
    if (d === 0) return { label: language.t('finDueToday'), cls: 'bg-amber-100 text-amber-800' };
    return { label: language.t('finPending'), cls: 'bg-[var(--cream)] text-[var(--espresso)]' };
  }

</script>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}

<div class="mb-5 grid gap-3 md:grid-cols-3">
  {#each overview as o (o.channel)}
    <button
      class="card p-4 text-left transition {channel === o.channel ? 'ring-2 ring-[var(--om-ink)]' : ''}"
      onclick={() => { channel = o.channel; batchPage = 1; historyPage = 1; }}
    >
      <img src={META[o.channel].logo} alt={META[o.channel].label} class="mb-3 h-7 w-auto max-w-[140px]" />
      <div class="grid grid-cols-2 gap-3 text-sm tabular-nums">
        <div><div class="text-xs text-[var(--text-muted)]">{language.t('finOutstanding')}</div><div class="font-bold">{formatRupiah(o.outstanding)}</div><div class="text-xs text-[var(--text-muted)]">{o.outstanding_count} {language.t('finOrdersCount')}</div></div>
        <div><div class="text-xs text-[var(--text-muted)]">{language.t('finOverdue')}</div><div class="font-bold {o.overdue ? 'text-red-700' : ''}">{formatRupiah(o.overdue)}</div></div>
        <div><div class="text-xs text-[var(--text-muted)]">{language.t('finReceivedMonth')}</div><div class="font-bold">{formatRupiah(o.received_month)}</div></div>
        <div><div class="text-xs text-[var(--text-muted)]">{language.t('finCommissionMonth')}</div><div class="font-bold">{formatRupiah(o.commission_month)}</div></div>
      </div>
    </button>
  {/each}
</div>

<div class="mb-3 flex flex-wrap items-center gap-3">
  <h2 class="flex flex-1 items-center gap-2 text-base font-semibold">
    <img src={META[channel].logo} alt="" class="h-6 w-auto max-w-[68px]" />
    {META[channel].label} · {language.t('finReceivablesTitle')}
  </h2>
  <button class="btn-primary flex items-center gap-2 disabled:opacity-50" disabled={!batchTotal} onclick={() => openForm(null)}><Landmark class="h-4 w-4" />{language.t('finRecordPayout')}</button>
</div>

<div class="card mb-6 overflow-hidden" class:opacity-60={loading}>
  <div class="hidden grid-cols-[120px_90px_130px_120px_130px_1fr_130px] gap-3 border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
    <div>{language.t('finEstPayout')}</div><div class="text-right">{language.t('finOrders')}</div><div class="text-right">{language.t('finGross')}</div><div class="text-right">{language.t('finCommission')}</div><div class="text-right">{language.t('finExpected')}</div><div>{language.t('finStatus')}</div><div></div>
  </div>
  {#each batches as b (b.date)}
    {@const st = batchStatus(b.date)}
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[var(--border)] p-3 last:border-0 md:grid md:grid-cols-[120px_90px_130px_120px_130px_1fr_130px] md:px-4">
      <div class="font-semibold tabular-nums">{fmtDate(b.date)}</div>
      <div class="tabular-nums md:text-right">{b.order_count}</div>
      <div class="tabular-nums md:text-right">{formatRupiah(b.gross)}</div>
      <div class="tabular-nums text-red-700 md:text-right">−{formatRupiah(b.gross - b.expected)}</div>
      <div class="font-bold tabular-nums md:text-right">{formatRupiah(b.expected)}</div>
      <div><span class="rounded-full px-2.5 py-1 text-xs font-bold {st.cls}">{st.label}</span></div>
      <div class="md:text-right"><button class="btn-outline px-3 py-1.5 text-sm" onclick={() => openForm(b.date)}>{language.t('finRecordRow')}</button></div>
    </div>
  {/each}
  {#if !batches.length && !loading}
    <div class="p-9 text-center text-[var(--text-muted)]">{language.t('finNoReceivables')}</div>
  {/if}
</div>
<Pagination page={batchPage} total={batchTotal} limit={HISTORY_SIZE} {loading} onPage={(p) => (batchPage = p)} />

<h2 class="mb-3 text-base font-semibold">{language.t('finHistory')}</h2>
<div class="card overflow-hidden" class:opacity-60={loading}>
  {#each history as h (h.id)}
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[var(--border)] p-3 text-sm last:border-0 md:px-4">
      <div class="w-28 font-semibold tabular-nums">{fmtDate(h.received_date)}</div>
      <div class="w-24 text-[var(--text-muted)]">{h.order_count} {language.t('finOrdersCount')}</div>
      <div class="w-32 tabular-nums"><span class="text-xs text-[var(--text-muted)]">{language.t('finExpected')}</span> {formatRupiah(h.expected)}</div>
      <div class="w-32 font-bold tabular-nums">{formatRupiah(h.amount)}</div>
      <div class="w-28 font-semibold tabular-nums {h.diff < 0 ? 'text-red-700' : 'text-[var(--om-brand)]'}">{h.diff ? signed(h.diff) : language.t('finMatch')}</div>
      <div class="min-w-0 flex-1 text-[var(--text-muted)]">{h.reason ?? ''}</div>
    </div>
  {/each}
  {#if !history.length && !loading}
    <div class="p-9 text-center text-[var(--text-muted)]">{language.t('finNoHistory')}</div>
  {/if}
</div>
<Pagination page={historyPage} total={historyTotal} limit={HISTORY_SIZE} {loading} onPage={(p) => (historyPage = p)} />

{#if formOpen}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) formOpen = false; }}>
    <section class="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <img src={META[channel].logo} alt="" class="h-7 w-auto max-w-[80px]" />
        <h2 class="display-font min-w-0 flex-1 truncate text-2xl font-bold text-[var(--espresso)]">{language.t('finPayoutTitle')} {META[channel].label}</h2>
        <button class="btn-outline px-4 py-2" onclick={() => (formOpen = false)}>{language.t('close')}</button>
      </div>
      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {#if formError}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{formError}</div>{/if}
        <div>
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <span class="flex-1 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finSelectOrders')} · {chosenIds.length} {language.t('finSelected')}</span>
            <button class={chip(false)} style="min-height: 40px" onclick={() => selectUpTo(null)}>{language.t('finSelectAll')}</button>
            <button class={chip(false)} style="min-height: 40px" onclick={() => selectUpTo(today())}>{language.t('finSelectDue')}</button>
            <button class={chip(false)} style="min-height: 40px" onclick={() => selectUpTo('none')}>{language.t('finSelectNone')}</button>
          </div>
          <div class="max-h-60 overflow-y-auto rounded-xl border border-[var(--border)]">
            {#each modalRows as r (r.id)}
              <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-3 py-2 text-sm last:border-0">
                <input type="checkbox" checked={isChecked(r.id)} onchange={(e) => toggleRow(r, e.currentTarget.checked)} />
                <span class="min-w-0 flex-1"><span class="font-semibold">#{r.order_number}</span> <span class="text-xs text-[var(--text-muted)]">{r.channel_order_id ?? ''}</span><br /><span class="text-xs text-[var(--text-muted)]">{fmtDate(r.expected_payout_date)}</span></span>
                <span class="text-xs text-[var(--text-muted)] tabular-nums">{formatRupiah(r.total_amount)}</span>
                <span class="w-24 text-right font-semibold tabular-nums">{formatRupiah(r.expected_payout)}</span>
              </label>
            {/each}
          </div>
          <Pagination page={modalPage} total={modalTotal} limit={MODAL_SIZE} onPage={(p) => { modalPage = p; void loadModalRows(); }} />
          <div class="mt-2 flex justify-between text-sm"><span class="text-[var(--text-muted)]">{language.t('finExpected')}</span><span class="font-bold tabular-nums">{formatRupiah(expected)}</span></div>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finReceivedAmount')} (Rp)</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={fAmount} oninput={(e) => { const d = digits(e.currentTarget.value); fAmount = d ? parseInt(d, 10).toLocaleString('id-ID') : ''; e.currentTarget.value = fAmount; }} />
            <button class="mt-1 text-xs font-bold text-[var(--warm-brown)]" onclick={fillAmount}>{language.t('finFillExpected')}</button>
          </label>
          <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finReceivedDate')}</span><input class="field" type="date" bind:value={fDate} /></label>
        </div>
        {#if fAmount !== '' && diff === 0 && chosenIds.length}
          <div class="flex items-center gap-1.5 text-sm font-semibold text-[var(--om-brand)]"><Check class="h-4 w-4" />{language.t('finMatch')}</div>
        {:else if fAmount !== '' && diff !== 0}
          <div class="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--cream)] p-3">
            <div class="flex justify-between text-sm font-semibold"><span>{language.t('finDiff')}</span><span class="tabular-nums {diff < 0 ? 'text-red-700' : 'text-[var(--om-brand)]'}">{signed(diff)}</span></div>
            <div class="text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finDiffReason')}</div>
            <div class="flex flex-wrap gap-1.5">{#each REASONS as r}<button class={chip(fReason === r)} style="min-height: 40px" onclick={() => (fReason = r)}>{r}</button>{/each}</div>
            {#if fReason}<input class="field" placeholder={language.t('finReasonNote')} bind:value={fNote} />{/if}
          </div>
        {/if}
      </div>
      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-outline" onclick={() => (formOpen = false)}>{language.t('cancel')}</button>
        <button class="btn-primary disabled:opacity-50" disabled={saving} onclick={save}>{saving ? language.t('saving') : language.t('finRecord')}</button>
      </div>
    </section>
  </div>
{/if}
