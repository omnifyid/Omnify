<script lang="ts">
  import type { Snippet } from 'svelte';
  import { untrack } from 'svelte';
  import { page as pageStore } from '$app/stores';
  import PhotoField from './PhotoField.svelte';
  import Toggle from './Toggle.svelte';
  import { toAddonGroupsPayload, toItemUpdatePayload, toOptionGroupsPayload, type AddonGroupPayloadInput, type OptionGroupPayloadInput } from '$lib/api/catalog';
  import { api, mediaUrl } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { BranchSetting, Category, ChannelSetting, Ingredient, Item, OrderChannel, PaginatedResponse, RecipeLine } from '$lib/api/types';
  import IngredientPicker from '$lib/components/IngredientPicker.svelte';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { getItemPrice } from '$lib/utils/catalog';
  import { formatRupiah } from '$lib/utils/format';
  import { chip, CHIP_ROW, SEG_GROUP, seg } from '$lib/utils/ui';
  import CatalogNotice from './CatalogNotice.svelte';
  import { getChoiceLabel, getChoicePrice, getGroupChoices, getGroupLabel } from '$lib/utils/modifiers';

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
  let addonGroups = $state<AddonGroupPayloadInput[]>([]);
  // option choices are edited as tags; `draft` is the text being typed for a new tag
  type OptionEditGroup = OptionGroupPayloadInput & { draft: string };
  let optionGroups = $state<OptionEditGroup[]>([]);
  // manual per-platform prices (edit modal)
  const CHANNEL_NAMES: Record<OrderChannel, string> = { GOFOOD: 'GoFood', GRABFOOD: 'GrabFood', SHOPEEFOOD: 'ShopeeFood' };
  let channelSettings = $state<ChannelSetting[]>([]);
  let enabledChannels = $derived(channelSettings.filter((c) => c.enabled));
  let gridCols = $derived(`1fr 120px ${enabledChannels.map(() => '110px ').join('')}120px 90px 150px 28px`);

  /** Platform price shown in the list: manual if set, otherwise the automatic markup price. */
  function channelPriceFor(item: Item, c: ChannelSetting) {
    const manual = item.channel_prices?.[c.channel];
    return { value: manual || autoChannelPrice(getItemPrice(item), c.markup_bp), manual: !!manual };
  }

  let editChannelPrices = $state<Partial<Record<OrderChannel, string>>>({});

  /** Automatic platform price: price × (1 + markup), rounded up to Rp500 (mirrors the backend). */
  function autoChannelPrice(price: number, markupBp: number) {
    if (!markupBp || price <= 0) return price;
    return Math.ceil((price * (10000 + markupBp)) / (10000 * 500)) * 500;
  }

  type RecipeEditLine = { ingredient_id: string; name: string; unit: string; cost_price: number; quantity: string };
  let recipeLines = $state<RecipeEditLine[]>([]);
  let editingItemId = $state<string | null>(null);
  let editProductName = $state('');
  let editCategoryId = $state('');
  let editStock = $state('');
  // per-branch sold toggle and price override (only shown when the business has several branches)
  let editBranches = $state<Array<BranchSetting & { priceDisplay: string }>>([]);
  let editPriceDisplay = $state('');
  let editTab = $state<'recipe' | 'options' | 'addons'>('recipe');
  // branches follow the parent store's catalog; only their sold toggle and price are editable
  let catalogLocked = $derived(session.selectedStore?.is_parent === false);
  // recipes are edited on the parent store only; branches follow it
  let editIsParent = $derived(editBranches.find((b) => b.store_id === session.selectedStore?.id)?.is_parent ?? true);
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
      channelSettings = await api.get<ChannelSetting[]>(`/stores/${storeId}/channels`).catch(() => []);
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
    editTab = 'recipe';
    error = '';
    editProductName = item.name;
    editCategoryId = item.category_id ?? '';
    editStock = item.stock !== null && item.stock !== undefined ? String(item.stock) : '';
    editPriceDisplay = formatPriceDisplay(item.base_price ?? getItemPrice(item));
    void loadBranches(item.id);
    void loadRecipe(item.id);
    optionGroups = (item.option_groups ?? []).map((group) => ({
      name: getGroupLabel(group),
      required: Boolean(group.is_required ?? group.required),
      draft: '',
      choices: getGroupChoices(group).map((choice) => ({ name: getChoiceLabel(choice), is_default: Boolean((choice as { is_default?: boolean }).is_default) }))
    }));
    addonGroups = (item.addon_groups ?? []).map((group) => ({
      name: getGroupLabel(group),
      min_select: group.min_select ?? 0,
      max_select: group.max_select ?? null,
      choices: getGroupChoices(group).map((choice) => ({ name: getChoiceLabel(choice), extra_price: getChoicePrice(choice) }))
    }));
    editCostDisplay = formatPriceDisplay(item.cost_price ?? 0);
    editChannelPrices = Object.fromEntries(Object.entries(item.channel_prices ?? {}).map(([k, v]) => [k, formatPriceDisplay(v ?? 0)]));
    editImageFile = null;
    editModalOpen = true;
  }

  async function loadBranches(itemId: string) {
    const storeId = session.selectedStore?.id;
    editBranches = [];
    if (!storeId) return;
    try {
      const rows = await api.get<BranchSetting[]>(`/stores/${storeId}/items/${itemId}/branches`);
      if (editingItemId !== itemId) return;
      editBranches = rows.map((r) => ({ ...r, priceDisplay: formatPriceDisplay(r.price ?? 0) }));
    } catch { /* branch settings are optional */ }
  }

  function closeEditModal() {
    editBranches = [];
    recipeLines = [];
    optionGroups = [];
    addonGroups = [];
    editModalOpen = false;
    editingItemId = null;
    editProductName = '';
    editCategoryId = '';
    editStock = '';
    editPriceDisplay = '';
    editCostDisplay = '';
    editChannelPrices = {};
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
    error = '';
    optionGroups.forEach((_, i) => commitOptionDraft(i));
    try {
      const stock = editStock === '' ? null : Math.max(0, parseInt(editStock, 10));
      const imageFile = editImageFile;
      // a branch only saves its own sold toggle and price; the catalog belongs to the parent store
      const catalogCalls: Promise<unknown>[] = catalogLocked ? [] : [
        api.patch(`/stores/${storeId}/items/${editingItemId}`, { ...toItemUpdatePayload({ name: editProductName, categoryId: editCategoryId, basePrice: parsePrice(editPriceDisplay) }), cost_price: editCostDisplay ? parsePrice(editCostDisplay) : null }),
        api.patch(`/stores/${storeId}/items/${editingItemId}/stock`, { stock }),
        api.put(`/stores/${storeId}/items/${editingItemId}/option-groups`, toOptionGroupsPayload(optionGroups)),
        api.put(`/stores/${storeId}/items/${editingItemId}/addon-groups`, toAddonGroupsPayload(addonGroups)),
        editIsParent
          ? api.put(`/stores/${storeId}/items/${editingItemId}/recipe`, {
              lines: recipeLines
                .map((l) => ({ ingredient_id: l.ingredient_id, quantity: parseFloat(l.quantity.replace(',', '.')) }))
                .filter((l) => l.ingredient_id && l.quantity > 0)
            })
          : Promise.resolve(),
        // PUT replaces all platform prices, so start from the saved ones and apply the edited platforms
        enabledChannels.length
          ? api.put(`/stores/${storeId}/items/${editingItemId}/channel-prices`, {
              prices: {
                ...(editingItem?.channel_prices ?? {}),
                ...Object.fromEntries(enabledChannels.map((c) => [c.channel, parsePrice(editChannelPrices[c.channel] ?? '') || null]))
              }
            })
          : Promise.resolve()
      ];
      await Promise.all([
        ...catalogCalls,
        editBranches.length
          ? api.put(`/stores/${storeId}/items/${editingItemId}/branches`, {
              branches: editBranches.map((b) => ({ store_id: b.store_id, is_sold: b.is_sold, price: parsePrice(b.priceDisplay) || null }))
            })
          : Promise.resolve()
      ]);
      if (imageFile && !catalogLocked) {
        uploadingImage = true;
        try { await uploadImage(editingItemId, imageFile); } catch { /* non-fatal */ } finally { uploadingImage = false; }
      }
      closeEditModal();
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      savingEdit = false;
    }
  }

  async function loadRecipe(itemId: string) {
    const storeId = session.selectedStore?.id;
    recipeLines = [];
    if (!storeId) return;
    try {
      const lines = await api.get<RecipeLine[]>(`/stores/${storeId}/items/${itemId}/recipe`);
      if (editingItemId !== itemId) return;
      recipeLines = lines.map((l) => ({ ingredient_id: l.ingredient_id, name: l.ingredient_name, unit: l.unit, cost_price: l.cost_price, quantity: String(l.quantity) }));
    } catch { /* recipe is optional */ }
  }

  function addRecipeLine(ing: Ingredient) {
    recipeLines.push({ ingredient_id: ing.id, name: ing.name, unit: ing.unit, cost_price: ing.cost_price, quantity: '' });
  }

  let recipeCost = $derived(
    recipeLines.reduce((sum, l) => {
      const q = parseFloat(l.quantity.replace(',', '.'));
      return sum + (q > 0 ? l.cost_price * q : 0);
    }, 0)
  );

  let editHpp = $derived(recipeLines.length ? Math.round(recipeCost) : parsePrice(editCostDisplay));
  let editMargin = $derived.by(() => {
    const price = parsePrice(editPriceDisplay);
    return price > 0 && editHpp > 0 ? Math.round(((price - editHpp) / price) * 100) : null;
  });

  function addOptionGroup() {
    optionGroups.push({ name: language.t('options'), required: true, draft: '', choices: [] });
  }

  function removeOptionGroup(index: number) {
    optionGroups = optionGroups.filter((_, i) => i !== index);
  }

  /** Turns the typed text (comma separated) into tags, skipping blanks and duplicates. */
  function commitOptionDraft(groupIndex: number) {
    const group = optionGroups[groupIndex];
    for (const part of group.draft.split(',')) {
      const name = part.trim();
      if (name && !group.choices.some((c) => c.name.toLowerCase() === name.toLowerCase())) group.choices.push({ name, is_default: false });
    }
    group.draft = '';
  }

  /** One default per group (options are single-choice); tapping the default again clears it. */
  function toggleOptionDefault(groupIndex: number, choiceIndex: number) {
    const choices = optionGroups[groupIndex].choices;
    const makeDefault = !choices[choiceIndex].is_default;
    choices.forEach((c, i) => { c.is_default = makeDefault && i === choiceIndex; });
  }

  function removeOptionChoice(groupIndex: number, choiceIndex: number) {
    optionGroups[groupIndex].choices = optionGroups[groupIndex].choices.filter((_, i) => i !== choiceIndex);
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
  {#if !catalogLocked}
  <button class="btn-primary flex items-center gap-1.5 !rounded-[10px]" onclick={openCreateModal}>
    <span class="ms !text-[20px] text-[var(--om-brand-on-dark)]">add</span>{language.t('add')}
  </button>
  {/if}
</div>

<CatalogNotice />

{#if error}
  <div role="alert" class="mb-4 flex items-center gap-2 rounded-[12px] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)]"><span class="ms">error</span>{error}</div>
{/if}

<section class="card overflow-hidden">
  <div class="hidden gap-3.5 border-b border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-[18px] py-3 text-[12px] text-[var(--om-text-secondary)] lg:grid" style="grid-template-columns: {gridCols}">
    <span>{language.t('products')}</span><span class="text-right">{language.t('price')}</span>{#each enabledChannels as c (c.channel)}<span class="text-right">{CHANNEL_NAMES[c.channel]}</span>{/each}<span class="text-right">HPP</span><span class="text-right">Margin</span><span>{language.t('status')}</span><span></span>
  </div>

  {#each items as item}
    <div
      class="group flex cursor-pointer items-center gap-3 border-b border-[var(--om-divider)] px-[18px] py-3 transition-colors last:border-0 hover:bg-[var(--om-bg)] lg:grid lg:gap-3.5 lg:[grid-template-columns:var(--cols)]"
      style="min-height: var(--om-tap); --cols: {gridCols}"
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
          {#if enabledChannels.length}
            <div class="mt-0.5 flex flex-wrap gap-x-3 text-[12px] tabular-nums text-[var(--om-text-secondary)] lg:hidden">
              {#each enabledChannels as c (c.channel)}<span>{CHANNEL_NAMES[c.channel]} {formatRupiah(channelPriceFor(item, c).value)}</span>{/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="hidden text-right text-[16px] font-semibold lg:block">{formatRupiah(getItemPrice(item))}</div>
      {#each enabledChannels as c (c.channel)}
        {@const cp = channelPriceFor(item, c)}
        <div class="hidden text-right text-[14px] tabular-nums lg:block {cp.manual ? 'font-semibold' : 'text-[var(--om-text-secondary)]'}" title={cp.manual ? language.t('channelPriceManual') : language.t('channelPriceAuto')}>{formatRupiah(cp.value)}</div>
      {/each}
      <div class="hidden text-right text-[14px] lg:block">{item.cost_price != null ? formatRupiah(item.cost_price) : '—'}</div>
      <div class="hidden text-right text-[14px] font-semibold lg:block {marginTone(item)}">{marginLabel(item)}</div>

      <div class="flex items-center gap-1.5">
        <Toggle
          checked={item.is_available !== false}
          disabled={togglingItemId === item.id || catalogLocked}
          label={language.t('status')}
          onchange={() => toggleAvailable(item)}
        />
        {#if item.is_sold === false}<span class="rounded-full bg-[var(--om-fill-muted)] px-2 py-0.5 text-[12px] font-semibold text-[var(--om-text-secondary)]">{language.t('notSoldHere')}</span>{/if}
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
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeCreateModal} aria-label={language.t('close')}><span class="ms !text-[16px]" aria-hidden="true">close</span></button>
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

<!-- ─── Edit product (full screen, like new-ui) ───────────────────── -->
{#if editModalOpen}
  <div class="fixed inset-0 z-[56] flex flex-col bg-[var(--om-bg)]" role="dialog" aria-modal="true" aria-label={language.t('editProduct')}>
    <div class="flex shrink-0 items-center gap-2 border-b border-[var(--om-border)] bg-white px-3 py-2.5 md:px-5">
      <button class="grid h-11 w-11 place-items-center rounded-[10px] hover:bg-[var(--om-fill-hover)]" onclick={closeEditModal} aria-label={language.t('close')}><span class="ms">close</span></button>
      <div class="min-w-0 flex-1">
        <div class="truncate text-[20px] font-bold">{editProductName || language.t('editProduct')}</div>
        <div class="truncate text-[12px] text-[var(--om-text-secondary)]">{editingItem ? categoryNameFor(editingItem) || language.t('noCategory') : ''}</div>
      </div>
      {#if !catalogLocked}
      <button class="grid h-11 w-11 place-items-center rounded-[10px] text-[var(--om-danger)] hover:bg-[var(--om-danger-tint)]" onclick={openDeleteConfirm} aria-label={language.t('delete')} title={language.t('delete')}><span class="ms">delete</span></button>
      <span class="h-7 w-px bg-[var(--om-border)]" aria-hidden="true"></span>
      {/if}
      <button class="btn-outline hidden px-4 md:inline-flex" onclick={closeEditModal}>{language.t('cancel')}</button>
      <button class="btn-primary inline-flex items-center gap-1.5 px-4" disabled={savingEdit} onclick={saveProductEdit}>
        <span class="ms !text-[20px]">check</span>{savingEdit ? language.t('saving') : language.t('saveChanges')}
      </button>
    </div>

    <div class="min-h-0 flex-1 overflow-auto">
      {#if catalogLocked}
        <div class="mx-auto max-w-[1480px] px-3 pt-5 md:px-5"><CatalogNotice /></div>
      {/if}
      {#if error}
        <div role="alert" class="mx-auto mt-5 flex max-w-[1480px] items-center gap-2 rounded-[12px] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)] md:mx-5 2xl:mx-auto"><span class="ms">error</span>{error}</div>
      {/if}
      <div class="mx-auto grid max-w-[1480px] grid-cols-1 items-start gap-4 px-3 pb-10 pt-5 md:grid-cols-[minmax(280px,340px)_minmax(0,1fr)] md:px-5 xl:grid-cols-[minmax(300px,360px)_minmax(0,1fr)_320px]">
        <!-- Info -->
        <div class="flex min-w-0 flex-col gap-4 md:col-start-1 md:row-span-2 md:row-start-1 xl:row-span-1">
          <section class="card space-y-3 p-5">
<fieldset disabled={catalogLocked} class="m-0 min-w-0 space-y-3 border-0 p-0">
            <h2 class="text-[16px] font-bold">{language.t('productInfo')}</h2>
            <PhotoField bind:file={editImageFile} currentUrl={editingItem?.image_url ? mediaUrl(editingItem.image_url) : null} uploading={uploadingImage} onremove={removeItemImage} />
            <label class="block">
              <span class="mb-1 block text-[14px] font-semibold">{language.t('name')}</span>
              <input class="field" placeholder={language.t('productPlaceholder')} bind:value={editProductName} required />
            </label>
            <div>
              <span class="mb-1 block text-[14px] font-semibold">{language.t('category')}</span>
              <div class={CHIP_ROW}>
                <button type="button" class={chip(editCategoryId === '')} style="min-height: var(--om-tap)" aria-pressed={editCategoryId === ''} onclick={() => (editCategoryId = '')}>{language.t('noCategory')}</button>
                {#each categories as category (category.id)}
                  <button type="button" class={chip(editCategoryId === category.id)} style="min-height: var(--om-tap)" aria-pressed={editCategoryId === category.id} onclick={() => (editCategoryId = category.id)}>{category.name}</button>
                {/each}
              </div>
            </div>
            <label class="block">
              <span class="mb-1 block text-[14px] font-semibold">{language.t('baseSellPrice')}</span>
              <div class="field flex items-center gap-2"><span class="text-[14px] text-[var(--om-text-secondary)]">Rp</span><input class="min-w-0 flex-1 bg-transparent text-right outline-none" type="text" inputmode="numeric" placeholder="0" value={editPriceDisplay} oninput={(e) => { editPriceDisplay = onPriceInput(e); }} /></div>
              <span class="mt-1 block text-[12px] text-[var(--om-text-secondary)]">{language.t('baseSellPriceHint')}</span>
            </label>
            <label class="block">
              <span class="mb-1 block text-[14px] font-semibold">HPP (Rp)</span>
              <div class="field flex items-center gap-2"><span class="text-[14px] text-[var(--om-text-secondary)]">Rp</span><input class="min-w-0 flex-1 bg-transparent text-right outline-none" type="text" inputmode="numeric" placeholder="0" value={editCostDisplay} oninput={(e) => { editCostDisplay = onPriceInput(e); }} /></div>
              <span class="mt-1 block text-[12px] text-[var(--om-text-secondary)]">{language.t('hppManualHint')}</span>
            </label>
            <label class="block">
              <span class="mb-1 block text-[14px] font-semibold">{language.t('stock')}</span>
              <input class="field" type="number" min="0" step="1" placeholder="—" bind:value={editStock} />
            </label>
          </fieldset>
</section>

          {#if enabledChannels.length}
            <section class="card space-y-3 p-5">
<fieldset disabled={catalogLocked} class="m-0 min-w-0 space-y-3 border-0 p-0">
              <div>
                <h2 class="text-[16px] font-bold">{language.t('channelPrices')}</h2>
                <span class="text-[12px] text-[var(--om-text-secondary)]">{language.t('channelPricesHint')}</span>
              </div>
              {#each enabledChannels as c (c.channel)}
                {@const auto = autoChannelPrice(parsePrice(editPriceDisplay), c.markup_bp)}
                <div class="grid grid-cols-[1fr_9rem] items-center gap-3">
                  <div class="min-w-0">
                    <div class="text-[14px] font-semibold">{CHANNEL_NAMES[c.channel]}</div>
                    <div class="text-[12px] text-[var(--om-text-secondary)]">{language.t('channelPriceAuto')} {c.markup_bp ? `+${c.markup_bp / 100}%` : ''} · {formatRupiah(auto)}</div>
                    {#if editChannelPrices[c.channel]}
                      <button type="button" class="text-[12px] font-semibold text-[var(--om-brand)] underline" onclick={() => { editChannelPrices[c.channel] = ''; }}>{language.t('resetToAuto')}</button>
                    {/if}
                  </div>
                  <div class="field flex items-center gap-2"><span class="text-[14px] text-[var(--om-text-secondary)]">Rp</span><input class="min-w-0 flex-1 bg-transparent text-right outline-none" type="text" inputmode="numeric" placeholder={formatPriceDisplay(auto)} value={editChannelPrices[c.channel] ?? ''} oninput={(e) => { editChannelPrices[c.channel] = onPriceInput(e); }} /></div>
                </div>
              {/each}
            </fieldset>
</section>
          {/if}

          {#if editBranches.length}
            <section class="card space-y-3 p-5">
              <div>
                <h2 class="text-[16px] font-bold">{language.t('branchPrices')}</h2>
                <span class="text-[12px] text-[var(--om-text-secondary)]">{language.t('branchPricesHint')}</span>
              </div>
              {#each editBranches as b (b.store_id)}
                <div class="grid grid-cols-[1fr_9rem] items-center gap-3 {b.is_sold ? '' : 'opacity-60'}">
                  <div class="flex min-w-0 items-center gap-1">
                    <Toggle bind:checked={b.is_sold} label={`${language.t('branchPrices')}: ${b.store_name}`} />
                    <div class="min-w-0">
                      <div class="truncate text-[14px] font-semibold">{b.store_name}</div>
                      {#if b.is_parent && editBranches.length > 1}<div class="text-[12px] text-[var(--om-text-secondary)]">{language.t('parentStore')}</div>{/if}
                    </div>
                  </div>
                  <div class="field flex items-center gap-2"><span class="text-[14px] text-[var(--om-text-secondary)]">Rp</span><input class="min-w-0 flex-1 bg-transparent text-right outline-none disabled:opacity-50" type="text" inputmode="numeric" disabled={!b.is_sold} placeholder={editPriceDisplay} value={b.priceDisplay} oninput={(e) => { b.priceDisplay = onPriceInput(e); }} /></div>
                </div>
              {/each}
              {#if editBranches.length < 2}
                <p class="text-[12px] text-[var(--om-text-secondary)]">{language.t('branchOnlyOne')} <a class="font-semibold text-[var(--om-brand)] underline" href="/settings">{language.t('addBranch')}</a></p>
              {/if}
            </section>
          {/if}
        </div>

        <!-- Recipe -->
        <div class="min-w-0 space-y-4 md:col-start-2 md:row-start-2 xl:row-start-1">
          <div class={SEG_GROUP} role="tablist" aria-label={language.t('recipeIngredients')}>
            {#each [['recipe', language.t('recipe')], ['options', language.t('options')], ['addons', language.t('addons')]] as [key, label] (key)}
              <button type="button" role="tab" aria-selected={editTab === key} class="{seg(editTab === key)} flex-1 md:flex-none" style="min-height: var(--om-tap)" onclick={() => (editTab = key as typeof editTab)}>{label}</button>
            {/each}
          </div>

          {#if editTab === 'recipe'}
          <section class="card space-y-4 p-5">
            <div>
              <h2 class="text-[16px] font-bold">{language.t('recipeIngredients')}</h2>
              <span class="text-[12px] text-[var(--om-text-secondary)]">{language.t('invRecipeHint')}</span>
            </div>

            {#if !editIsParent}
              <div class="flex items-start gap-2 rounded-[10px] bg-[var(--om-brand-tint)] p-3 text-[14px]"><span class="ms !text-[20px] text-[var(--om-brand)]">link</span><span>{language.t('recipeFollowsParent')}</span></div>
            {/if}

            {#if recipeLines.length === 0}
              <div class="flex items-center gap-2 py-2 text-[14px] text-[var(--om-text-secondary)]"><span class="ms !text-[20px]">info</span>{language.t('recipeEmpty')}</div>
            {:else}
              <div class="hidden gap-2.5 border-b border-[var(--om-border)] pb-2 text-[12px] font-semibold text-[var(--om-text-secondary)] md:flex">
                <span class="flex-1">{language.t('recipeIngredient')}</span>
                <span class="w-[150px] shrink-0">{language.t('invRecipeQty')}</span>
                <span class="w-[110px] shrink-0 text-right">{language.t('recipeUnitCost')}</span>
                <span class="w-[100px] shrink-0 text-right">{language.t('recipeSubtotal')}</span>
                {#if editIsParent}<span class="w-11 shrink-0"></span>{/if}
              </div>
              {#each recipeLines as line, index (line.ingredient_id)}
                {@const q = parseFloat(line.quantity.replace(',', '.')) || 0}
                <div class="flex flex-wrap items-center gap-2.5 border-b border-[var(--om-border)] pb-3 last:border-0 md:flex-nowrap md:pb-2">
                  <div class="min-w-0 flex-1 basis-full text-[14px] font-semibold md:basis-auto">{line.name}</div>
                  {#if editIsParent}
                    <div class="field flex w-[150px] shrink-0 items-center gap-2"><input class="min-w-0 flex-1 bg-transparent text-right outline-none" inputmode="decimal" placeholder="0" aria-label={language.t('invRecipeQty')} bind:value={line.quantity} /><span class="text-[14px] text-[var(--om-text-secondary)]">{line.unit}</span></div>
                  {:else}
                    <div class="w-[150px] shrink-0 text-[14px] tabular-nums">{line.quantity} {line.unit}</div>
                  {/if}
                  <div class="w-[110px] shrink-0 text-right text-[14px] tabular-nums">{formatRupiah(line.cost_price)}</div>
                  <div class="w-[100px] shrink-0 text-right text-[14px] font-bold tabular-nums">{formatRupiah(Math.round(line.cost_price * q))}</div>
                  {#if editIsParent}
                    <button type="button" class="grid h-11 w-11 shrink-0 place-items-center rounded-[10px] text-[var(--om-text-secondary)] hover:bg-[var(--om-danger-tint)] hover:text-[var(--om-danger)]" aria-label={language.t('delete')} onclick={() => (recipeLines = recipeLines.filter((_, i) => i !== index))}><span class="ms !text-[20px]">delete</span></button>
                  {/if}
                </div>
              {/each}
            {/if}

            {#if editIsParent}
              <IngredientPicker placeholder={`+ ${language.t('invRecipeAdd')}`} emptyText={language.t('invRecipeNoIngredients')} exclude={recipeLines.map((l) => l.ingredient_id)} onPick={addRecipeLine} />
            {/if}
            <div class="flex items-center justify-end gap-2 text-[14px] tabular-nums text-[var(--om-ink-2)]">{language.t('recipeTotal')} <strong class="text-[16px] text-[var(--om-ink)]">{formatRupiah(Math.round(recipeCost))}</strong></div>

          </section>
          {:else if editTab === 'options'}
            <section class="card space-y-3 p-5">
<fieldset disabled={catalogLocked} class="m-0 min-w-0 space-y-3 border-0 p-0">
              <div>
                <h2 class="text-[16px] font-bold">{language.t('options')}</h2>
                <span class="text-[12px] text-[var(--om-text-secondary)]">{language.t('manageOptions')}</span>
              </div>
              {#each optionGroups as group, groupIndex}
                <div class="rounded-xl border border-[var(--border)] bg-[var(--cream)] p-3">
                  <div class="mb-2 flex items-center gap-1.5">
                    <input class="field min-w-0 flex-1 py-2 text-sm" placeholder={language.t('groupNamePlaceholder')} bind:value={group.name} />
                    <label class="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-2.5 py-2 text-xs font-bold text-[var(--espresso)] transition-colors hover:bg-[var(--cream)]">
                      <input type="checkbox" bind:checked={group.required} class="accent-[var(--espresso)]" />
                      {language.t('required')}
                    </label>
                    <button type="button" class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-red-200 bg-red-50 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600" title={language.t('removeGroup')} onclick={() => removeOptionGroup(groupIndex)}><span class="ms !text-[14px]" aria-hidden="true">delete</span></button>
                  </div>
                  <div class="flex flex-wrap items-center gap-1.5">
                    {#each group.choices as choice, choiceIndex (choice.name)}
                      <span class="inline-flex h-9 items-center overflow-hidden rounded-full border text-sm font-medium transition-colors {choice.is_default ? 'border-[var(--om-brand)] bg-[var(--om-brand-tint)] text-[var(--om-ink)]' : 'border-[var(--om-border)] bg-white text-[var(--om-ink-2)]'}">
                        <button type="button" class="flex h-full items-center gap-1 pl-3 pr-1.5" aria-pressed={choice.is_default} title={language.t('optionDefaultHint')} onclick={() => toggleOptionDefault(groupIndex, choiceIndex)}>
                          {#if choice.is_default}<span class="ms !text-[16px] text-[var(--om-brand)]">check_circle</span>{/if}{choice.name}
                        </button>
                        <button type="button" class="grid h-full w-8 place-items-center text-[var(--text-muted)] hover:text-red-500" title={language.t('removeChoice')} aria-label={language.t('removeChoice')} onclick={() => removeOptionChoice(groupIndex, choiceIndex)}><span class="ms !text-[14px]" aria-hidden="true">close</span></button>
                      </span>
                    {/each}
                    <input
                      class="field h-9 min-w-[10rem] flex-1 py-0 text-sm"
                      placeholder={language.t('optionTagPlaceholder')}
                      bind:value={group.draft}
                      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); commitOptionDraft(groupIndex); } else if (e.key === 'Backspace' && !group.draft && group.choices.length) { removeOptionChoice(groupIndex, group.choices.length - 1); } }}
                      onblur={() => commitOptionDraft(groupIndex)}
                    />
                  </div>
                  <p class="mt-1.5 text-[12px] text-[var(--om-text-secondary)]">{language.t('optionDefaultHint')}</p>
                </div>
              {/each}
              <button type="button" class="btn-outline px-3 py-2 text-sm" onclick={addOptionGroup}>+ {language.t('addOptionGroup')}</button>
            </fieldset>
</section>
          {:else}
            <section class="card space-y-3 p-5">
<fieldset disabled={catalogLocked} class="m-0 min-w-0 space-y-3 border-0 p-0">
              <div>
                <h2 class="text-[16px] font-bold">{language.t('addons')}</h2>
                <span class="text-[12px] text-[var(--om-text-secondary)]">{language.t('manageAddons')}</span>
              </div>
              {#each addonGroups as group, groupIndex}
                <div class="rounded-xl border border-[var(--border)] bg-[var(--cream)] p-3">
                  <div class="mb-2 flex items-end gap-1.5">
                    <div class="min-w-0 flex-1">
                      <span class="mb-0.5 block text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('name')}</span>
                      <input class="field w-full min-w-0 py-2 text-sm" placeholder="e.g. Toppings" bind:value={group.name} />
                    </div>
                    <div class="w-14 shrink-0">
                      <span class="mb-0.5 block text-center text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('min')}</span>
                      <input class="field py-2 text-center text-sm" type="number" min="0" placeholder="0" bind:value={group.min_select} />
                    </div>
                    <div class="w-14 shrink-0">
                      <span class="mb-0.5 block text-center text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('max')}</span>
                      <input class="field py-2 text-center text-sm" type="number" min="0" placeholder="∞" bind:value={group.max_select} />
                    </div>
                    <button type="button" class="mb-0.5 grid h-[2.375rem] w-8 shrink-0 place-items-center rounded-lg border border-red-200 bg-red-50 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600" title={language.t('removeGroup')} onclick={() => removeAddonGroup(groupIndex)}><span class="ms !text-[14px]" aria-hidden="true">delete</span></button>
                  </div>
                  <div class="mb-1 flex items-center gap-1.5 px-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">
                    <span class="flex-1">{language.t('name')}</span>
                    <span class="w-[6.5rem] shrink-0 text-right">{language.t('price')} (Rp)</span>
                    <span class="w-8 shrink-0"></span>
                  </div>
                  <div class="space-y-1">
                    {#each group.choices as choice, choiceIndex}
                      <div class="flex items-center gap-1.5">
                        <input class="field min-w-0 flex-1 py-2 text-sm" placeholder="e.g. Extra Shot" bind:value={choice.name} />
                        <div class="w-[6.5rem] shrink-0"><input class="field py-2 text-right text-sm" type="number" min="0" placeholder="0" bind:value={choice.extra_price} /></div>
                        <button type="button" class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--border)] text-[var(--text-muted)] transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-500" title={language.t('removeChoice')} onclick={() => removeAddonChoice(groupIndex, choiceIndex)}><span class="ms !text-[14px]" aria-hidden="true">close</span></button>
                      </div>
                    {/each}
                  </div>
                  <button type="button" class="mt-2 text-xs font-bold text-[var(--warm-brown)] transition-colors hover:text-[var(--espresso)]" onclick={() => addAddonChoice(groupIndex)}>+ {language.t('addChoice')}</button>
                </div>
              {/each}
              <button type="button" class="btn-outline px-3 py-2 text-sm" onclick={addAddonGroup}>+ {language.t('addAddonGroup')}</button>
            </fieldset>
</section>
          {/if}
        </div>

        <!-- HPP summary -->
        <div class="min-w-0 md:col-start-2 md:row-start-1 xl:col-start-3 xl:sticky xl:top-5">
          <section class="card space-y-3 p-5" aria-live="polite">
            <div>
              <h2 class="text-[16px] font-bold">{language.t('hppPerServing')}</h2>
              <div class="text-[32px] font-bold tabular-nums">{formatRupiah(editHpp)}</div>
            </div>
            <div class="h-px bg-[var(--om-border)]"></div>
            <div class="flex justify-between gap-2.5 text-[14px]"><span class="text-[var(--om-ink-2)]">{language.t('sellPrice')}</span><strong class="tabular-nums">{formatRupiah(parsePrice(editPriceDisplay))}</strong></div>
            <div class="flex items-center justify-between gap-2.5">
              <span class="font-semibold">{language.t('margin')}</span>
              <div class="text-right"><span class="text-[24px] font-bold tabular-nums">{editMargin === null ? '—' : `${editMargin}%`}</span>{#if editMargin !== null}<div class="text-[12px] text-[var(--om-text-secondary)] tabular-nums">{formatRupiah(parsePrice(editPriceDisplay) - editHpp)}</div>{/if}</div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- ─── Delete confirm modal ─────────────────────────────────────── -->
{#if deleteConfirmItem}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pt-7 pb-5 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100">
          <span class="ms !text-[24px] text-red-600" aria-hidden="true">delete</span>
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
