<script lang="ts">
  import Toggle from '$lib/components/Toggle.svelte';
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Category, Discount, DiscountScope, DiscountTargetType, DiscountType, Item, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { formatDateTime, formatRupiah } from '$lib/utils/format';
  import { Trash2, X } from 'lucide-svelte';

  let discounts = $state<Discount[]>([]);
  let categories = $state<Category[]>([]);
  let items = $state<Item[]>([]);
  let loading = $state(false);
  let error = $state('');
  let page = $state(1);
  const limit = 20;
  let total = $state(0);
  let totalPages = $derived(Math.max(1, Math.ceil(total / limit)));
  let loadedStoreId = $state<string | null>(null);

  // Create modal state
  let creatingOpen = $state(false);
  let createName = $state('');
  let createCode = $state('');
  let createType = $state<DiscountType>('PERCENTAGE');
  let createValue = $state(0);
  let createMaxAmount = $state('');
  let createScope = $state<DiscountScope>('ORDER');
  let createTargetType = $state<DiscountTargetType>('ALL');
  let createTargetItemId = $state('');
  let createTargetCategoryId = $state('');
  let createIsAutomatic = $state(false);
  let createMinOrderAmount = $state('');
  let createMaxUses = $state('');
  let createExpiresAt = $state('');
  let createIsActive = $state(true);
  let creating = $state(false);

  // Edit modal state
  let editingDiscount = $state<Discount | null>(null);
  let editName = $state('');
  let editCode = $state('');
  let editType = $state<DiscountType>('PERCENTAGE');
  let editValue = $state(0);
  let editMaxAmount = $state('');
  let editScope = $state<DiscountScope>('ORDER');
  let editTargetType = $state<DiscountTargetType>('ALL');
  let editTargetItemId = $state('');
  let editTargetCategoryId = $state('');
  let editIsAutomatic = $state(false);
  let editMinOrderAmount = $state('');
  let editMaxUses = $state('');
  let editExpiresAt = $state('');
  let editIsActive = $state(true);
  let saving = $state(false);
  let deleteConfirmDiscount = $state<Discount | null>(null);
  let deleting = $state(false);

  // Derived visibility for create form
  let createShowTarget = $derived(createScope === 'ITEM');
  let createShowItemPicker = $derived(createScope === 'ITEM' && createTargetType === 'ITEM');
  let createShowCategoryPicker = $derived(createScope === 'ITEM' && createTargetType === 'CATEGORY');
  let createShowMaxAmount = $derived(createType === 'PERCENTAGE');

  // Derived visibility for edit form
  let editShowTarget = $derived(editScope === 'ITEM');
  let editShowItemPicker = $derived(editScope === 'ITEM' && editTargetType === 'ITEM');
  let editShowCategoryPicker = $derived(editScope === 'ITEM' && editTargetType === 'CATEGORY');
  let editShowMaxAmount = $derived(editType === 'PERCENTAGE');

  type PayloadFields = {
    name: string; code: string; type: DiscountType; value: number; maxAmount: string;
    scope: DiscountScope; targetType: DiscountTargetType; targetItemId: string;
    targetCategoryId: string; isAutomatic: boolean; minOrderAmount: string;
    maxUses: string; expiresAt: string; isActive: boolean;
  };

  function buildPayload(f: PayloadFields) {
    return {
      name: f.name,
      code: f.code.trim() || null,
      discount_type: f.type,
      value: f.type === 'PERCENTAGE' ? Math.round(f.value * 100) : f.value,
      max_discount_amount: f.maxAmount !== '' ? Number(f.maxAmount) : null,
      scope: f.scope,
      target_type: f.scope === 'ITEM' ? f.targetType : null,
      target_item_id: f.scope === 'ITEM' && f.targetType === 'ITEM' ? f.targetItemId || null : null,
      target_category_id: f.scope === 'ITEM' && f.targetType === 'CATEGORY' ? f.targetCategoryId || null : null,
      is_automatic: f.isAutomatic,
      min_order_amount: f.minOrderAmount !== '' ? Number(f.minOrderAmount) : null,
      max_uses: f.maxUses !== '' ? Number(f.maxUses) : null,
      expires_at: f.expiresAt || null,
      is_active: f.isActive
    };
  }

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loadedStoreId = storeId;
    loading = true;
    error = '';
    try {
      const [discRes, catsRes, itemsRes] = await Promise.all([
        api.get<PaginatedResponse<Discount>>(`/stores/${storeId}/discounts?limit=${limit}&offset=${(page - 1) * limit}`),
        api.get<PaginatedResponse<Category>>(`/stores/${storeId}/categories?limit=100`),
        api.get<PaginatedResponse<Item>>(`/stores/${storeId}/items?limit=500`)
      ]);
      discounts = paginatedItems(discRes);
      total = discRes.total;
      categories = paginatedItems(catsRes);
      items = paginatedItems(itemsRes);
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  function openCreate() {
    createName = ''; createCode = ''; createType = 'PERCENTAGE'; createValue = 0;
    createMaxAmount = ''; createScope = 'ORDER'; createTargetType = 'ALL';
    createTargetItemId = ''; createTargetCategoryId = ''; createIsAutomatic = false;
    createMinOrderAmount = ''; createMaxUses = ''; createExpiresAt = ''; createIsActive = true;
    creatingOpen = true;
  }

  function closeCreate() { creatingOpen = false; }

  async function createDiscount() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    creating = true;
    error = '';
    try {
      await api.post(`/stores/${storeId}/discounts`, buildPayload({
        name: createName, code: createCode, type: createType, value: createValue,
        maxAmount: createMaxAmount, scope: createScope, targetType: createTargetType,
        targetItemId: createTargetItemId, targetCategoryId: createTargetCategoryId,
        isAutomatic: createIsAutomatic, minOrderAmount: createMinOrderAmount,
        maxUses: createMaxUses, expiresAt: createExpiresAt, isActive: createIsActive
      }));
      closeCreate();
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      creating = false;
    }
  }

  function startEdit(d: Discount) {
    editingDiscount = d;
    editName = d.name;
    editCode = d.code ?? '';
    editType = d.discount_type;
    editValue = d.discount_type === 'PERCENTAGE' ? d.value / 100 : d.value;
    editMaxAmount = d.max_discount_amount != null ? String(d.max_discount_amount) : '';
    editScope = d.scope;
    editTargetType = d.target_type ?? 'ALL';
    editTargetItemId = d.target_item_id ?? '';
    editTargetCategoryId = d.target_category_id ?? '';
    editIsAutomatic = d.is_automatic;
    editMinOrderAmount = d.min_order_amount != null ? String(d.min_order_amount) : '';
    editMaxUses = d.max_uses != null ? String(d.max_uses) : '';
    editExpiresAt = d.expires_at ? d.expires_at.slice(0, 16) : '';
    editIsActive = d.is_active;
  }

  function cancelEdit() { editingDiscount = null; }

  async function saveEdit() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !editingDiscount) return;
    saving = true;
    error = '';
    try {
      await api.patch(`/stores/${storeId}/discounts/${editingDiscount.id}`, buildPayload({
        name: editName, code: editCode, type: editType, value: editValue,
        maxAmount: editMaxAmount, scope: editScope, targetType: editTargetType,
        targetItemId: editTargetItemId, targetCategoryId: editTargetCategoryId,
        isAutomatic: editIsAutomatic, minOrderAmount: editMinOrderAmount,
        maxUses: editMaxUses, expiresAt: editExpiresAt, isActive: editIsActive
      }));
      cancelEdit();
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  function openDeleteConfirm() {
    const d = editingDiscount;
    if (!d) return;
    cancelEdit();
    deleteConfirmDiscount = d;
  }

  function closeDeleteConfirm() {
    deleteConfirmDiscount = null;
  }

  async function confirmDelete() {
    const d = deleteConfirmDiscount;
    if (!d) return;
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    deleting = true;
    error = '';
    try {
      await api.delete(`/stores/${storeId}/discounts/${d.id}`);
      deleteConfirmDiscount = null;
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      deleting = false;
    }
  }

  async function goToPage(newPage: number) {
    page = newPage;
    await load();
  }

  function discountValue(d: Discount): string {
    return d.discount_type === 'PERCENTAGE' ? `${d.value / 100}%` : formatRupiah(d.value);
  }

  function discountCap(d: Discount): string | null {
    return d.discount_type === 'PERCENTAGE' && d.max_discount_amount
      ? `max ${formatRupiah(d.max_discount_amount)}`
      : null;
  }

  $effect(() => {
    const storeId = session.selectedStore?.id;
    if (storeId && storeId !== loadedStoreId) { page = 1; untrack(() => void load()); }
  });
</script>

<svelte:head><title>{language.t('discounts')} | Kasir</title></svelte:head>

<div class="mb-6 flex items-center justify-between gap-4">
  <div>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('discounts')}</h1>
    <p class="text-[var(--text-muted)]">{language.t('createPromoAndAutomaticDiscounts')}</p>
  </div>
  <button class="btn-primary flex-shrink-0" onclick={openCreate}>{language.t('addDiscount')}</button>
