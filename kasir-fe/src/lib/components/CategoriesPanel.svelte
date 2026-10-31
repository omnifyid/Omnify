<script lang="ts">
  import type { Snippet } from 'svelte';
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { toCategoryPayload } from '$lib/api/catalog';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Category, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import CatalogNotice from './CatalogNotice.svelte';
  import { session } from '$lib/stores/session.svelte';

  const categoryIcons = [
    { icon: '☕', label: 'Coffee' },
    { icon: '🍵', label: 'Tea' },
    { icon: '🥤', label: 'Cold drink' },
    { icon: '🧋', label: 'Boba' },
    { icon: '🍹', label: 'Juice' },
    { icon: '🥐', label: 'Bakery' },
    { icon: '🍞', label: 'Bread' },
    { icon: '🍰', label: 'Cake' },
    { icon: '🍩', label: 'Donut' },
    { icon: '🍪', label: 'Cookie' },
    { icon: '🍔', label: 'Burger' },
    { icon: '🍟', label: 'Fries' },
    { icon: '🍕', label: 'Pizza' },
    { icon: '🍝', label: 'Pasta' },
    { icon: '🍜', label: 'Noodles' },
    { icon: '🍛', label: 'Rice' },
    { icon: '🍗', label: 'Chicken' },
    { icon: '🥗', label: 'Salad' },
    { icon: '🍽️', label: 'Dining' },
    { icon: '⭐', label: 'Featured' }
  ];

  let { tabs }: { tabs?: Snippet } = $props();

  let categories = $state<Category[]>([]);
  let name = $state('');
  let icon = $state('');
  let editName = $state('');
  let editIcon = $state('');
  let loading = $state(false);
  let error = $state('');
  let loadedStoreId = $state<string | null>(null);
  let reordering = $state(false);
  let page = $state(1);
  const limit = 20;
  let total = $state(0);
  let totalPages = $derived(Math.max(1, Math.ceil(total / limit)));

  let modalOpen = $state(false);
  let modalEditing = $state<Category | null>(null);
  let deleteConfirmCategory = $state<Category | null>(null);
  let deleteLoading = $state(false);

  let sortedCategories = $derived([...categories].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name)));

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loadedStoreId = storeId;
    loading = true;
    error = '';
    try {
      const res = await api.get<PaginatedResponse<Category>>(`/stores/${storeId}/categories?limit=${limit}&offset=${(page - 1) * limit}`);
      categories = paginatedItems(res);
      total = res.total;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load categories';
    } finally {
      loading = false;
    }
  }

  function openCreate() {
    name = '';
    icon = '';
    modalEditing = null;
    modalOpen = true;
  }

  let locked = $derived(session.selectedStore?.is_parent === false);

  function openEdit(category: Category) {
    if (locked) return;
    editName = category.name;
    editIcon = category.icon ?? '';
    modalEditing = category;
    modalOpen = true;
  }

  function closeModal() {
    modalOpen = false;
    modalEditing = null;
    editName = '';
    editIcon = '';
  }

  async function createCategory() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    const sortOrder = Math.max(0, ...categories.map((category) => category.sort_order ?? 0)) + 10;
    await api.post(`/stores/${storeId}/categories`, toCategoryPayload({ name, icon, sortOrder }));
    closeModal();
    await load();
  }

  async function saveCategory(category: Category) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    await api.patch(`/stores/${storeId}/categories/${category.id}`, toCategoryPayload({ name: editName, icon: editIcon, sortOrder: category.sort_order }));
    closeModal();
    await load();
  }

  // Order shown while dragging; null when idle.
  let dragId = $state<string | null>(null);
  let dragOrder = $state<string[] | null>(null);
  let displayCategories = $derived(
    dragOrder
      ? dragOrder.map((id) => categories.find((c) => c.id === id)).filter((c): c is Category => !!c)
      : sortedCategories
  );

  async function applyOrder(ids: string[]) {
    const storeId = session.selectedStore?.id;
    if (!storeId || reordering) return;
    const current = sortedCategories.map((c) => c.id);
    if (ids.join() === current.join()) return;

    const reordered = ids
      .map((id) => categories.find((c) => c.id === id))
      .filter((c): c is Category => !!c)
      .map((item, index) => ({ ...item, sort_order: (index + 1) * 10 }));

    reordering = true;
    error = '';
    categories = reordered;
    try {
      await Promise.all(
        reordered
          .map((item) => api.patch(`/stores/${storeId}/categories/${item.id}`, { sort_order: item.sort_order }))
      );
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to reorder categories';
      await load();
    } finally {
      reordering = false;
    }
  }

  function startDrag(e: PointerEvent, category: Category) {
    if (reordering || e.button > 0) return;
    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragId = category.id;
    dragOrder = sortedCategories.map((c) => c.id);
  }

  function moveDrag(e: PointerEvent) {
    if (!dragId || !dragOrder) return;
    const over = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>('[data-cat-id]');
    const overId = over?.dataset.catId;
    if (!overId || overId === dragId) return;
    const next = dragOrder.filter((id) => id !== dragId);
    const target = dragOrder.indexOf(overId);
    next.splice(target, 0, dragId);
    dragOrder = next;
  }

  async function endDrag() {
    const ids = dragOrder;
    dragId = null;
    dragOrder = null;
    if (ids) await applyOrder(ids);
  }

  function keyMove(e: KeyboardEvent, category: Category) {
    if (locked) return;
    const delta = e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowDown' || e.key === 'ArrowRight' ? 1 : 0;
    if (!delta) return;
    e.preventDefault();
    e.stopPropagation();
    const ids = sortedCategories.map((c) => c.id);
    const from = ids.indexOf(category.id);
    const to = from + delta;
    if (to < 0 || to >= ids.length) return;
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    void applyOrder(ids).then(() => document.querySelector<HTMLElement>(`[data-cat-id="${category.id}"] [data-handle]`)?.focus());
  }

  async function removeCategory(category: Category) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    await api.delete(`/stores/${storeId}/categories/${category.id}`);
    await load();
  }

  function openDeleteConfirm() {
    const cat = modalEditing;
    if (!cat) return;
    closeModal();
    deleteConfirmCategory = cat;
  }

  function closeDeleteConfirm() {
    deleteConfirmCategory = null;
  }

  async function confirmDeleteCategory() {
    if (!deleteConfirmCategory) return;
    deleteLoading = true;
    try {
      await removeCategory(deleteConfirmCategory);
      deleteConfirmCategory = null;
    } finally {
      deleteLoading = false;
    }
  }

  async function goToPage(newPage: number) {
    page = newPage;
    await load();
  }

  $effect(() => {
    const storeId = session.selectedStore?.id;
    if (storeId && storeId !== loadedStoreId) { page = 1; untrack(() => void load()); }
  });
