<script lang="ts">
  import type { Snippet } from 'svelte';
  import { untrack } from 'svelte';
  import { page as pageStore } from '$app/stores';
  import PhotoField from './PhotoField.svelte';
  import Toggle from './Toggle.svelte';
  import { toAddonGroupsPayload, toItemUpdatePayload, toOptionGroupsPayload, type AddonGroupPayloadInput, type OptionGroupPayloadInput } from '$lib/api/catalog';
  import { api, mediaUrl } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Category, Item, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { getItemPrice } from '$lib/utils/catalog';
  import { formatRupiah } from '$lib/utils/format';
  import { getChoiceLabel, getChoicePrice, getGroupChoices, getGroupLabel } from '$lib/utils/modifiers';
  import { ChevronRight, ListChecks, PlusCircle, Search, SlidersHorizontal, Trash2, X } from 'lucide-svelte';

  let { tabs }: { tabs?: Snippet } = $props();

  let categories = $state<Category[]>([]);
  let items = $state<Item[]>([]);
  let name = $state('');
  let priceDisplay = $state('');
  let costDisplay = $state('');
  let editCostDisplay = $state('');
  let categoryId = $state('');
  let description = $state('');
  let error = $state('');
  let loading = $state(false);
  let addonItem = $state<Item | null>(null);
  let addonGroups = $state<AddonGroupPayloadInput[]>([]);
  let savingAddons = $state(false);
  let optionItem = $state<Item | null>(null);
  let optionGroups = $state<OptionGroupPayloadInput[]>([]);
  let savingOptions = $state(false);
  let editingItemId = $state<string | null>(null);
  let editProductName = $state('');
  let editCategoryId = $state('');
  let editStock = $state('');
  let editPriceDisplay = $state('');
  let togglingItemId = $state<string | null>(null);
  let page = $state(1);
  const limit = 20;
  let total = $state(0);
  let totalPages = $derived(Math.max(1, Math.ceil(total / limit)));
  let createStock = $state('');

  let createModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteConfirmItem = $state<Item | null>(null);
  let deleting = $state(false);
  let savingEdit = $state(false);

  let createImageFile = $state<File | null>(null);
  let editImageFile = $state<File | null>(null);
  let uploadingImage = $state(false);


  // Filters & search
  let searchQuery = $state('');
  let filterCategoryId = $state(untrack(() => $pageStore.url.searchParams.get('cat') ?? ''));
  let searchTimeout = $state<ReturnType<typeof setTimeout> | null>(null);

  let hasActiveFilter = $derived(!!filterCategoryId);

  let editingItem = $derived(items.find((i) => i.id === editingItemId) ?? null);

  function parsePrice(s: string): number {
    const n = parseInt(s.replace(/\D/g, '') || '0', 10);
    return isNaN(n) ? 0 : n;
  }

  function formatPriceDisplay(n: number): string {
    return n > 0 ? n.toLocaleString('id-ID') : '';
  }

  function onPriceInput(e: Event & { currentTarget: HTMLInputElement }): string {
    const digits = e.currentTarget.value.replace(/\D/g, '');
    const n = digits ? parseInt(digits, 10) : 0;
    const formatted = n > 0 ? n.toLocaleString('id-ID') : '';
    e.currentTarget.value = formatted;
    return formatted;
  }

  function buildItemsQuery() {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('offset', String((page - 1) * limit));
    if (filterCategoryId) params.set('category_id', filterCategoryId);
    if (searchQuery.trim()) params.set('search', searchQuery.trim());
    return params.toString();
  }

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    error = '';
    try {
      const [catsRes, itemsRes] = await Promise.all([
        api.get<PaginatedResponse<Category>>(`/stores/${storeId}/categories?limit=100`),
        api.get<PaginatedResponse<Item>>(`/stores/${storeId}/items?${buildItemsQuery()}`)
      ]);
      categories = paginatedItems(catsRes);
      items = paginatedItems(itemsRes);
      total = itemsRes.total;
      categoryId ||= categories[0]?.id ?? '';
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  function onSearchInput() {
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => { page = 1; void load(); }, 350);
  }

  async function applyFilters() {
    page = 1;
    await load();
  }

  async function clearFilters() {
    filterCategoryId = '';
    page = 1;
    await load();
  }

  async function uploadImage(itemId: string, file: File) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    const fd = new FormData();
    fd.append('file', file);
    const updated = await api.post<Item>(`/stores/${storeId}/items/${itemId}/image`, fd);
    items = items.map((i) => (i.id === itemId ? { ...i, image_url: updated.image_url } : i));
  }

  function openCreateModal() {
    name = '';
    priceDisplay = '';
    costDisplay = '';
    description = '';
    createStock = '';
    createImageFile = null;
    createModalOpen = true;
  }

  function closeCreateModal() {
    createModalOpen = false;
    createImageFile = null;
  }

  async function createItem() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    const stock = createStock === '' ? null : Math.max(0, parseInt(createStock, 10));
    const newItem = await api.post<Item>(`/stores/${storeId}/items`, { name, base_price: parsePrice(priceDisplay), cost_price: costDisplay ? parsePrice(costDisplay) : null, category_id: categoryId || null, description, is_available: true, stock });
    closeCreateModal();
    if (createImageFile) {
      try { await uploadImage(newItem.id, createImageFile); } catch { /* non-fatal */ }
    }
    await load();
  }

  async function toggleAvailable(item: Item) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    togglingItemId = item.id;
    error = '';
    try {
      await api.patch(`/stores/${storeId}/items/${item.id}`, toItemUpdatePayload({ isAvailable: !(item.is_available ?? true) }));
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      togglingItemId = null;
    }
  }

  async function removeItem(item: Item) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    await api.delete(`/stores/${storeId}/items/${item.id}`);
    await load();
  }

  function marginPct(item: Item): number | null {
    const price = getItemPrice(item);
    if (item.cost_price == null || price <= 0) return null;
    return ((price - item.cost_price) / price) * 100;
  }

  function marginLabel(item: Item) {
    const m = marginPct(item);
    return m === null ? '—' : `${m.toFixed(0)}%`;
  }

  function marginTone(item: Item) {
    const m = marginPct(item);
    if (m === null) return 'text-[var(--om-text-secondary)]';
    return m >= 50 ? 'text-[var(--om-brand)]' : m >= 25 ? 'text-[var(--om-warning)]' : 'text-[var(--om-danger)]';
  }

  function categoryNameFor(item: Item) {
    return categories.find((category) => category.id === item.category_id)?.name ?? '';
  }

  function optionSummaryFor(item: Item) {
    return (item.option_groups ?? []).map((group) => getGroupLabel(group)).join(', ');
  }

  function addonSummaryFor(item: Item) {
    return (item.addon_groups ?? []).map((group) => getGroupLabel(group)).join(', ');
  }

  function openEditModal(item: Item) {
    editingItemId = item.id;
    editProductName = item.name;
    editCategoryId = item.category_id ?? '';
    editStock = item.stock !== null && item.stock !== undefined ? String(item.stock) : '';
    editPriceDisplay = formatPriceDisplay(getItemPrice(item));
    editCostDisplay = formatPriceDisplay(item.cost_price ?? 0);
    editImageFile = null;
    editModalOpen = true;
  }

  function closeEditModal() {
    editModalOpen = false;
    editingItemId = null;
    editProductName = '';
    editCategoryId = '';
    editStock = '';
    editPriceDisplay = '';
    editCostDisplay = '';
    editImageFile = null;
  }

  async function removeItemImage() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !editingItemId) return;
    uploadingImage = true;
    try {
      await api.delete(`/stores/${storeId}/items/${editingItemId}/image`);
      items = items.map((i) => (i.id === editingItemId ? { ...i, image_url: null } : i));
    } finally {
      uploadingImage = false;
    }
  }

  async function saveProductEdit() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !editingItemId) return;
    savingEdit = true;
    try {
      const stock = editStock === '' ? null : Math.max(0, parseInt(editStock, 10));
      const imageFile = editImageFile;
      await Promise.all([
        api.patch(`/stores/${storeId}/items/${editingItemId}`, { ...toItemUpdatePayload({ name: editProductName, categoryId: editCategoryId, basePrice: parsePrice(editPriceDisplay) }), cost_price: editCostDisplay ? parsePrice(editCostDisplay) : null }),
        api.patch(`/stores/${storeId}/items/${editingItemId}/stock`, { stock })
      ]);
      if (imageFile) {
        uploadingImage = true;
        try { await uploadImage(editingItemId, imageFile); } catch { /* non-fatal */ } finally { uploadingImage = false; }
      }
      closeEditModal();
      await load();
    } finally {
      savingEdit = false;
    }
  }

  function openOptionEditorFromEdit() {
    const item = editingItem;
    if (!item) return;
    closeEditModal();
    optionItem = item;
    optionGroups = (item.option_groups ?? []).map((group) => ({
      name: getGroupLabel(group),
      required: Boolean(group.required),
      choices: getGroupChoices(group).map((choice) => ({ name: getChoiceLabel(choice) }))
    }));
    if (optionGroups.length === 0) addOptionGroup();
  }

  function openAddonEditorFromEdit() {
    const item = editingItem;
    if (!item) return;
    closeEditModal();
    addonItem = item;
    addonGroups = (item.addon_groups ?? []).map((group) => ({
      name: getGroupLabel(group),
      min_select: group.min_select ?? 0,
      max_select: group.max_select ?? null,
      choices: getGroupChoices(group).map((choice) => ({
        name: getChoiceLabel(choice),
        extra_price: getChoicePrice(choice)
      }))
    }));
    if (addonGroups.length === 0) addAddonGroup();
  }

  function closeOptionEditor() {
    optionItem = null;
    optionGroups = [];
  }

  function addOptionGroup() {
    optionGroups.push({ name: language.t('options'), required: true, choices: [{ name: '' }] });
  }

  function removeOptionGroup(index: number) {
    optionGroups = optionGroups.filter((_, i) => i !== index);
  }

  function addOptionChoice(groupIndex: number) {
    optionGroups[groupIndex].choices.push({ name: '' });
  }

  function removeOptionChoice(groupIndex: number, choiceIndex: number) {
    optionGroups[groupIndex].choices = optionGroups[groupIndex].choices.filter((_, i) => i !== choiceIndex);
  }

  async function saveOptions() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !optionItem) return;
    savingOptions = true;
    error = '';
    try {
      await api.put(`/stores/${storeId}/items/${optionItem.id}/option-groups`, {
        option_groups: toOptionGroupsPayload(optionGroups)
      });
      closeOptionEditor();
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      savingOptions = false;
    }
  }

  function closeAddonEditor() {
    addonItem = null;
    addonGroups = [];
  }

  function addAddonGroup() {
    addonGroups.push({ name: 'Add-ons', min_select: 0, max_select: null, choices: [{ name: '', extra_price: 0 }] });
  }

  function removeAddonGroup(index: number) {
    addonGroups = addonGroups.filter((_, i) => i !== index);
  }

  function addAddonChoice(groupIndex: number) {
    addonGroups[groupIndex].choices.push({ name: '', extra_price: 0 });
  }

  function removeAddonChoice(groupIndex: number, choiceIndex: number) {
    addonGroups[groupIndex].choices = addonGroups[groupIndex].choices.filter((_, i) => i !== choiceIndex);
  }

  async function saveAddons() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !addonItem) return;
    savingAddons = true;
    error = '';
    try {
      await api.put(`/stores/${storeId}/items/${addonItem.id}/addon-groups`, {
        addon_groups: toAddonGroupsPayload(addonGroups)
      });
      closeAddonEditor();
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      savingAddons = false;
    }
  }

  function openDeleteConfirm() {
    const toDelete = editingItem;
    if (!toDelete) return;
    closeEditModal();
    deleteConfirmItem = toDelete;
  }

  function closeDeleteConfirm() {
    deleteConfirmItem = null;
  }

  async function confirmDelete() {
    if (!deleteConfirmItem) return;
    deleting = true;
    try {
      await removeItem(deleteConfirmItem);
      deleteConfirmItem = null;
    } finally {
      deleting = false;
    }
  }

  async function goToPage(newPage: number) {
    page = newPage;
    await load();
  }

  $effect(() => { if (session.selectedStore?.id) { page = 1; untrack(() => void load()); } });