</div>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}

<!-- Discounts list -->
<div class="card overflow-hidden">
  <div class="hidden grid-cols-[1fr_110px_150px_80px_80px] border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
    <div>{language.t('name')} / {language.t('code')}</div>
    <div class="text-right">{language.t('value')}</div>
    <div class="pl-4">Scope · {language.t('target')}</div>
    <div>{language.t('automatic')}</div>
    <div>{language.t('status')}</div>
  </div>

  {#each discounts as d}
    <div
      class="group grid cursor-pointer grid-cols-[1fr_110px] items-center gap-2 border-b border-[var(--border)] px-4 py-3 last:border-0 transition-colors hover:bg-[var(--cream)] active:bg-[var(--light-brown)]/60 md:grid-cols-[1fr_110px_150px_80px_80px]"
      role="button"
      tabindex="0"
      onclick={() => startEdit(d)}
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startEdit(d); } }}
      aria-label={`Edit ${d.name}`}
    >
      <div>
        <div class="font-semibold text-[var(--espresso)]">{d.name}</div>
        <div class="mt-0.5 text-xs text-[var(--text-muted)]">
          {#if d.code}<span class="font-mono">{d.code}</span>{:else}<span class="italic">{language.t('automatic')}</span>{/if}
          {#if d.used_count != null} · {language.t('used')} {d.used_count}{d.max_uses != null ? `/${d.max_uses}` : ''}×{/if}
          {#if d.expires_at} · exp {formatDateTime(d.expires_at).slice(0, 10)}{/if}
        </div>
      </div>
      <div class="text-right">
        <div class="text-sm font-semibold text-[var(--espresso)]">{discountValue(d)}</div>
        {#if discountCap(d)}<div class="text-xs text-[var(--text-muted)]">{discountCap(d)}</div>{/if}
      </div>
      <div class="hidden pl-4 md:block">
        <span class="inline-flex items-center rounded-full bg-[var(--light-brown)] px-2 py-0.5 text-xs font-bold text-[var(--espresso)]">{d.scope}</span>
        {#if d.scope === 'ITEM' && d.target_type && d.target_type !== 'ALL'}
          <div class="mt-0.5 text-xs text-[var(--text-muted)]">
            {#if d.target_type === 'CATEGORY' && d.target_category_id}
              {categories.find(c => c.id === d.target_category_id)?.name ?? '—'}
            {:else if d.target_type === 'ITEM' && d.target_item_id}
              {items.find(i => i.id === d.target_item_id)?.name ?? '—'}
            {:else}
              {language.t('all')} {language.t('items')}
            {/if}
          </div>
        {/if}
      </div>
      <div class="hidden md:block">
        {#if d.is_automatic}<span class="text-xs font-bold text-[var(--warm-brown)]">{language.t('automatic')}</span>{:else}<span class="text-xs text-[var(--text-muted)]">—</span>{/if}
      </div>
      <div>
        {#if d.is_active}
          <span class="rounded-full bg-green-100 px-2 py-0.5 text-xs font-bold text-green-700">{language.t('active')}</span>
        {:else}
          <span class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold text-gray-500">{language.t('inactive')}</span>
        {/if}
      </div>
    </div>
  {:else}
    <div class="p-8 text-center text-[var(--text-muted)]">{loading ? language.t('loading') : language.t('noDiscountsYet')}</div>
  {/each}

  {#if totalPages > 1}
    <div class="flex items-center justify-between gap-3 border-t border-[var(--border)] p-4 text-sm">
      <span class="text-[var(--text-muted)]">{language.t('page')} {page} {language.t('of')} {totalPages}</span>
      <div class="flex gap-2">
        <button class="btn-outline py-1" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>{language.t('previous')}</button>
        <button class="btn-outline py-1" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>{language.t('next')}</button>
      </div>
    </div>
  {/if}
</div>

<!-- Create modal -->
{#if creatingOpen}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeCreate(); }}
  >
    <section
      class="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
    >
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('addDiscount')}</h2>
          <p class="text-sm text-[var(--text-muted)]">{language.t('createDiscountSubtitle')}</p>
        </div>
        <button class="icon-btn flex-shrink-0" onclick={closeCreate}><X size={18} /></button>
      </div>

      <form
        class="min-h-0 flex-1 overflow-y-auto p-5"
        onsubmit={(e) => { e.preventDefault(); createDiscount(); }}
      >
        <div class="grid gap-3 md:grid-cols-2">
          <div>
            <label for="create-discount-name" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('name')}</label>
            <input id="create-discount-name" class="field" placeholder={language.t('name')} bind:value={createName} required />
          </div>
          <div>
            <label for="create-discount-code" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('promoCode')}</label>
            <input id="create-discount-code" class="field" placeholder={language.t('code')} bind:value={createCode} />
          </div>
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_1fr]">
          <div>
            <label for="create-discount-type" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('type')}</label>
            <select id="create-discount-type" class="field" bind:value={createType}>
              <option value="PERCENTAGE">{language.t('percentage')} (%)</option>
              <option value="FIXED">{language.t('fixedAmount')} (Rp)</option>
            </select>
          </div>
          <div>
            <label for="create-discount-value" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('value')}</label>
            <input id="create-discount-value" class="field" type="number" min="0" step="any" placeholder={createType === 'PERCENTAGE' ? 'e.g. 20' : 'e.g. 10000'} bind:value={createValue} required />
          </div>
          {#if createShowMaxAmount}
            <div>
              <label for="create-discount-max-amount" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('maxDiscountCap')} (Rp)</label>
              <input id="create-discount-max-amount" class="field" type="number" min="0" placeholder="e.g. 50000" bind:value={createMaxAmount} />
            </div>
          {/if}
        </div>

        <div class="mt-3 grid gap-3 {createShowTarget ? 'md:grid-cols-[1fr_1fr]' : 'md:grid-cols-[1fr]'}">
          <div>
            <label for="create-discount-scope" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Scope</label>
            <select id="create-discount-scope" class="field" bind:value={createScope}>
              <option value="ORDER">Order (whole cart)</option>
              <option value="ITEM">Item (specific products)</option>
            </select>
          </div>
          {#if createShowTarget}
            <div>
              <label for="create-discount-target" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('target')}</label>
              <select id="create-discount-target" class="field" bind:value={createTargetType}>
                <option value="ALL">{language.t('all')} {language.t('items')}</option>
                <option value="CATEGORY">{language.t('category')}</option>
                <option value="ITEM">{language.t('item')}</option>
              </select>
            </div>
          {/if}
        </div>

        {#if createShowCategoryPicker}
          <div class="mt-3">
            <label for="create-discount-category" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('category')}</label>
            <select id="create-discount-category" class="field" bind:value={createTargetCategoryId}>
              <option value="">{language.t('selectCategory')}</option>
              {#each categories as cat}<option value={cat.id}>{cat.icon ?? ''} {cat.name}</option>{/each}
            </select>
          </div>
        {/if}

        {#if createShowItemPicker}
          <div class="mt-3">
            <label for="create-discount-item" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('item')}</label>
            <select id="create-discount-item" class="field" bind:value={createTargetItemId}>
              <option value="">{language.t('selectItem')}</option>
              {#each items as item}<option value={item.id}>{item.name}</option>{/each}
            </select>
          </div>
        {/if}

        <div class="mt-3 grid gap-3 md:grid-cols-3">
          <div>
            <label for="create-discount-min-order" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('minOrderAmount')} (Rp)</label>
            <input id="create-discount-min-order" class="field" type="number" min="0" placeholder="e.g. 50000" bind:value={createMinOrderAmount} />
          </div>
          <div>
            <label for="create-discount-max-uses" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('maxUses')}</label>
            <input id="create-discount-max-uses" class="field" type="number" min="1" placeholder={language.t('unlimited')} bind:value={createMaxUses} />
          </div>
          <div>
            <label for="create-discount-expires-at" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('expiresAt')}</label>
            <input id="create-discount-expires-at" class="field" type="datetime-local" bind:value={createExpiresAt} />
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-5">
          <label class="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <Toggle bind:checked={createIsAutomatic} />
            {language.t('autoApplyDiscount')}
          </label>
          <label class="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <Toggle bind:checked={createIsActive} />
            {language.t('active')}
          </label>
        </div>
      </form>

      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-primary" onclick={createDiscount} disabled={creating}>{creating ? language.t('creating') : language.t('addDiscount')}</button>
      </div>
    </section>
  </div>
{/if}

<!-- Edit modal -->
{#if editingDiscount}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) cancelEdit(); }}
  >
    <section
      class="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
    >
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('editDiscount')}</h2>
          <p class="truncate text-sm text-[var(--text-muted)]">{editingDiscount.name}</p>
        </div>
        <button class="icon-btn flex-shrink-0" onclick={cancelEdit}><X size={18} /></button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto p-5">
        <div class="grid gap-3 md:grid-cols-2">
          <div>
            <label for="edit-discount-name" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('name')}</label>
            <input id="edit-discount-name" class="field" placeholder={language.t('name')} bind:value={editName} required />
          </div>
          <div>
            <label for="edit-discount-code" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('promoCode')}</label>
            <input id="edit-discount-code" class="field" placeholder={language.t('code')} bind:value={editCode} />
          </div>
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_1fr]">
          <div>
            <label for="edit-discount-type" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('type')}</label>
            <select id="edit-discount-type" class="field" bind:value={editType}>
              <option value="PERCENTAGE">{language.t('percentage')} (%)</option>
              <option value="FIXED">{language.t('fixedAmount')} (Rp)</option>
            </select>
          </div>
          <div>
            <label for="edit-discount-value" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('value')}</label>
            <input id="edit-discount-value" class="field" type="number" min="0" step="any" bind:value={editValue} required />
          </div>
          {#if editShowMaxAmount}
            <div>
              <label for="edit-discount-max-amount" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('maxDiscountCap')} (Rp)</label>
              <input id="edit-discount-max-amount" class="field" type="number" min="0" bind:value={editMaxAmount} />
            </div>
          {/if}
        </div>

        <div class="mt-3 grid gap-3 {editShowTarget ? 'md:grid-cols-[1fr_1fr]' : 'md:grid-cols-[1fr]'}">
          <div>
            <label for="edit-discount-scope" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Scope</label>
            <select id="edit-discount-scope" class="field" bind:value={editScope}>
              <option value="ORDER">Order (whole cart)</option>
              <option value="ITEM">Item (specific products)</option>
            </select>
          </div>
          {#if editShowTarget}
            <div>
            <label for="edit-discount-target" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('target')}</label>
              <select id="edit-discount-target" class="field" bind:value={editTargetType}>
                <option value="ALL">{language.t('all')} {language.t('items')}</option>
                <option value="CATEGORY">{language.t('category')}</option>
                <option value="ITEM">{language.t('item')}</option>
              </select>
            </div>
          {/if}
        </div>

        {#if editShowCategoryPicker}
          <div class="mt-3">
            <label for="edit-discount-category" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('category')}</label>
            <select id="edit-discount-category" class="field" bind:value={editTargetCategoryId}>
              <option value="">{language.t('selectCategory')}</option>
              {#each categories as cat}<option value={cat.id}>{cat.icon ?? ''} {cat.name}</option>{/each}
            </select>
          </div>
        {/if}

        {#if editShowItemPicker}
          <div class="mt-3">
            <label for="edit-discount-item" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('item')}</label>
            <select id="edit-discount-item" class="field" bind:value={editTargetItemId}>
              <option value="">{language.t('selectItem')}</option>
              {#each items as item}<option value={item.id}>{item.name}</option>{/each}
            </select>
          </div>
        {/if}

        <div class="mt-3 grid gap-3 md:grid-cols-3">
          <div>
            <label for="edit-discount-min-order" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('minOrderAmount')} (Rp)</label>
            <input id="edit-discount-min-order" class="field" type="number" min="0" bind:value={editMinOrderAmount} />
          </div>
          <div>
            <label for="edit-discount-max-uses" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('maxUses')}</label>
            <input id="edit-discount-max-uses" class="field" type="number" min="1" placeholder={language.t('unlimited')} bind:value={editMaxUses} />
          </div>
          <div>
            <label for="edit-discount-expires-at" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">{language.t('expiresAt')}</label>
            <input id="edit-discount-expires-at" class="field" type="datetime-local" bind:value={editExpiresAt} />
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-5">
          <label class="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <Toggle bind:checked={editIsAutomatic} />
            {language.t('autoApplyDiscount')}
          </label>
          <label class="flex cursor-pointer items-center gap-2 text-sm font-semibold">
            <Toggle bind:checked={editIsActive} />
            {language.t('active')}
          </label>
        </div>
      </div>

      <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
        <button
          class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100"
          onclick={openDeleteConfirm}
        >
          <Trash2 class="h-4 w-4" />
          {language.t('delete')}
        </button>
        <div class="flex flex-1 items-center justify-end gap-3">
          <button class="btn-primary" onclick={saveEdit} disabled={saving}>{saving ? language.t('saving') : language.t('saveChanges')}</button>
        </div>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Delete confirm modal ─────────────────────────────────────── -->
{#if deleteConfirmDiscount}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100">
          <Trash2 class="h-6 w-6 text-red-600" />
        </div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('deleteDiscount')}</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]">
          {language.t('deleteConfirmPrefix')}
          <strong class="text-[var(--espresso)]">{deleteConfirmDiscount.name}</strong>?
          {language.t('deleteConfirmSuffix')}
        </p>
      </div>
      <div class="flex gap-3 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={closeDeleteConfirm}>{language.t('cancel')}</button>
        <button
          class="flex-1 rounded-full bg-red-600 px-4 py-2.5 font-bold text-white transition hover:bg-red-700 disabled:opacity-50"
          disabled={deleting}
          onclick={confirmDelete}
        >{deleting ? language.t('deleting') : language.t('delete')}</button>
      </div>
    </section>
  </div>
{/if}

<style>
  .icon-btn {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--white);
    color: var(--espresso);
    cursor: pointer;
    transition: background 0.15s;
  }
  .icon-btn:hover { background: var(--cream); }
</style>
