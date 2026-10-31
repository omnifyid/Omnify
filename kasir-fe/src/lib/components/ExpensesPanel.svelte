<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Expense, ExpenseSource, ExpenseSummary, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import type { MessageKey } from '$lib/i18n/messages';
  import { session } from '$lib/stores/session.svelte';
  import { EXPENSE_CATEGORIES } from '$lib/utils/finance';
  import { chip, seg, SEG_GROUP } from '$lib/utils/ui';
  import { formatRupiah } from '$lib/utils/format';
  import { PAGE_SIZE, pageCount } from '$lib/utils/paging';
  import Pagination from './Pagination.svelte';

  const CATEGORIES = EXPENSE_CATEGORIES;
  const SOURCES: { id: ExpenseSource; key: MessageKey }[] = [
    { id: 'BANK', key: 'finSrcBank' },
    { id: 'EWALLET', key: 'finSrcEwallet' },
    { id: 'PETTY', key: 'finSrcPetty' },
    { id: 'DRAWER', key: 'finSrcDrawer' }
  ];
  const PERIODS: { id: number; key: MessageKey }[] = [
    { id: 0, key: 'finToday' },
    { id: 7, key: 'fin7d' },
    { id: 30, key: 'fin30d' },
    { id: 60, key: 'fin60d' }
  ];

  const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const daysAgo = (n: number) => iso(new Date(Date.now() - n * 86400000));
  const digits = (v: string) => v.replace(/\D/g, '');
  const srcLabel = (s: ExpenseSource) => language.t(SOURCES.find((x) => x.id === s)!.key);
  const fmtDate = (d: string) =>
    new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium' }).format(new Date(`${d}T00:00:00`));

  let period = $state(7);
  let category = $state('');
  let source = $state('');
  let rows = $state<Expense[]>([]);
  let page = $state(1);
  let rowTotal = $state(0);
  let summary = $state<ExpenseSummary | null>(null);
  let error = $state('');
  let loading = $state(false);

  let formOpen = $state(false);
  let fDate = $state(iso(new Date()));
  let fCategory = $state('');
  let fDescription = $state('');
  let fAmount = $state('');
  let fSource = $state<ExpenseSource>('BANK');
  let fRecurring = $state(false);
  let formError = $state('');
  let saving = $state(false);
  let busyId = $state('');

  const filterQuery = () => {
    const q = new URLSearchParams({ date_from: daysAgo(period) });
    if (category) q.set('category', category);
    if (source) q.set('source', source);
    return q;
  };

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    try {
      const q = filterQuery();
      const [list, sum] = await Promise.all([
        api.get<PaginatedResponse<Expense>>(`/stores/${storeId}/expenses?${q}&limit=${PAGE_SIZE}&offset=${(page - 1) * PAGE_SIZE}`),
        api.get<ExpenseSummary>(`/stores/${storeId}/expenses/summary?${q}`)
      ]);
      rows = paginatedItems(list);
      rowTotal = list.total;
      if (!rows.length && page > 1) page = pageCount(rowTotal);
      summary = sum;
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
    void category;
    void source;
    void page;
    untrack(() => void load());
  });

  function openCreate() {
    fDate = iso(new Date());
    fCategory = '';
    fDescription = '';
    fAmount = '';
    fSource = 'BANK';
    fRecurring = false;
    formError = '';
    formOpen = true;
  }

  async function save() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    const amount = parseInt(digits(fAmount) || '0', 10);
    if (!fCategory) return void (formError = language.t('finErrCategory'));
    if (!fDescription.trim()) return void (formError = language.t('finErrDescription'));
    if (amount <= 0) return void (formError = language.t('finErrAmount'));
    saving = true;
    try {
      await api.post(`/stores/${storeId}/expenses`, {
        date: fDate,
        category: fCategory,
        description: fDescription.trim(),
        amount,
        source: fSource,
        recurring: fRecurring
      });
      formOpen = false;
      await load();
    } catch (err) {
      formError = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  async function act(e: Expense, kind: 'confirm' | 'delete') {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    busyId = e.id;
    try {
      if (kind === 'confirm') await api.post(`/stores/${storeId}/expenses/${e.id}/confirm`, {});
      else await api.delete(`/stores/${storeId}/expenses/${e.id}`);
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      busyId = '';
    }
  }

</script>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}