</script>

<div class="mb-4 flex flex-wrap items-center gap-2.5">
  {@render tabs?.()}
  <div class="flex flex-wrap gap-1.5" role="group" aria-label={language.t('category')}>
    {#each [{ id: '', name: language.t('allCategories') }, ...categories] as cat}
      {@const active = filterCategoryId === cat.id}
      <button
        class="rounded-[20px] border-2 px-3 font-medium transition-colors {active ? 'border-[var(--om-brand)] bg-[var(--om-brand-tint)] text-[var(--om-ink)]' : 'border-[var(--om-border)] bg-white text-[var(--om-ink-2)] hover:border-[var(--om-ink)]'}"
        style="min-height: var(--om-tap)"
        aria-pressed={active}
        onclick={() => { filterCategoryId = cat.id; applyFilters(); }}
      >{cat.name}</button>
    {/each}
  </div>
  <div class="flex-1"></div>
  <div class="flex w-full items-center gap-2 rounded-[10px] border border-[var(--om-border)] bg-white px-3 sm:w-[160px]" style="min-height: var(--om-tap)">
    <span class="ms !text-[20px] text-[var(--om-text-secondary)]">search</span>
    <input
      class="min-w-0 flex-1 bg-transparent text-[16px] outline-none"
      type="search"
      placeholder={language.t('searchProducts')}
      aria-label={language.t('searchProducts')}
      bind:value={searchQuery}
      oninput={onSearchInput}
    />
  </div>
  <button class="btn-primary flex items-center gap-1.5 !rounded-[10px]" onclick={openCreateModal}>
    <span class="ms !text-[20px] text-[var(--om-brand-on-dark)]">add</span>{language.t('add')}
  </button>
</div>

{#if error}
  <div role="alert" class="mb-4 flex items-center gap-2 rounded-[12px] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)]"><span class="ms">error</span>{error}</div>
{/if}

<section class="card overflow-hidden">
  <div class="hidden grid-cols-[1fr_120px_120px_90px_150px_28px] gap-3.5 border-b border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-[18px] py-3 text-[12px] text-[var(--om-text-secondary)] lg:grid">
    <span>{language.t('products')}</span><span class="text-right">{language.t('price')}</span><span class="text-right">HPP</span><span class="text-right">Margin</span><span>{language.t('status')}</span><span></span>
  </div>

  {#each items as item}
    <div
      class="group flex cursor-pointer items-center gap-3 border-b border-[var(--om-divider)] px-[18px] py-3 transition-colors last:border-0 hover:bg-[var(--om-bg)] lg:grid lg:grid-cols-[1fr_120px_120px_90px_150px_28px] lg:gap-3.5"
      style="min-height: var(--om-tap)"
      role="button"
      tabindex="0"
      onclick={() => openEditModal(item)}
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openEditModal(item); } }}
      aria-label={`Edit ${item.name}`}
    >
      <div class="flex min-w-0 flex-1 items-center gap-3">
        <div class="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-[10px] bg-[var(--om-fill-image)]">
          {#if item.image_url}
            <img src={mediaUrl(item.image_url)} alt={item.name} class="h-full w-full object-cover" />
          {:else}
            <span class="ms !text-[24px] text-[var(--om-text-secondary)] opacity-50" aria-hidden="true">image</span>
          {/if}
        </div>
        <div class="min-w-0">
          <div class="truncate text-[16px] font-medium">{item.name}</div>
          <div class="mt-0.5 flex flex-wrap items-center gap-1.5 text-[12px] text-[var(--om-text-secondary)]">
            <span>{categoryNameFor(item) || language.t('noCategory')}</span>
            {#if item.stock !== null && item.stock !== undefined}
              <span class="rounded-[20px] px-[9px] py-[2px] font-semibold {item.stock === 0 ? 'bg-[var(--om-danger-tint)] text-[var(--om-danger)]' : 'bg-[var(--om-brand-tint)] text-[var(--om-brand)]'}">{item.stock} stok</span>
            {/if}
          </div>
          <div class="mt-0.5 text-[12px] tabular-nums text-[var(--om-text-secondary)] lg:hidden">
            {formatRupiah(getItemPrice(item))}{#if item.cost_price != null} · HPP {formatRupiah(item.cost_price)}{/if}
          </div>
        </div>
      </div>

      <div class="hidden text-right text-[16px] font-semibold lg:block">{formatRupiah(getItemPrice(item))}</div>
      <div class="hidden text-right text-[14px] lg:block">{item.cost_price != null ? formatRupiah(item.cost_price) : '—'}</div>
      <div class="hidden text-right text-[14px] font-semibold lg:block {marginTone(item)}">{marginLabel(item)}</div>

      <div class="flex items-center gap-1.5">
        <Toggle
          checked={item.is_available !== false}
          disabled={togglingItemId === item.id}
          label={language.t('status')}
          onchange={() => toggleAvailable(item)}
        />
        <span class="hidden text-[12px] text-[var(--om-text-secondary)] sm:inline">{item.is_available === false ? language.t('unavailable') : language.t('available')}</span>
      </div>

      <span class="ms hidden text-[var(--om-text-secondary)] opacity-40 transition-opacity group-hover:opacity-100 lg:block">chevron_right</span>
    </div>
  {:else}
    <div class="p-5 text-[16px] text-[var(--om-text-secondary)]">{loading ? language.t('loading') : (hasActiveFilter || searchQuery) ? language.t('noProductsMatch') : language.t('noProductsFound')}</div>
  {/each}
</section>

{#if totalPages > 1}
  <div class="mt-4 flex items-center justify-between gap-3 text-sm">
    <span class="text-[var(--text-muted)]">{language.t('page')} {page} {language.t('of')} {totalPages}</span>
    <div class="flex gap-2">
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>{language.t('previous')}</button>
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>{language.t('next')}</button>
    </div>
  </div>
{/if}

<!-- ─── Create product modal ─────────────────────────────────────── -->
{#if createModalOpen}
  <div class="fixed inset-0 z-50 flex justify-end bg-[var(--om-scrim)]"
       role="presentation"
       onclick={(e) => { if (e.target === e.currentTarget) closeCreateModal(); }}>
    <section class="flex h-full w-full max-w-[440px] flex-col overflow-hidden bg-white shadow-[var(--om-sh-drawer)]" style="animation: omUp .2s ease" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="flex-1 text-[16px] font-semibold">{language.t('newProduct')}</h2>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeCreateModal} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
      </div>
      <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
        <PhotoField bind:file={createImageFile} uploading={false} />
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('name')}</span>
          <input class="field" placeholder={language.t('productPlaceholder')} bind:value={name} required />
        </label>
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('price')} (Rp)</span>
          <input class="field" type="text" inputmode="numeric" placeholder="0" value={priceDisplay} oninput={(e) => { priceDisplay = onPriceInput(e); }} />
        </label>
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">HPP (Rp)</span>
          <input class="field" type="text" inputmode="numeric" placeholder="0" value={costDisplay} oninput={(e) => { costDisplay = onPriceInput(e); }} />
        </label>
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('category')}</span>
          <select class="field" bind:value={categoryId}>
            <option value="">{language.t('noCategory')}</option>
            {#each categories as category}<option value={category.id}>{category.name}</option>{/each}
          </select>
        </label>
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('description')}</span>
          <input class="field" placeholder={language.t('shortDescriptionPlaceholder')} bind:value={description} />
        </label>
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('stock')}</span>
          <input class="field" type="number" min="0" step="1" placeholder="—" bind:value={createStock} />
        </label>
      </div>
      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-primary" onclick={createItem}>{language.t('addProduct')}</button>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Edit product modal ────────────────────────────────────────── -->
{#if editModalOpen}
  <div class="fixed inset-0 z-50 flex justify-end bg-[var(--om-scrim)]"
       role="presentation"
       onclick={(e) => { if (e.target === e.currentTarget) closeEditModal(); }}>
    <section class="flex h-full w-full max-w-[440px] flex-col overflow-hidden bg-white shadow-[var(--om-sh-drawer)]" style="animation: omUp .2s ease" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="min-w-0 flex-1 truncate text-[16px] font-semibold">{language.t('editProduct')}</h2>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeEditModal} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
      </div>

      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        <!-- Basic fields -->
        <div class="space-y-3">
          <PhotoField bind:file={editImageFile} currentUrl={editingItem?.image_url ? mediaUrl(editingItem.image_url) : null} uploading={uploadingImage} onremove={removeItemImage} />
          <label class="block">
            <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('name')}</span>
            <input class="field" placeholder={language.t('productPlaceholder')} bind:value={editProductName} required />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('price')} (Rp)</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={editPriceDisplay} oninput={(e) => { editPriceDisplay = onPriceInput(e); }} />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">HPP (Rp)</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={editCostDisplay} oninput={(e) => { editCostDisplay = onPriceInput(e); }} />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('category')}</span>
            <select class="field" bind:value={editCategoryId}>
              <option value="">{language.t('noCategory')}</option>
              {#each categories as category}<option value={category.id}>{category.name}</option>{/each}
            </select>
          </label>
          <label class="block">
            <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('stock')}</span>
            <input class="field" type="number" min="0" step="1" placeholder="—" bind:value={editStock} />
          </label>
        </div>

        <!-- Modifier editors -->
        <div>
          <p class="mb-2 text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('options')} / {language.t('addons')}</p>
          <div class="overflow-hidden rounded-2xl border border-[var(--border)]">
            <button
              class="flex w-full items-center gap-3 bg-[var(--white)] px-4 py-3.5 text-left transition-colors hover:bg-[var(--cream)]"
              onclick={openOptionEditorFromEdit}
            >
              <div class="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-blue-100 text-blue-600">
                <ListChecks class="h-4 w-4" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-bold text-[var(--espresso)]">{language.t('manageOptions')}</div>
                <div class="truncate text-xs text-[var(--text-muted)]">
                  {editingItem && optionSummaryFor(editingItem) ? optionSummaryFor(editingItem) : 'Size, sugar level, temperature...'}
                </div>
              </div>
              <ChevronRight class="h-4 w-4 shrink-0 text-[var(--text-muted)]" />
            </button>
            <div class="mx-4 h-px bg-[var(--border)]"></div>
            <button
              class="flex w-full items-center gap-3 bg-[var(--white)] px-4 py-3.5 text-left transition-colors hover:bg-[var(--cream)]"
              onclick={openAddonEditorFromEdit}
            >
              <div class="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-amber-100 text-amber-600">
                <PlusCircle class="h-4 w-4" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-bold text-[var(--espresso)]">{language.t('manageAddons')}</div>
                <div class="truncate text-xs text-[var(--text-muted)]">
                  {editingItem && addonSummaryFor(editingItem) ? addonSummaryFor(editingItem) : 'Extra shots, toppings...'}
                </div>
              </div>
              <ChevronRight class="h-4 w-4 shrink-0 text-[var(--text-muted)]" />
            </button>
          </div>
        </div>
      </div>

      <!-- Footer: delete left, save right -->
      <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
        <button
          class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100"
          onclick={openDeleteConfirm}
        >
          <Trash2 class="h-4 w-4" />
          {language.t('delete')}
        </button>
        <div class="flex flex-1 items-center justify-end gap-3">
          <button class="btn-primary" disabled={savingEdit} onclick={saveProductEdit}>
            {savingEdit ? language.t('saving') : language.t('saveChanges')}
          </button>
        </div>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Delete confirm modal ─────────────────────────────────────── -->
{#if deleteConfirmItem}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pt-7 pb-5 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100">
          <Trash2 class="h-6 w-6 text-red-600" />
        </div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('deleteProduct')}</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]">
          {language.t('deleteConfirmPrefix')}
          <strong class="text-[var(--espresso)]">{deleteConfirmItem.name}</strong>?
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

