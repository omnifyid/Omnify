<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Ingredient, IngredientSummary, PaginatedResponse, StockMovement } from '$lib/api/types';
  import type { MessageKey } from '$lib/i18n/messages';
  import { language } from '$lib/i18n/language.svelte';
  import { goto } from '$app/navigation';
  import { session } from '$lib/stores/session.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import { chip, CHIP_ROW, seg, SEG_GROUP } from '$lib/utils/ui';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { PAGE_SIZE } from '$lib/utils/paging';

  type Tab = 'stock' | 'opname' | 'movements';

  let tab = $state<Tab>('stock');
  let ingredients = $state<Ingredient[]>([]);
  let movements = $state<StockMovement[]>([]);
  let search = $state('');
  let error = $state('');
  let notice = $state('');
  let saving = $state(false);

  // ingredient modal (create/edit)
  let formOpen = $state(false);
  let editing = $state<Ingredient | null>(null);
  let fName = $state('');
  let fUnit = $state('');
  let fCategory = $state('');
  let fMin = $state('');
  let fCost = $state('');
  let fInitial = $state('');
  let deleteTarget = $state<Ingredient | null>(null);

  // restock modal
  let restockTarget = $state<Ingredient | null>(null);
  let rQty = $state('');
  let rCost = $state('');
  let rNote = $state('');

  // opname: ingredient id -> counted text
  let counted = $state<Record<string, string>>({});

  const storeId = $derived(session.selectedStore?.id);
  const num = (s: string) => {
    const n = parseFloat(s.replace(',', '.'));
    return Number.isFinite(n) ? n : NaN;
  };
  const fmtQty = (n: number) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 3 }).format(n);
  const isLow = (i: Ingredient) => i.stock <= i.min_stock;
  /** Kritis under half the limit, Menipis at or under it (same rule as the low-stock KPI), otherwise Aman. */
  function stockLevel(i: Ingredient) {
    if (i.stock < i.min_stock * 0.5 || i.stock < 0) return 'critical' as const;
    return isLow(i) ? ('low' as const) : ('ok' as const);
  }
  const LEVEL = {
    critical: { label: 'invCritical', bar: 'bg-[#D64535]', chip: 'bg-[var(--om-danger-tint)] text-[var(--om-danger)]' },
    low: { label: 'invLow', bar: 'bg-[#E0A526]', chip: 'bg-[var(--om-warning-tint)] text-[var(--om-warning)]' },
    ok: { label: 'invOk', bar: 'bg-[var(--om-brand-bright)]', chip: 'bg-[var(--om-brand-tint)] text-[var(--om-brand)]' }
  } as const;
  /** Bar fill: the full bar equals twice the limit, like new-ui. */
  const levelPct = (i: Ingredient) => (i.min_stock > 0 ? Math.max(0, Math.min(100, (i.stock / (i.min_stock * 2)) * 100)) : i.stock > 0 ? 100 : 0);
  const digits = (s: string) => s.replace(/\D/g, '');

  // stock tab filter, server-side: Menipis = at or under the limit, Kritis = under half of it
  let stockFilter = $state<'' | 'low' | 'critical'>('');
  let summary = $state<IngredientSummary | null>(null);
  let listTotal = $state(0);
  let stockPage = $state(1);
  let opPage = $state(1);
  let movPage = $state(1);
  let movTotal = $state(0);
  let loading = $state(false);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  // Ingredients seen on any loaded page, so opname totals cover counts typed on earlier pages.
  let known = $state<Record<string, Ingredient>>({});
  let lowCount = $derived(summary?.low_count ?? 0);
  let stockValue = $derived(summary?.stock_value ?? 0);
  let categories = $derived(summary?.categories ?? []);

  async function loadSummary() {
    if (!storeId) return;
    try {
      summary = await api.get<IngredientSummary>(`/stores/${storeId}/ingredients/summary`);
    } catch {
      /* the list request reports errors */
    }
  }

  async function loadIngredients() {
    if (!storeId || tab === 'movements') return;
    loading = true;
    try {
      const page = tab === 'opname' ? opPage : stockPage;
      const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
      if (tab === 'stock' && search.trim()) q.set('search', search.trim());
      if (tab === 'stock' && stockFilter) q.set('level', stockFilter);
      const res = await api.get<PaginatedResponse<Ingredient>>(`/stores/${storeId}/ingredients?${q}`);
      ingredients = paginatedItems(res);
      listTotal = res.total;
      known = { ...known, ...Object.fromEntries(ingredients.map((i) => [i.id, i])) };
      error = '';
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  const reload = async () => {
    await Promise.all([loadIngredients(), loadSummary()]);
  };

  async function loadMovements() {
    if (!storeId) return;
    try {
      const res = await api.get<PaginatedResponse<StockMovement>>(`/stores/${storeId}/inventory/movements?limit=${PAGE_SIZE}&offset=${(movPage - 1) * PAGE_SIZE}`);
      movements = paginatedItems(res);
      movTotal = res.total;
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    }
  }

  function openCreate() {
    editing = null;
    fName = '';
    fUnit = '';
    fCategory = '';
    fMin = '';
    fCost = '';
    fInitial = '';
    formOpen = true;
  }

  function openEdit(i: Ingredient) {
    editing = i;
    fName = i.name;
    fUnit = i.unit;
    fCategory = i.category ?? '';
    fMin = i.min_stock ? String(i.min_stock) : '';
    fCost = i.cost_price ? i.cost_price.toLocaleString('id-ID') : '';
    fInitial = '';
    formOpen = true;
  }

  async function saveIngredient() {
    if (!storeId || !fName.trim() || !fUnit.trim()) return;
    saving = true;
    error = '';
    const min = fMin ? num(fMin) : 0;
    const body = {
      name: fName.trim(),
      unit: fUnit.trim(),
      category: fCategory.trim() || null,
      min_stock: Number.isNaN(min) ? 0 : min,
      cost_price: fCost ? parseInt(digits(fCost) || '0', 10) : 0
    };
    try {
      if (editing) {
        await api.patch(`/stores/${storeId}/ingredients/${editing.id}`, body);
      } else {
        const init = fInitial ? num(fInitial) : 0;
        await api.post(`/stores/${storeId}/ingredients`, { ...body, initial_stock: Number.isNaN(init) ? 0 : init });
      }
      formOpen = false;
      await reload();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  function openDelete() {
    const target = editing;
    if (!target) return;
    formOpen = false;
    deleteTarget = target;
  }

  async function confirmDelete() {
    if (!storeId || !deleteTarget) return;
    saving = true;
    try {
      await api.delete(`/stores/${storeId}/ingredients/${deleteTarget.id}`);
      deleteTarget = null;
      await reload();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
      deleteTarget = null;
    } finally {
      saving = false;
    }
  }

  function openRestock(i: Ingredient) {
    restockTarget = i;
    rQty = '';
    rCost = i.cost_price ? i.cost_price.toLocaleString('id-ID') : '';
    rNote = '';
  }

  async function saveRestock() {
    const target = restockTarget;
    const qty = num(rQty);
    if (!storeId || !target || !(qty > 0)) return;
    saving = true;
    try {
      await api.post(`/stores/${storeId}/ingredients/${target.id}/restock`, {
        quantity: qty,
        cost_price: rCost ? parseInt(digits(rCost) || '0', 10) : null,
        note: rNote.trim() || null
      });
      restockTarget = null;
      await reload();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  // opname
  const countedValue = (i: Ingredient) => {
    const raw = counted[i.id];
    return raw === undefined || raw === '' ? null : num(raw);
  };
  const diffOf = (i: Ingredient) => {
    const c = countedValue(i);
    return c === null || Number.isNaN(c) ? null : Math.round((c - i.stock) * 1000) / 1000;
  };
  let opRows = $derived(ingredients.map((i) => ({ i, diff: diffOf(i) })));
  let opChanged = $derived(
    Object.keys(counted)
      .map((id) => known[id])
      .filter((i): i is Ingredient => !!i)
      .map((i) => ({ i, diff: diffOf(i) }))
      .filter((r) => r.diff !== null)
  );
  let opValue = $derived(opChanged.reduce((a, r) => a + (r.diff ?? 0) * r.i.cost_price, 0));

  function fillFromSystem() {
    counted = { ...counted, ...Object.fromEntries(ingredients.map((i) => [i.id, String(i.stock)])) };
  }

  async function saveOpname() {
    if (!storeId || !opChanged.length) return;
    saving = true;
    try {
      await api.post(`/stores/${storeId}/inventory/opname`, {
        lines: opChanged.map((r) => ({ ingredient_id: r.i.id, counted: num(counted[r.i.id]) }))
      });
      counted = {};
      notice = language.t('invOpnameSaved');
      setTimeout(() => (notice = ''), 4000);
      await reload();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  function setTab(next: Tab) {
    tab = next;
    if (next === 'movements') void loadMovements();
  }

  $effect(() => {
    void storeId;
    void tab;
    void stockPage;
    void opPage;
    void search;
    void stockFilter;
    untrack(() => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => void loadIngredients(), tab === 'stock' && search.trim() ? 350 : 0);
    });
  });

  $effect(() => {
    if (storeId) untrack(() => void loadSummary());
  });

  const TABS: [Tab, MessageKey][] = [['stock', 'invStock'], ['opname', 'invOpname'], ['movements', 'invMovements']];

  // module switched off in Settings: leave the page
  $effect(() => {
    if (session.selectedStore?.inventory_enabled === false) void goto('/dashboard');
  });
</script>

<svelte:head><title>{language.t('inventory')} | Omnify</title></svelte:head>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}
{#if notice}
  <div class="mb-5 rounded-xl border border-green-200 bg-green-50 p-3 text-green-700">{notice}</div>
{/if}

<div class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
  <div class="card p-4"><div class="text-xs text-[var(--text-muted)]">{language.t('invTotalIngredients')}</div><div class="text-2xl font-bold tabular-nums">{summary?.count ?? 0}</div></div>
  <div class="card p-4"><div class="text-xs text-[var(--text-muted)]">{language.t('invLowCount')}</div><div class="text-2xl font-bold tabular-nums {lowCount ? 'text-amber-700' : 'text-[var(--om-brand)]'}">{lowCount}</div></div>
  <div class="card p-4"><div class="text-xs text-[var(--text-muted)]">{language.t('invStockValue')}</div><div class="text-2xl font-bold tabular-nums">{formatRupiah(stockValue)}</div></div>
</div>

<div class="mb-4 flex flex-wrap items-center gap-3">
  <div class="inline-flex {SEG_GROUP}" role="tablist">
    {#each TABS as [key, label]}
      <button role="tab" aria-selected={tab === key} class="{seg(tab === key)} !px-5" style="height: var(--om-tap)" onclick={() => setTab(key)}>{language.t(label)}</button>
    {/each}
  </div>
  <div class="flex-1"></div>
  {#if tab === 'stock'}
    <button class="btn-primary flex items-center gap-2" onclick={openCreate}><span class="ms !text-[16px]" aria-hidden="true">add</span>{language.t('invAddIngredient')}</button>
  {/if}
</div>

{#if tab === 'stock'}
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <label class="field flex w-full max-w-sm items-center gap-2">
      <span class="ms !text-[16px] text-[var(--text-muted)]" aria-hidden="true">search</span>
      <input class="min-w-0 flex-1 bg-transparent outline-none" placeholder={language.t('invSearch')} bind:value={search} oninput={() => (stockPage = 1)} />
    </label>
    <div class={CHIP_ROW} role="group" aria-label={language.t('status')}>
      {#each [['', 'all'], ['low', 'invLow'], ['critical', 'invCritical']] as [key, label] (key)}
        <button type="button" class={chip(stockFilter === key)} style="min-height: var(--om-tap)" aria-pressed={stockFilter === key} onclick={() => { stockFilter = key as typeof stockFilter; stockPage = 1; }}>{language.t(label as MessageKey)}</button>
      {/each}
    </div>
  </div>
{/if}

{#if tab === 'stock'}
  <div class="card overflow-hidden">
    <div class="hidden grid-cols-[1.4fr_1.6fr_120px_100px_90px] gap-3 border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
      <div>{language.t('invName')}</div><div>{language.t('invOnHand')}</div><div class="text-right">{language.t('price')}</div><div>{language.t('status')}</div><div></div>
    </div>
    {#each ingredients as i (i.id)}
      {@const level = LEVEL[stockLevel(i)]}
      <div
        class="group flex cursor-pointer flex-wrap items-center gap-3 border-b border-[var(--border)] p-3 transition-colors last:border-0 hover:bg-[var(--cream)] active:bg-[var(--light-brown)]/60 md:grid md:grid-cols-[1.4fr_1.6fr_120px_100px_90px] md:px-4 md:py-3"
        role="button"
        tabindex="0"
        onclick={() => openEdit(i)}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openEdit(i); } }}
        aria-label={`${language.t('invEditIngredient')} ${i.name}`}
      >
        <div class="min-w-0 flex-1">
          <div class="truncate font-medium">{i.name}</div>
          <div class="text-xs text-[var(--text-muted)]">{i.category ?? '—'}</div>
        </div>
        <div class="flex basis-full items-center gap-2.5 md:basis-auto">
          <div class="h-1.5 flex-1 overflow-hidden rounded bg-[var(--om-fill-muted)]" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(levelPct(i))}>
            <div class="h-full rounded {level.bar}" style="width: {levelPct(i)}%"></div>
          </div>
          <div class="w-[9rem] shrink-0 whitespace-nowrap text-right text-xs tabular-nums"><strong>{fmtQty(i.stock)}</strong> <span class="text-[var(--text-muted)]">/ {fmtQty(i.min_stock)} {i.unit}</span></div>
        </div>
        <div class="hidden text-right text-sm tabular-nums md:block">{formatRupiah(i.cost_price)}/{i.unit}</div>
        <div><span class="rounded-full px-2.5 py-1 text-xs font-semibold {level.chip}">{language.t(level.label)}</span></div>
        <button class="btn-outline px-3 py-2 text-sm" onclick={(e) => { e.stopPropagation(); openRestock(i); }}>{language.t('invReceive')}</button>
      </div>
    {:else}
      <div class="p-8 text-center text-[var(--text-muted)]">{language.t(search.trim() || stockFilter ? 'invNoMatch' : 'invEmptyList')}</div>
    {/each}
  </div>
  <Pagination page={stockPage} total={listTotal} {loading} onPage={(p) => (stockPage = p)} />
{:else if tab === 'opname'}
  <div class="grid items-start gap-4 lg:grid-cols-[1fr_300px]">
    <div class="card overflow-hidden">
      <div class="hidden grid-cols-[minmax(0,1.4fr)_90px_70px_110px_100px_110px] gap-3 border-b border-[var(--border)] bg-[var(--cream)] px-4 py-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
        <div>{language.t('invName')}</div><div class="text-right">{language.t('invSystem')}</div><div>{language.t('invUnit')}</div><div>{language.t('invCounted')}</div><div class="text-right">{language.t('invDifference')}</div><div class="text-right">{language.t('invDiffValue')}</div>
      </div>
      {#each opRows as { i, diff } (i.id)}
        {@const tone = !diff ? 'text-[var(--text-muted)]' : diff < 0 ? 'text-[var(--om-danger)]' : 'text-[var(--om-brand)]'}
        {@const diffText = diff === null ? '' : `${diff > 0 ? '+' : diff < 0 ? '−' : ''}${fmtQty(Math.abs(diff))}`}
        {@const valueText = diff ? `${diff > 0 ? '+' : '−'}${formatRupiah(Math.abs(Math.round(diff * i.cost_price)))}` : ''}
        <div class="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-0.5 border-b border-[var(--border)] px-3 py-2 last:border-0 md:grid-cols-[minmax(0,1.4fr)_90px_70px_110px_100px_110px] md:gap-3 md:px-4 md:py-1.5 {diff !== null ? 'bg-[var(--om-surface-sunk)]' : ''}">
          <div class="min-w-0 truncate text-sm font-medium">{i.name}</div>
          <div class="hidden text-right text-sm tabular-nums md:block">{fmtQty(i.stock)}</div>
          <div class="hidden text-sm text-[var(--text-muted)] md:block">{i.unit}</div>
          <div class="field flex !min-h-0 h-9 w-28 items-center !px-2.5 !py-0 md:w-auto">
            <input
              class="min-w-0 flex-1 bg-transparent text-right tabular-nums outline-none"
              inputmode="decimal"
              placeholder="0"
              aria-label={`${language.t('invCounted')}: ${i.name}`}
              value={counted[i.id] ?? ''}
              oninput={(e) => (counted[i.id] = e.currentTarget.value)}
            />
          </div>
          <div class="hidden text-right text-sm font-semibold tabular-nums md:block {tone}">{diffText}</div>
          <div class="hidden text-right text-sm font-semibold tabular-nums md:block {tone}">{valueText}</div>
          <div class="col-span-2 text-xs tabular-nums text-[var(--text-muted)] md:hidden">
            {language.t('invSystem')} {fmtQty(i.stock)} {i.unit}{#if diff} · <span class="font-bold {tone}">{diffText} {i.unit} {valueText}</span>{/if}
          </div>
        </div>
      {:else}
        <div class="p-8 text-center text-[var(--text-muted)]">{language.t('invEmptyList')}</div>
      {/each}
      <div class="px-3 pb-3"><Pagination page={opPage} total={listTotal} {loading} onPage={(p) => (opPage = p)} /></div>
    </div>
    <div class="card space-y-3 p-4">
      <div class="flex justify-between text-sm"><span class="text-[var(--text-muted)]">{language.t('invCounted')}</span><strong class="tabular-nums">{opChanged.length}/{summary?.count ?? 0}</strong></div>
      <div class="flex justify-between text-sm"><span class="text-[var(--text-muted)]">{language.t('invDifference')}</span><strong class="tabular-nums {opValue < 0 ? 'text-red-600' : ''}">{formatRupiah(opValue)}</strong></div>
      <div class="flex gap-2">
        <button class="btn-outline flex-1 px-3 py-2 text-sm" onclick={fillFromSystem}>{language.t('invFillFromSystem')}</button>
        <button class="btn-outline flex-1 px-3 py-2 text-sm" onclick={() => (counted = {})}>{language.t('reset')}</button>
      </div>
      <button class="btn-primary w-full disabled:opacity-50" disabled={saving || !opChanged.length} onclick={saveOpname}>{language.t('invSaveOpname')}</button>
    </div>
  </div>
{:else}
  <div class="card overflow-hidden">
    {#each movements as m (m.id)}
      <div class="flex items-center gap-3 border-b border-[var(--border)] p-3 last:border-0">
        <div class="min-w-0 flex-1">
          <div class="truncate font-medium">{m.ingredient_name}</div>
          <div class="truncate text-xs text-[var(--text-muted)]">{language.t(`invType${m.type}` as MessageKey)}{m.note ? ` · ${m.note}` : ''} · {formatDateTime(m.created_at)}</div>
        </div>
        <div class="text-right tabular-nums">
          <div class="font-bold {m.quantity < 0 ? 'text-red-600' : 'text-green-700'}">{m.quantity > 0 ? '+' : ''}{fmtQty(m.quantity)} {m.unit}</div>
          <div class="text-xs text-[var(--text-muted)]">= {fmtQty(m.balance_after)}</div>
        </div>
      </div>
    {:else}
      <div class="p-8 text-center text-[var(--text-muted)]">{language.t('invNoMovements')}</div>
    {/each}
  </div>
  <Pagination page={movPage} total={movTotal} onPage={(p) => { movPage = p; void loadMovements(); }} />
{/if}

<!-- ─── Ingredient modal ─────────────────────────────────────────── -->
{#if formOpen}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) formOpen = false; }}>
    <section class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font min-w-0 flex-1 truncate text-2xl font-bold text-[var(--espresso)]">{editing ? language.t('invEditIngredient') : language.t('invAddIngredient')}</h2>
        <button class="btn-outline px-4 py-2" onclick={() => (formOpen = false)}>{language.t('close')}</button>
      </div>
      <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
        <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invName')}</span><input class="field" bind:value={fName} /></label>
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invUnit')}</span><input class="field" placeholder="kg, g, L, pcs" bind:value={fUnit} /></label>
          <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invCategory')}</span><input class="field" list="inv-cats" bind:value={fCategory} /></label>
        </div>
        <datalist id="inv-cats">{#each categories as c}<option value={c}></option>{/each}</datalist>
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invMinStock')}</span><input class="field" inputmode="decimal" placeholder="0" bind:value={fMin} /></label>
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invCostPerUnit')}</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={fCost} oninput={(e) => { const d = digits(e.currentTarget.value); fCost = d ? parseInt(d, 10).toLocaleString('id-ID') : ''; e.currentTarget.value = fCost; }} />
          </label>
        </div>
        {#if !editing}
          <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invInitialStock')}</span><input class="field" inputmode="decimal" placeholder="0" bind:value={fInitial} /></label>
        {/if}
      </div>
      <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
        {#if editing}
          <button class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100" onclick={openDelete}><span class="ms !text-[16px]" aria-hidden="true">delete</span>{language.t('delete')}</button>
        {/if}
        <div class="flex flex-1 items-center justify-end gap-3">
          <button class="btn-outline" onclick={() => (formOpen = false)}>{language.t('cancel')}</button>
          <button class="btn-primary disabled:opacity-50" disabled={saving || !fName.trim() || !fUnit.trim()} onclick={saveIngredient}>{saving ? language.t('saving') : editing ? language.t('saveChanges') : language.t('add')}</button>
        </div>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Restock modal ────────────────────────────────────────────── -->
{#if restockTarget}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) restockTarget = null; }}>
    <section class="flex w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font truncate text-2xl font-bold text-[var(--espresso)]">{language.t('invRestock')}</h2>
          <p class="truncate text-sm text-[var(--text-muted)]">{restockTarget.name} · {fmtQty(restockTarget.stock)} {restockTarget.unit}</p>
        </div>
        <button class="grid h-9 w-9 place-items-center rounded-xl border border-[var(--border)]" onclick={() => (restockTarget = null)} aria-label={language.t('close')}><span class="ms !text-[16px]" aria-hidden="true">close</span></button>
      </div>
      <div class="space-y-3 p-5">
        <label class="block">
          <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invRestockQty')} ({restockTarget.unit})</span>
          <input class="field" inputmode="decimal" placeholder="0" bind:value={rQty} />
        </label>
        <label class="block">
          <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invCostPerUnit')}</span>
          <input class="field" type="text" inputmode="numeric" placeholder="0" value={rCost} oninput={(e) => { const d = digits(e.currentTarget.value); rCost = d ? parseInt(d, 10).toLocaleString('id-ID') : ''; e.currentTarget.value = rCost; }} />
        </label>
        <label class="block"><span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('invRestockNote')}</span><input class="field" bind:value={rNote} /></label>
      </div>
      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-outline" onclick={() => (restockTarget = null)}>{language.t('cancel')}</button>
        <button class="btn-primary disabled:opacity-50" disabled={saving || !(num(rQty) > 0)} onclick={saveRestock}>{saving ? language.t('saving') : language.t('invReceive')}</button>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Delete confirm ───────────────────────────────────────────── -->
{#if deleteTarget}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100"><span class="ms !text-[24px] text-red-600" aria-hidden="true">delete</span></div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('invDeleteTitle')}</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]"><strong class="text-[var(--espresso)]">{deleteTarget.name}</strong> — {language.t('invDeleteBody')}</p>
      </div>
      <div class="flex gap-3 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={() => (deleteTarget = null)}>{language.t('cancel')}</button>
        <button class="flex-1 rounded-full bg-red-600 px-4 py-2.5 font-bold text-white transition hover:bg-red-700 disabled:opacity-50" disabled={saving} onclick={confirmDelete}>{saving ? language.t('deleting') : language.t('delete')}</button>
      </div>
    </section>
  </div>
{/if}