<div class="mb-4 flex flex-wrap items-center gap-3">
  <div class={SEG_GROUP} role="group">
    {#each PERIODS as p (p.id)}
      <button class={seg(period === p.id)} style="height: var(--om-tap)" aria-pressed={period === p.id} onclick={() => { period = p.id; page = 1; }}>{language.t(p.key)}</button>
    {/each}
  </div>
  <select class="field w-auto" bind:value={category} onchange={() => (page = 1)}>
    <option value="">{language.t('finAllCategories')}</option>
    {#each CATEGORIES as c}<option value={c}>{c}</option>{/each}
  </select>
  <select class="field w-auto" bind:value={source} onchange={() => (page = 1)}>
    <option value="">{language.t('finAllSources')}</option>
    {#each SOURCES as s}<option value={s.id}>{language.t(s.key)}</option>{/each}
  </select>
  <button class="btn-primary ml-auto flex items-center gap-2" onclick={openCreate}><span class="ms !text-[16px]" aria-hidden="true">add</span>{language.t('finAddExpense')}</button>
</div>

{#if summary}
  <div class="mb-4 grid gap-3 md:grid-cols-2" class:opacity-60={loading}>
    <section class="card p-5">
      <div class="text-xs text-[var(--text-muted)]">{language.t('finExpTotal')}</div>
      <div class="my-2 text-3xl font-bold tabular-nums">{formatRupiah(summary.total)}</div>
      <div class="text-xs text-[var(--text-muted)]">
        {summary.posted_count} {language.t('finExpRecorded')}{summary.draft_count ? ` · ${summary.draft_count} ${language.t('finDraftsWaiting')}` : ''}
      </div>
    </section>
    <section class="card space-y-2 p-5">
      <div class="text-xs text-[var(--text-muted)]">{language.t('finTopCategories')}</div>
      {#each summary.by_category.slice(0, 4) as c (c.category)}
        <div class="flex justify-between gap-3 text-sm">
          <span>{c.category}</span>
          <span class="font-semibold tabular-nums">{formatRupiah(c.total)} <span class="text-xs font-normal text-[var(--text-muted)]">{Math.round((c.total / (summary.total || 1)) * 100)}%</span></span>
        </div>
      {/each}
    </section>
  </div>
{/if}

<div class="card overflow-hidden" class:opacity-60={loading}>
  <div class="hidden grid-cols-[110px_1fr_1.6fr_1fr_120px_150px] gap-3 border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
    <div>{language.t('finDate')}</div><div>{language.t('finCategory')}</div><div>{language.t('finDescription')}</div><div>{language.t('finSource')}</div><div class="text-right">{language.t('finAmount')}</div><div>{language.t('finStatus')}</div>
  </div>
  {#each rows as e (e.id)}
    {@const draft = e.status === 'DRAFT'}
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-[var(--border)] p-3 last:border-0 md:grid md:grid-cols-[110px_1fr_1.6fr_1fr_120px_150px] md:px-4 md:py-3 {draft ? 'bg-amber-50/50' : ''}">
      <div class="text-xs tabular-nums">{fmtDate(e.date)}</div>
      <div class="font-medium">{e.category}</div>
      <div class="flex min-w-0 items-center gap-1.5">
        <span class="truncate">{e.description}</span>
        {#if e.recurring}<span class="inline-flex shrink-0 items-center gap-0.5 text-xs text-blue-700"><span class="ms !text-[14px]" aria-hidden="true">event_repeat</span>{language.t('finRecurring')}</span>{/if}
      </div>
      <div class="text-sm">{srcLabel(e.source)}</div>
      <div class="font-bold tabular-nums md:text-right">{formatRupiah(e.amount)}</div>
      <div class="flex items-center gap-2">
        <span class="rounded-full px-2.5 py-1 text-xs font-bold {draft ? 'bg-amber-100 text-amber-800' : 'bg-[var(--light-brown)] text-[var(--om-brand)]'}">{draft ? language.t('finDraft') : language.t('finPosted')}</span>
        {#if draft}
          <button class="btn-outline px-2.5 py-1.5 text-xs" disabled={busyId === e.id} onclick={() => act(e, 'confirm')}>{language.t('finConfirm')}</button>
          <button class="grid h-8 w-8 place-items-center rounded-lg border border-[var(--border)] text-red-600 hover:bg-red-50" aria-label={language.t('finDeleteDraft')} disabled={busyId === e.id} onclick={() => act(e, 'delete')}><span class="ms !text-[16px]" aria-hidden="true">delete</span></button>
        {/if}
      </div>
    </div>
  {/each}
  {#if !rows.length && !loading}
    <div class="p-9 text-center text-[var(--text-muted)]">{language.t('finNoExpenses')}</div>
  {/if}
</div>
<Pagination {page} total={rowTotal} {loading} onPage={(p) => (page = p)} />

{#if formOpen}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) formOpen = false; }}>
    <section class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font min-w-0 flex-1 truncate text-2xl font-bold text-[var(--espresso)]">{language.t('finAddExpense')}</h2>
        <button class="btn-outline px-4 py-2" onclick={() => (formOpen = false)}>{language.t('close')}</button>
      </div>
      <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
        {#if formError}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{formError}</div>{/if}
        <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finDate')}</span><input class="field" type="date" bind:value={fDate} /></label>
        <div>
          <span class="mb-1 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finCategory')}</span>
          <div class="flex flex-wrap gap-1.5">
            {#each CATEGORIES as c}<button class={chip(fCategory === c)} style="min-height: 40px" onclick={() => (fCategory = c)}>{c}</button>{/each}
          </div>
        </div>
        <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finDescription')}</span><input class="field" maxlength="200" bind:value={fDescription} /></label>
        <label class="block">
          <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finAmount')} (Rp)</span>
          <input class="field" type="text" inputmode="numeric" placeholder="0" value={fAmount} oninput={(e) => { const d = digits(e.currentTarget.value); fAmount = d ? parseInt(d, 10).toLocaleString('id-ID') : ''; e.currentTarget.value = fAmount; }} />
        </label>
        <div>
          <span class="mb-1 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('finSource')}</span>
          <div class="flex flex-wrap gap-1.5">
            {#each SOURCES as s}<button class={chip(fSource === s.id)} style="min-height: 40px" onclick={() => (fSource = s.id)}>{language.t(s.key)}</button>{/each}
          </div>
        </div>
        <label class="flex cursor-pointer items-center gap-2 text-sm"><input type="checkbox" bind:checked={fRecurring} />{language.t('finRecurringToggle')}</label>
      </div>
      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-outline" onclick={() => (formOpen = false)}>{language.t('cancel')}</button>
        <button class="btn-primary disabled:opacity-50" disabled={saving} onclick={save}>{saving ? language.t('saving') : language.t('finRecord')}</button>
      </div>
    </section>
  </div>
{/if}