</script>

<div class="mb-4 flex flex-wrap items-center gap-2.5">
  {@render tabs?.()}
  <div class="flex-1"></div>
  {#if !locked}
  <button class="btn-primary flex items-center gap-1.5 !rounded-[10px]" onclick={openCreate}>
    <span class="ms !text-[20px] text-[var(--om-brand-on-dark)]">add</span>{language.t('add')}
  </button>
  {/if}
</div>

<CatalogNotice />

{#if error}
  <div role="alert" class="mb-4 flex items-center gap-2 rounded-[12px] bg-[var(--om-danger-tint)] p-3 text-[14px] font-semibold text-[var(--om-danger)]"><span class="ms">error</span>{error}</div>
{/if}

<div class="grid gap-3" style="grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); grid-auto-rows: max-content">
  {#each displayCategories as category, index (category.id)}
    <div
      data-cat-id={category.id}
      class="group flex flex-col gap-2.5 rounded-[14px] border bg-white p-3 transition duration-150 {dragId === category.id ? 'border-[var(--om-brand)] opacity-70 shadow-[var(--om-sh-popover)]' : 'border-[var(--om-border)] hover:-translate-y-0.5 hover:border-[var(--om-brand)] hover:shadow-[var(--om-sh-popover)]'}"
    >
      <div class="flex items-center gap-2.5">
        <div class="relative shrink-0">
          <div class="grid h-12 w-12 place-items-center rounded-xl bg-[var(--om-ink)] text-[24px]">{category.icon ?? '🍽️'}</div>
          <span class="absolute -left-1.5 -top-1.5 grid min-w-[22px] place-items-center rounded-full border-2 border-white bg-[var(--om-brand)] px-1 text-[11px] font-bold leading-[18px] tabular-nums text-white">{(page - 1) * limit + index + 1}</span>
        </div>
        <span class="min-w-0 flex-1 truncate text-[18px] font-semibold">{category.name}</span>
        <div class="flex shrink-0 flex-col items-end leading-none">
          <span class="text-[40px] font-bold tabular-nums tracking-tight">{category.item_count ?? 0}</span>
          <span class="mt-0.5 text-[12px] text-[var(--om-text-secondary)]">{language.t('products').toLowerCase()}</span>
        </div>
      </div>

      <div class="grid grid-cols-[1fr_1fr_36px] gap-1.5">
        <button
          class="flex h-9 items-center justify-center gap-1.5 rounded-[9px] border border-[var(--om-border)] bg-white text-[14px] font-semibold text-[var(--om-ink)] transition-colors hover:border-[var(--om-brand)] hover:bg-[var(--om-brand-tint)] disabled:opacity-40 disabled:hover:border-[var(--om-border)] disabled:hover:bg-white"
          disabled={locked}
          onclick={() => openEdit(category)}
          aria-label={`${language.t('editCategory')}: ${category.name}`}
        ><span class="ms !text-[18px]">edit</span>{language.t('editShort')}</button>
        <button
          class="flex h-9 items-center justify-center gap-1.5 rounded-[9px] border border-[var(--om-border)] bg-white text-[14px] font-semibold text-[var(--om-ink)] transition-colors hover:border-[var(--om-brand)] hover:bg-[var(--om-brand-tint)]"
          onclick={() => goto(`/products?cat=${category.id}`)}
          aria-label={`${language.t('products')}: ${category.name}`}
        ><span class="ms !text-[18px]">format_list_bulleted</span>{language.t('products')}</button>
        <button
          type="button"
          data-handle
          class="grid h-9 w-9 touch-none place-items-center rounded-[9px] text-[var(--om-text-secondary)] hover:bg-[var(--om-fill-hover)] {dragId === category.id ? 'cursor-grabbing' : 'cursor-grab'}"
          aria-label={`${language.t('reorder')}: ${category.name}`}
          disabled={reordering || locked}
          onpointerdown={(e) => startDrag(e, category)}
          onpointermove={moveDrag}
          onpointerup={endDrag}
          onpointercancel={endDrag}
          onlostpointercapture={endDrag}
          onkeydown={(e) => keyMove(e, category)}
        ><span class="ms !text-[20px]">drag_indicator</span></button>
      </div>
    </div>
  {:else}
    <div class="col-span-full p-5 text-[16px] text-[var(--om-text-secondary)]">{loading ? language.t('loading') : language.t('noCategoriesFound')}</div>
  {/each}
</div>

{#if totalPages > 1}
  <div class="mt-4 flex items-center justify-between gap-3 text-sm">
    <span class="text-[var(--text-muted)]">{language.t('page')} {page} {language.t('of')} {totalPages}</span>
    <div class="flex gap-2">
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>{language.t('previous')}</button>
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>{language.t('next')}</button>
    </div>
  </div>
{/if}

<!-- ─── Create / Edit modal ───────────────────────────────────────── -->
{#if modalOpen}
  <div class="fixed inset-0 z-50 flex justify-end bg-[var(--om-scrim)]"
       role="presentation"
       onclick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
    <section class="flex h-full w-full max-w-[440px] flex-col overflow-hidden bg-white shadow-[var(--om-sh-drawer)]" style="animation: omUp .2s ease" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="flex-1 text-[16px] font-semibold">{modalEditing ? language.t('editCategory') : language.t('newCategory')}</h2>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeModal} aria-label={language.t('close')}><span class="ms !text-[16px]" aria-hidden="true">close</span></button>
      </div>

      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        <div>
          <p class="mb-2 text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">Icon</p>
          <div class="grid grid-cols-5 gap-2">
            {#each categoryIcons as option}
              <button type="button"
                      class="rounded-[10px] border p-2 text-center transition {(modalEditing ? editIcon : icon) === option.icon ? 'border-[var(--om-brand)] bg-[var(--om-brand-tint)]' : 'border-[var(--border)] bg-[var(--white)] hover:border-[var(--warm-brown)] hover:bg-[var(--cream)]'}"
                      onclick={() => { if (modalEditing) editIcon = option.icon; else icon = option.icon; }}>
                <div class="text-2xl">{option.icon}</div>
                <div class="mt-0.5 truncate text-[12px] text-[var(--om-text-secondary)]">{option.label}</div>
              </button>
            {/each}
          </div>
        </div>
        <label class="block">
          <span class="mb-0.5 block text-[12px] font-medium normal-case tracking-normal text-[var(--om-ink-2)]">{language.t('name')}</span>
          {#if modalEditing}
            <input class="field" placeholder={language.t('categoryName')} bind:value={editName} required />
          {:else}
            <input class="field" placeholder={language.t('categoryName')} bind:value={name} required />
          {/if}
        </label>
      </div>

      <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
        {#if modalEditing}
          <button
            class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100"
            onclick={openDeleteConfirm}
          >
            <span class="ms !text-[16px]" aria-hidden="true">delete</span>
            {language.t('delete')}
          </button>
        {/if}
        <div class="flex flex-1 items-center justify-end gap-3">
          <button class="btn-primary" onclick={() => modalEditing ? saveCategory(modalEditing) : createCategory()}>
            {modalEditing ? language.t('saveChanges') : language.t('addCategory')}
          </button>
        </div>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Delete confirm modal ─────────────────────────────────────── -->
{#if deleteConfirmCategory}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100">
          <span class="ms !text-[24px] text-red-600" aria-hidden="true">delete</span>
        </div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('deleteCategory')}</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]">
          {language.t('deleteConfirmPrefix')}
          <strong class="text-[var(--espresso)]">{deleteConfirmCategory.name}</strong>?
          {language.t('deleteConfirmSuffix')}
        </p>
      </div>
      <div class="flex gap-3 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={closeDeleteConfirm}>{language.t('cancel')}</button>
        <button
          class="flex-1 rounded-full bg-red-600 px-4 py-2.5 font-bold text-white transition hover:bg-red-700 disabled:opacity-50"
          disabled={deleteLoading}
          onclick={confirmDeleteCategory}
        >{deleteLoading ? language.t('deleting') : language.t('delete')}</button>
      </div>
    </section>
  </div>
{/if}
