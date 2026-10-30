<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Ingredient, IngredientSummary, PaginatedResponse, StockMovement } from '$lib/api/types';
  import type { MessageKey } from '$lib/i18n/messages';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { PAGE_SIZE } from '$lib/utils/paging';
  import { Plus, Search, Trash2, X } from 'lucide-svelte';

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
  const digits = (s: string) => s.replace(/\D/g, '');

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
    untrack(() => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => void loadIngredients(), tab === 'stock' && search.trim() ? 350 : 0);
    });
  });

  $effect(() => {
    if (storeId) untrack(() => void loadSummary());
  });

  const TABS: [Tab, MessageKey][] = [['stock', 'invStock'], ['opname', 'invOpname'], ['movements', 'invMovements']];
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
  <div class="inline-flex rounded-[11px] bg-[var(--om-fill-muted)] p-1" role="tablist">
    {#each TABS as [key, label]}
      {@const active = tab === key}
      <button
        role="tab"
        aria-selected={active}
        class="rounded-[8px] px-5 text-[14px] transition-colors {active ? 'bg-[var(--om-brand-tint)] font-semibold shadow-[inset_0_0_0_2px_var(--om-brand)]' : 'font-medium text-[var(--om-ink-2)] hover:bg-[var(--om-fill-hover)]'}"
        style="min-height: calc(var(--om-tap) - 8px)"
        onclick={() => setTab(key)}
      >{language.t(label)}</button>
    {/each}
  </div>
  <div class="flex-1"></div>
  {#if tab === 'stock'}
    <button class="btn-primary flex items-center gap-2" onclick={openCreate}><Plus class="h-4 w-4" />{language.t('invAddIngredient')}</button>
  {/if}
</div>

{#if tab !== 'movements'}
  <label class="field mb-4 flex w-full max-w-sm items-center gap-2">
    <Search class="h-4 w-4 text-[var(--text-muted)]" />
    <input class="min-w-0 flex-1 bg-transparent outline-none" placeholder={language.t('invSearch')} bind:value={search} oninput={() => (stockPage = 1)} />
  </label>
{/if}

{#if tab === 'stock'}
  <div class="card overflow-hidden">
    <div class="hidden grid-cols-[1.4fr_1.6fr_120px_100px_90px] gap-3 border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
      <div>{language.t('invName')}</div><div>{language.t('invOnHand')}</div><div class="text-right">{language.t('invCostPerUnit')}</div><div>{language.t('status')}</div><div></div>
    </div>
    {#each ingredients as i (i.id)}
      {@const low = isLow(i)}
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
        <div class="text-sm tabular-nums"><strong>{fmtQty(i.stock)}</strong> <span class="text-[var(--text-muted)]">/ {fmtQty(i.min_stock)} {i.unit}</span></div>
        <div class="hidden text-right text-sm tabular-nums md:block">{formatRupiah(i.cost_price)}/{i.unit}</div>
        <div><span class="rounded-full px-2.5 py-1 text-xs font-bold {low ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-700'}">{low ? language.t('invLow') : language.t('invOk')}</span></div>
        <button class="btn-outline px-3 py-2 text-sm" onclick={(e) => { e.stopPropagation(); openRestock(i); }}>{language.t('invReceive')}</button>
      </div>
    {:else}
      <div class="p-8 text-center text-[var(--text-muted)]">{language.t('invEmptyList')}</div>
    {/each}
  </div>
  <Pagination page={stockPage} total={listTotal} {loading} onPage={(p) => (stockPage = p)} />
{:else if tab === 'opname'}
  <div class="grid items-start gap-4 lg:grid-cols-[1fr_300px]">
    <div class="card overflow-hidden">
      {#each opRows as { i, diff } (i.id)}
        <div class="flex items-center gap-3 border-b border-[var(--border)] p-3 last:border-0 {diff ? 'bg-[var(--light-brown)]/40' : ''}">
          <div class="min-w-0 flex-1">
            <div class="truncate font-medium">{i.name}</div>
            <div class="text-xs tabular-nums text-[var(--text-muted)]">{language.t('invSystem')} {fmtQty(i.stock)} {i.unit}</div>
          </div>
          {#if diff}
            <div class="w-20 text-right text-sm font-bold tabular-nums {diff < 0 ? 'text-red-600' : 'text-green-700'}">{diff > 0 ? '+' : ''}{fmtQty(diff)}</div>
          {/if}
          <div class="field flex w-32 shrink-0 items-center gap-1">
            <input
              class="min-w-0 flex-1 bg-transparent text-right tabular-nums outline-none"
              inputmode="decimal"
              placeholder={language.t('invCounted')}
              value={counted[i.id] ?? ''}
              oninput={(e) => (counted[i.id] = e.currentTarget.value)}
            />
            <span class="text-xs text-[var(--text-muted)]">{i.unit}</span>
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
          <button class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100" onclick={openDelete}><Trash2 class="h-4 w-4" />{language.t('delete')}</button>
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
        <button class="grid h-9 w-9 place-items-center rounded-xl border border-[var(--border)]" onclick={() => (restockTarget = null)} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
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
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100"><Trash2 class="h-6 w-6 text-red-600" /></div>
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