<!-- ─── Addon editor modal ────────────────────────────────────────── -->
{#if addonItem}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center">
    <section class="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true" tabindex="-1">
      <div class="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div class="min-w-0 flex-1">
          <h2 class="display-font truncate text-xl font-bold text-[var(--espresso)]">{language.t('addons')} - {addonItem.name}</h2>
          <p class="text-xs text-[var(--text-muted)]">{language.t('addons')}</p>
        </div>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeAddonEditor} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
      </div>

      <div class="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {#each addonGroups as group, groupIndex}
          <div class="rounded-xl border border-[var(--border)] bg-[var(--cream)] p-3">
            <!-- Group header: name + min + max + delete — always one row -->
            <div class="mb-2 flex items-end gap-1.5">
              <div class="min-w-0 flex-1">
                <span class="mb-0.5 block text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('name')}</span>
                <input class="field min-w-0 w-full py-2 text-sm" placeholder="e.g. Toppings" bind:value={group.name} />
              </div>
              <div class="w-14 shrink-0">
                <span class="mb-0.5 block text-center text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('min')}</span>
                <input class="field py-2 text-center text-sm" type="number" min="0" placeholder="0" bind:value={group.min_select} />
              </div>
              <div class="w-14 shrink-0">
                <span class="mb-0.5 block text-center text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('max')}</span>
                <input class="field py-2 text-center text-sm" type="number" min="0" placeholder="∞" bind:value={group.max_select} />
              </div>
              <button
                class="mb-0.5 grid h-[2.375rem] w-8 shrink-0 place-items-center rounded-lg border border-red-200 bg-red-50 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600"
                title={language.t('removeGroup')}
                onclick={() => removeAddonGroup(groupIndex)}
              ><Trash2 class="h-3.5 w-3.5" /></button>
            </div>
            <!-- Column labels -->
            <div class="mb-1 flex items-center gap-1.5 px-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">
              <span class="flex-1">{language.t('name')}</span>
              <span class="w-[6.5rem] shrink-0 text-right">{language.t('price')} (Rp)</span>
              <span class="w-8 shrink-0"></span>
            </div>
            <!-- Choice rows -->
            <div class="space-y-1">
              {#each group.choices as choice, choiceIndex}
                <div class="flex items-center gap-1.5">
                  <input class="field min-w-0 flex-1 py-2 text-sm" placeholder="e.g. Extra Shot" bind:value={choice.name} />
                  <div class="w-[6.5rem] shrink-0">
                    <input class="field py-2 text-right text-sm" type="number" min="0" placeholder="0" bind:value={choice.extra_price} />
                  </div>
                  <button
                    class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--border)] text-[var(--text-muted)] transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-500"
                    title={language.t('removeChoice')}
                    onclick={() => removeAddonChoice(groupIndex, choiceIndex)}
                  ><X class="h-3.5 w-3.5" /></button>
                </div>
              {/each}
            </div>
            <button class="mt-2 text-xs font-bold text-[var(--warm-brown)] hover:text-[var(--espresso)] transition-colors" onclick={() => addAddonChoice(groupIndex)}>+ {language.t('addChoice')}</button>
          </div>
        {/each}
        <button class="btn-outline px-3 py-2 text-sm" onclick={addAddonGroup}>+ {language.t('addAddonGroup')}</button>
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-[var(--border)] px-4 py-3">
        <button class="btn-primary px-4 py-2 text-sm" disabled={savingAddons} onclick={saveAddons}>{savingAddons ? language.t('saving') : language.t('saveChanges')}</button>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Option editor modal ───────────────────────────────────────── -->
{#if optionItem}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center">
    <section class="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true" tabindex="-1">
      <div class="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div class="min-w-0 flex-1">
          <h2 class="display-font truncate text-xl font-bold text-[var(--espresso)]">{language.t('options')} - {optionItem.name}</h2>
          <p class="text-xs text-[var(--text-muted)]">{language.t('manageOptions')}</p>
        </div>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeOptionEditor} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
      </div>

      <div class="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {#each optionGroups as group, groupIndex}
          <div class="rounded-xl border border-[var(--border)] bg-[var(--cream)] p-3">
            <!-- Group header: name + required checkbox + delete — always one row -->
            <div class="mb-2 flex items-center gap-1.5">
              <input class="field min-w-0 flex-1 py-2 text-sm" placeholder={language.t('groupNamePlaceholder')} bind:value={group.name} />
              <label class="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-2.5 py-2 text-xs font-bold text-[var(--espresso)] transition-colors hover:bg-[var(--cream)]">
                <input type="checkbox" bind:checked={group.required} class="accent-[var(--espresso)]" />
                {language.t('required')}
              </label>
              <button
                class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-red-200 bg-red-50 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600"
                title={language.t('removeGroup')}
                onclick={() => removeOptionGroup(groupIndex)}
              ><Trash2 class="h-3.5 w-3.5" /></button>
            </div>
            <!-- Choice rows -->
            <div class="space-y-1">
              {#each group.choices as choice, choiceIndex}
                <div class="flex items-center gap-1.5">
                  <input class="field min-w-0 flex-1 py-2 text-sm" placeholder="e.g. Less Sugar" bind:value={choice.name} />
                  <button
                    class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--border)] text-[var(--text-muted)] transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-500"
                    title={language.t('removeChoice')}
                    onclick={() => removeOptionChoice(groupIndex, choiceIndex)}
                  ><X class="h-3.5 w-3.5" /></button>
                </div>
              {/each}
            </div>
            <button class="mt-2 text-xs font-bold text-[var(--warm-brown)] hover:text-[var(--espresso)] transition-colors" onclick={() => addOptionChoice(groupIndex)}>+ {language.t('addChoice')}</button>
          </div>
        {/each}
        <button class="btn-outline px-3 py-2 text-sm" onclick={addOptionGroup}>+ {language.t('addOptionGroup')}</button>
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-[var(--border)] px-4 py-3">
        <button class="btn-primary px-4 py-2 text-sm" disabled={savingOptions} onclick={saveOptions}>{savingOptions ? language.t('saving') : language.t('saveChanges')}</button>
      </div>
    </section>
  </div>
{/if}
