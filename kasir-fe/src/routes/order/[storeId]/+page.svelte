<script lang="ts">
  import CupcakeIcon from '$lib/components/CupcakeIcon.svelte';
  import { page } from '$app/stores';
  import { api, mediaUrl } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { getItemPrice } from '$lib/utils/catalog';
  import { formatRupiah } from '$lib/utils/format';

  // Types matching backend ItemRead schema
  type MenuOptionChoice = { id: string; label: string; is_default: boolean; extra_price?: number; };
  type MenuOptionGroup  = { id: string; name: string; is_required: boolean; choices: MenuOptionChoice[]; };
  type MenuAddonChoice  = { id: string; label: string; extra_price: number; is_available: boolean; is_default?: boolean; };
  type MenuAddonGroup   = { id: string; name: string; is_required: boolean; min_select: number; max_select: number | null; choices: MenuAddonChoice[]; };
  type MenuItem = {
    id: string; name: string; description: string | null;
    base_price: number; price?: number; image_url: string | null; icon: string | null;
    stock: number | null; category_id: string | null;
    option_groups: MenuOptionGroup[]; addon_groups: MenuAddonGroup[];
  };
  type MenuCategory = { id: string; name: string; icon?: string | null; };
  type MenuData = {
    store: { id: string; name: string; description: string | null; logo_url: string | null; selforder_is_open: boolean; service_bp?: number; pb1_bp?: number; };
    categories: MenuCategory[];
    items: MenuItem[];
  };

  type CartEntry = {
    item: MenuItem;
    qty: number;
    selectedOptionChoiceIds: string[];
    selectedAddonChoiceIds: string[];
  };

  const storeId    = $derived($page.params.storeId);
  const tableNumber = $derived($page.url.searchParams.get('table') ?? '');

  let menu        = $state<MenuData | null>(null);
  let loading     = $state(true);
  let error       = $state('');
  let activeCategory = $state('all');
  let cart        = $state<Map<string, CartEntry>>(new Map());
  let cartOpen    = $state(false);
  let notes       = $state('');
  let submitting  = $state(false);
  let orderPlaced = $state<{ order_number: string } | null>(null);

  // ── Customization sheet ──────────────────────────────────
  let customizeItem    = $state<MenuItem | null>(null);
  let customizeQty     = $state(1);
  let customizeOptions = $state<Record<string, string>>({}); // groupId → choiceId
  let customizeAddons  = $state<Set<string>>(new Set());     // choiceIds

  // ── Derived ──────────────────────────────────────────────
  let cartEntries = $derived([...cart.values()].filter((v) => v.qty > 0));
  let cartCount   = $derived(cartEntries.reduce((s, v) => s + v.qty, 0));
  let cartTotal   = $derived(cartEntries.reduce((s, e) => s + entryUnitPrice(e) * e.qty, 0));
  // Totals come from the server preview (automatic discounts, service on dine-in, PB1); the same rule
  // computed locally covers the moment before the first response.
  type Preview = { subtotal: number; discount_amount: number; service_amount: number; pb1_amount: number; total_amount: number };
  let preview = $state<Preview | null>(null);
  const feeRound = (amount: number, bp: number) => Math.floor((amount * bp + 5000) / 10000);
  let localService = $derived(tableNumber ? feeRound(cartTotal, menu?.store.service_bp ?? 0) : 0);
  let localPb1     = $derived(feeRound(cartTotal + localService, menu?.store.pb1_bp ?? 0));
  let discountTotal = $derived(preview ? cartTotal - preview.subtotal + preview.discount_amount : 0);
  let serviceFee  = $derived(preview ? preview.service_amount : localService);
  let pb1Fee      = $derived(preview ? preview.pb1_amount : localPb1);
  let grandTotal  = $derived(preview ? preview.total_amount : cartTotal + localService + localPb1);
  let previewTimer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    const items = cartEntries.map(({ item, qty, selectedOptionChoiceIds, selectedAddonChoiceIds }) => ({
      item_id: item.id,
      quantity: qty,
      selected_option_choice_ids: selectedOptionChoiceIds,
      selected_addon_choice_ids: selectedAddonChoiceIds,
    }));
    const dine = tableNumber ? 'DINE_IN' : null;
    clearTimeout(previewTimer);
    if (!items.length || !storeId) {
      preview = null;
      return;
    }
    previewTimer = setTimeout(async () => {
      try {
        preview = await api.post<Preview>(`/public/stores/${storeId}/orders/preview`, { items, order_type: dine });
      } catch {
        preview = null;
      }
    }, 250);
    return () => clearTimeout(previewTimer);
  });

  let isAcceptingOrders = $derived(menu?.store.selforder_is_open ?? true);

  let filteredItems = $derived(
    activeCategory === 'all'
      ? (menu?.items ?? [])
      : (menu?.items ?? []).filter((i) => i.category_id === activeCategory)
  );

  let customizeAddonExtra = $derived(
    [...customizeAddons].reduce((sum, cid) => {
      for (const g of (customizeItem?.addon_groups ?? [])) {
        const c = g.choices.find((ch) => ch.id === cid);
        if (c) return sum + c.extra_price;
      }
      return sum;
    }, 0) +
      Object.values(customizeOptions).reduce((sum, cid) => {
        for (const g of (customizeItem?.option_groups ?? [])) {
          const c = g.choices.find((ch) => ch.id === cid);
          if (c) return sum + (c.extra_price ?? 0);
        }
        return sum;
      }, 0)
  );
  let customizeUnitPrice = $derived(customizeItem ? getItemPrice(customizeItem) + customizeAddonExtra : 0);
  let customizeTotal     = $derived(customizeUnitPrice * customizeQty);
  let customizeCanAdd    = $derived(
    (customizeItem?.option_groups ?? []).every((g) => !g.is_required || !!customizeOptions[g.id]) &&
      (customizeItem?.addon_groups ?? []).every((g) => !(g.is_required || g.min_select > 0) || g.choices.some((c) => customizeAddons.has(c.id)))
  );

  // ── Helpers ──────────────────────────────────────────────
  function entryUnitPrice(e: CartEntry): number {
    const optionExtra = e.selectedOptionChoiceIds.reduce((sum, cid) => {
      for (const g of e.item.option_groups) {
        const c = g.choices.find((ch) => ch.id === cid);
        if (c) return sum + (c.extra_price ?? 0);
      }
      return sum;
    }, 0);
    return e.selectedAddonChoiceIds.reduce((sum, cid) => {
      for (const g of e.item.addon_groups) {
        const c = g.choices.find((ch) => ch.id === cid);
        if (c) return sum + c.extra_price;
      }
      return sum;
    }, getItemPrice(e.item) + optionExtra);
  }

  function entryModifierLabel(e: CartEntry): string {
    const parts: string[] = [];
    for (const g of e.item.option_groups) {
      const c = g.choices.find((ch) => e.selectedOptionChoiceIds.includes(ch.id));
      if (c) parts.push(c.label);
    }
    for (const g of e.item.addon_groups) {
      for (const c of g.choices) {
        if (e.selectedAddonChoiceIds.includes(c.id)) parts.push(c.label);
      }
    }
    return parts.join(', ');
  }

  function hasModifiers(item: MenuItem) {
    return item.option_groups.length > 0 || item.addon_groups.length > 0;
  }

  // ── Menu load ────────────────────────────────────────────
  $effect(() => { if (storeId) void loadMenu(); });

  async function loadMenu() {
    loading = true; error = '';
    try {
      menu = await api.get<MenuData>(`/public/stores/${storeId}/menu`);
    } catch (e) {
      error = e instanceof Error ? e.message : language.t('menuUnavailable');
    } finally {
      loading = false;
    }
  }

  // ── Cart actions ─────────────────────────────────────────
  function openCustomize(item: MenuItem) {
    cartOpen = false;
    customizeItem = item;
    const existing = cart.get(item.id);
    if (existing) {
      customizeQty = existing.qty;
      const opts: Record<string, string> = {};
      for (const g of item.option_groups) {
        const sel = existing.selectedOptionChoiceIds.find((id) => g.choices.some((c) => c.id === id));
        if (sel) opts[g.id] = sel;
      }
      customizeOptions = opts;
      customizeAddons  = new Set(existing.selectedAddonChoiceIds);
    } else {
      customizeQty = 1;
      const opts: Record<string, string> = {};
      for (const g of item.option_groups) {
        const def = g.choices.find((c) => c.is_default) ?? (g.is_required ? g.choices[0] : undefined);
        if (def) opts[g.id] = def.id;
      }
      customizeOptions = opts;
      customizeAddons  = new Set(item.addon_groups.flatMap((g) => g.choices.filter((c) => c.is_default && c.is_available).map((c) => c.id)));
    }
  }

  function closeCustomize() { customizeItem = null; }

  function confirmCustomize() {
    if (!customizeItem || !customizeCanAdd || customizeQty < 1) return;
    cart = new Map(cart).set(customizeItem.id, {
      item: customizeItem,
      qty: customizeQty,
      selectedOptionChoiceIds: Object.values(customizeOptions),
      selectedAddonChoiceIds: [...customizeAddons],
    });
    closeCustomize();
  }

  function addDirect(item: MenuItem) {
    const e = cart.get(item.id);
    cart = new Map(cart).set(item.id, {
      item,
      qty: (e?.qty ?? 0) + 1,
      selectedOptionChoiceIds: e?.selectedOptionChoiceIds ?? [],
      selectedAddonChoiceIds:  e?.selectedAddonChoiceIds  ?? [],
    });
  }

  function setQty(itemId: string, delta: number) {
    const updated = new Map(cart);
    const e = updated.get(itemId);
    if (!e) return;
    const newQty = e.qty + delta;
    if (newQty <= 0) updated.delete(itemId);
    else updated.set(itemId, { ...e, qty: newQty });
    cart = updated;
  }

  function toggleAddon(choiceId: string) {
    const s = new Set(customizeAddons);
    if (s.has(choiceId)) s.delete(choiceId); else s.add(choiceId);
    customizeAddons = s;
  }

  // ── Order submit ─────────────────────────────────────────
  async function submitOrder() {
    if (cartEntries.length === 0 || submitting) return;
    submitting = true; error = '';
    try {
      const result = await api.post<{ order_number: string }>(`/public/stores/${storeId}/orders`, {
        items: cartEntries.map(({ item, qty, selectedOptionChoiceIds, selectedAddonChoiceIds }) => ({
          item_id: item.id,
          quantity: qty,
          selected_option_choice_ids: selectedOptionChoiceIds,
          selected_addon_choice_ids:  selectedAddonChoiceIds,
        })),
        table_number: tableNumber || null,
        notes: notes || null,
      });
      orderPlaced = result;
      cart = new Map(); cartOpen = false; notes = '';
    } catch (e) {
      error = e instanceof Error ? e.message : language.t('orderSubmitFailed');
    } finally { submitting = false; }
  }

  function resetOrder() {
    orderPlaced = null; cart = new Map(); notes = ''; error = '';
  }
</script>

<svelte:head>
  <title>{menu?.store.name ?? language.t('menu')}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
</svelte:head>

<div class="flex min-h-dvh flex-col bg-[var(--background)]">

  <!-- Loading -->
  {#if loading}
    <div class="grid flex-1 place-items-center">
      <div class="display-font text-xl font-bold text-[var(--espresso)] opacity-60">{language.t('loading')}</div>
    </div>

  <!-- Error (no menu) -->
  {:else if error && !menu}
    <div class="grid flex-1 place-items-center p-6 text-center">
      <div>
        <div class="mb-2 text-4xl">😕</div>
        <div class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('menuUnavailable')}</div>
        <p class="mt-1 text-sm text-[var(--text-muted)]">{error}</p>
      </div>
    </div>

  <!-- Success screen -->
  {:else if orderPlaced}
    <div class="grid flex-1 place-items-center p-6 text-center">
      <div>
        <div class="mb-4 text-6xl">✅</div>
        <h1 class="display-font text-3xl font-bold text-[var(--espresso)]">{language.t('orderReceived')}</h1>
        {#if tableNumber}
          <p class="mt-2 text-lg font-bold text-[var(--warm-brown)]">{language.t('table')} {tableNumber}</p>
        {/if}
        <p class="mt-1 text-sm text-[var(--text-muted)]">#{orderPlaced.order_number}</p>
        <p class="mt-4 text-sm text-[var(--text-muted)]">{language.t('waitingOrderProcessing')}</p>
        <button class="btn-primary mt-8 px-8 py-3" onclick={resetOrder}>{language.t('orderAgain')}</button>
      </div>
    </div>

  <!-- Main menu -->
  {:else if menu}
    <!-- Header -->
    <header class="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--white)] px-4 py-3">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <h1 class="display-font truncate text-xl font-bold text-[var(--espresso)]">{menu.store.name}</h1>
          {#if tableNumber}
            <p class="text-xs font-bold text-[var(--warm-brown)]">{language.t('table')} {tableNumber}</p>
          {/if}
        </div>
        {#if cartCount > 0}
          <button
            class="relative flex shrink-0 items-center gap-2 rounded-full bg-[var(--espresso)] px-4 py-2 text-sm font-bold text-white transition active:scale-95"
            onclick={() => { cartOpen = true; }}
          >
            <span class="ms !text-[16px]" aria-hidden="true">shopping_cart</span>
            <span>{cartCount}</span>
          </button>
        {/if}
      </div>
    </header>

    <!-- Category tabs — hidden when store is closed -->
    {#if isAcceptingOrders}
    <div class="sticky top-[57px] z-10 bg-[var(--white)] shadow-sm">
      <div class="flex gap-2 overflow-x-auto px-4 py-2.5 scrollbar-none">
        <button
          class="shrink-0 rounded-full px-4 py-1.5 text-sm font-bold transition {activeCategory === 'all' ? 'bg-[var(--espresso)] text-white' : 'bg-[var(--cream)] text-[var(--text-muted)]'}"
          onclick={() => { activeCategory = 'all'; }}
        >{language.t('all')}</button>
        {#each menu.categories as cat}
          <button
            class="shrink-0 rounded-full px-4 py-1.5 text-sm font-bold transition {activeCategory === cat.id ? 'bg-[var(--espresso)] text-white' : 'bg-[var(--cream)] text-[var(--text-muted)]'}"
            onclick={() => { activeCategory = cat.id; }}
          >{cat.icon ?? ''} {cat.name}</button>
        {/each}
      </div>
    </div>
    {/if}

    <!-- Error banner -->
    {#if error}
      <div class="mx-4 mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
    {/if}

    {#if !isAcceptingOrders}
      <!-- Closed full-page state — no product list -->
      <div class="grid flex-1 place-items-center p-6 text-center">
        <div>
          <div class="mb-4 grid h-20 w-20 place-items-center rounded-full bg-amber-100 mx-auto">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>
          <h2 class="display-font text-2xl font-bold text-[var(--espresso)]">{language.t('selfOrderPaused')}</h2>
          <p class="mt-2 text-sm text-[var(--text-muted)]">{language.t('selfOrderCustomersCannotOrder')}</p>
        </div>
      </div>
    {:else}
    <!-- Item grid -->
    <div class="grid grid-cols-2 gap-3 p-4 pb-32 sm:grid-cols-3">
      {#each filteredItems as item}
        {@const qty = cart.get(item.id)?.qty ?? 0}
        {@const oos = item.stock === 0}
        {@const withMod = hasModifiers(item)}
        <div
          class="group relative flex flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--white)] text-left transition {oos ? 'opacity-50' : 'cursor-pointer active:scale-95'}"
          role="button"
          tabindex={oos ? -1 : 0}
          aria-label={`${item.name}${withMod ? ', options' : ''}`}
          onclick={() => {
            if (oos) return;
            if (withMod) openCustomize(item);
            else addDirect(item);
          }}
          onkeydown={(e) => {
            if (oos) return;
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              if (withMod) openCustomize(item); else addDirect(item);
            }
          }}
        >
          <!-- Thumbnail -->
          <div class="relative h-36 w-full overflow-hidden bg-gradient-to-br from-[var(--light-brown)] to-[#d4b896]">
            {#if item.image_url}
              <img src={mediaUrl(item.image_url)} alt={item.name} class="h-full w-full object-cover" />
            {:else}
              <div class="grid h-full w-full place-items-center bg-[var(--white)] text-[var(--text-muted)] opacity-60"><CupcakeIcon size={72} /></div>
            {/if}
            {#if oos}
              <div class="absolute inset-0 grid place-items-center bg-black/40">
                <span class="rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-[var(--espresso)]">{language.t('stockOut')}</span>
              </div>
            {:else if qty > 0}
              <span class="absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-full bg-[var(--espresso)] text-xs font-bold text-white">{qty}</span>
            {/if}
          </div>
          <!-- Info -->
          <div class="flex flex-1 flex-col p-3">
            <p class="line-clamp-2 text-sm font-bold leading-tight text-[var(--espresso)]">{item.name}</p>
            <p class="mt-1 text-sm font-bold text-[var(--warm-brown)]">{formatRupiah(getItemPrice(item))}</p>
            {#if withMod}
              <!-- Items with modifiers show a "pilih opsi" hint and no inline +/- -->
              <p class="mt-auto pt-2 text-xs text-[var(--text-muted)]">{language.t('chooseOptions')} -></p>
            {:else if qty > 0}
              <div class="mt-2 flex items-center justify-between">
                <button
                  class="grid h-7 w-7 place-items-center rounded-full bg-[var(--cream)] text-[var(--espresso)] transition hover:bg-[var(--light-brown)]"
                  onclick={(e) => { e.stopPropagation(); setQty(item.id, -1); }}
                ><span class="ms !text-[14px]" aria-hidden="true">remove</span></button>
                <span class="text-sm font-bold text-[var(--espresso)]">{qty}</span>
                <button
                  class="grid h-7 w-7 place-items-center rounded-full bg-[var(--espresso)] text-white"
                  onclick={(e) => { e.stopPropagation(); setQty(item.id, +1); }}
                ><span class="ms !text-[14px]" aria-hidden="true">add</span></button>
              </div>
            {:else}
              <div class="mt-2 flex justify-end">
                <span class="grid h-7 w-7 place-items-center rounded-full bg-[var(--cream)] text-[var(--espresso)]">
                  <span class="ms !text-[14px]" aria-hidden="true">add</span>
                </span>
              </div>
            {/if}
          </div>
        </div>
      {:else}
        <div class="col-span-2 py-12 text-center text-sm text-[var(--text-muted)]">{language.t('noItemsFound')}</div>
      {/each}
    </div>

    {/if}

    <!-- Sticky cart bar -->
    {#if cartCount > 0 && !cartOpen && isAcceptingOrders}
      <div class="fixed inset-x-0 bottom-0 z-30 p-4">
        <button
          class="flex w-full items-center justify-between rounded-2xl bg-[var(--espresso)] px-5 py-4 text-white shadow-lg transition active:scale-95"
          onclick={() => { cartOpen = true; }}
        >
          <span class="grid h-7 w-7 place-items-center rounded-full bg-white/20 text-sm font-bold">{cartCount}</span>
          <span class="font-bold">{language.t('viewOrder')}</span>
          <span class="font-bold">{formatRupiah(grandTotal)}</span>
        </button>
      </div>
    {/if}
  {/if}
</div>

<!-- ── Cart bottom sheet ─────────────────────────────── -->
{#if cartOpen}
  <div
    class="fixed inset-0 z-50 flex items-end bg-[var(--om-scrim)]"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) cartOpen = false; }}
  >
    <section class="flex max-h-[90dvh] w-full flex-col rounded-t-3xl bg-[var(--white)]" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] px-5 py-4">
        <h2 class="display-font flex-1 text-xl font-bold text-[var(--espresso)]">{language.t('order')}</h2>
        {#if tableNumber}
          <span class="rounded-full bg-[var(--cream)] px-3 py-1 text-xs font-bold text-[var(--warm-brown)]">{language.t('table')} {tableNumber}</span>
        {/if}
        <button class="grid h-9 w-9 place-items-center rounded-full bg-[var(--cream)]" onclick={() => { cartOpen = false; }}>
          <span class="ms !text-[16px] text-[var(--espresso)]" aria-hidden="true">close</span>
        </button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-5 py-3">
        {#each cartEntries as entry}
          {@const modLabel = entryModifierLabel(entry)}
          {@const unitPrice = entryUnitPrice(entry)}
          <div class="flex items-start gap-3 border-b border-[var(--border)] py-3 last:border-0">
            <!-- Thumbnail -->
            <div class="h-12 w-12 shrink-0 overflow-hidden rounded-xl bg-[var(--light-brown)]">
              {#if entry.item.image_url}
                <img src={mediaUrl(entry.item.image_url)} alt={entry.item.name} class="h-full w-full object-cover" />
              {:else}
                <div class="grid h-full w-full place-items-center bg-[var(--white)] text-[var(--text-muted)] opacity-60"><CupcakeIcon size={28} /></div>
              {/if}
            </div>
            <!-- Name + modifiers + price -->
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-bold text-[var(--espresso)]">{entry.item.name}</p>
              {#if modLabel}
                <p class="mt-0.5 truncate text-xs text-[var(--text-muted)]">{modLabel}</p>
              {/if}
              <p class="mt-0.5 text-xs text-[var(--warm-brown)]">{formatRupiah(unitPrice)} / {language.t('item')}</p>
            </div>
            <!-- Qty controls -->
            <div class="flex shrink-0 items-center gap-2">
              <button
                class="grid h-8 w-8 place-items-center rounded-full bg-[var(--cream)] transition hover:bg-[var(--light-brown)]"
                onclick={() => setQty(entry.item.id, -1)}
              ><span class="ms !text-[14px] text-[var(--espresso)]" aria-hidden="true">remove</span></button>
              <span class="w-5 text-center text-sm font-bold text-[var(--espresso)]">{entry.qty}</span>
              <button
                class="grid h-8 w-8 place-items-center rounded-full bg-[var(--espresso)]"
                onclick={() => setQty(entry.item.id, +1)}
              ><span class="ms !text-[14px] text-white" aria-hidden="true">add</span></button>
            </div>
            <p class="w-20 shrink-0 text-right text-sm font-bold text-[var(--espresso)]">{formatRupiah(unitPrice * entry.qty)}</p>
          </div>
        {/each}

        <!-- Notes -->
        <div class="mt-3">
          <label class="block">
            <span class="mb-1 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
              {language.t('notes')}
            </span>
            <textarea
              class="field resize-none text-sm"
              rows="2"
              placeholder={language.t('notes')}
              bind:value={notes}
            ></textarea>
          </label>
        </div>
      </div>

      <div class="border-t border-[var(--border)] px-5 py-4">
        {#if serviceFee > 0 || pb1Fee > 0 || discountTotal > 0}
          <div class="mb-1 flex items-center justify-between text-sm text-[var(--text-muted)]"><span>{language.t('subtotal')}</span><span>{formatRupiah(cartTotal)}</span></div>
          {#if discountTotal > 0}<div class="mb-1 flex items-center justify-between text-sm text-[var(--om-brand)]"><span>{language.t('discounts')}</span><span>−{formatRupiah(discountTotal)}</span></div>{/if}
          {#if serviceFee > 0}<div class="mb-1 flex items-center justify-between text-sm text-[var(--text-muted)]"><span>{language.t('serviceLabel')}</span><span>{formatRupiah(serviceFee)}</span></div>{/if}
          {#if pb1Fee > 0}<div class="mb-1 flex items-center justify-between text-sm text-[var(--text-muted)]"><span>{language.t('pb1Label')}</span><span>{formatRupiah(pb1Fee)}</span></div>{/if}
        {/if}
        <div class="mb-3 flex items-center justify-between text-sm">
          <span class="text-[var(--text-muted)]">{language.t('total')}</span>
          <span class="text-xl font-bold text-[var(--espresso)]">{formatRupiah(grandTotal)}</span>
        </div>
        {#if error}
          <p class="mb-2 text-xs text-red-600">{error}</p>
        {/if}
        <button
          class="btn-primary w-full py-3.5 text-base disabled:opacity-60"
          disabled={submitting}
          onclick={submitOrder}
        >{submitting ? language.t('sending') : language.t('sendOrder')}</button>
      </div>
    </section>
  </div>
{/if}

<!-- ── Customization bottom sheet ────────────────────── -->
{#if customizeItem}
  {@const item = customizeItem}
  <div
    class="fixed inset-0 z-50 flex items-end bg-[var(--om-scrim)]"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeCustomize(); }}
  >
    <section class="flex max-h-[92dvh] w-full flex-col rounded-t-3xl bg-[var(--white)]" role="dialog" aria-modal="true">
      <!-- Hero image -->
      {#if item.image_url}
        <div class="h-48 w-full shrink-0 overflow-hidden rounded-t-3xl">
          <img src={mediaUrl(item.image_url)} alt={item.name} class="h-full w-full object-cover" />
        </div>
      {:else}
        <div class="flex h-32 w-full shrink-0 items-center justify-center rounded-t-3xl bg-[var(--white)] text-[var(--text-muted)] opacity-60"><CupcakeIcon size={80} /></div>
      {/if}

      <!-- Header row (name + close) -->
      <div class="flex items-start gap-3 px-5 pt-4">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-2xl font-bold leading-tight text-[var(--espresso)]">{item.name}</h2>
          {#if item.description}
            <p class="mt-1 text-sm text-[var(--text-muted)]">{item.description}</p>
          {/if}
          <p class="mt-1 text-base font-bold text-[var(--warm-brown)]">{formatRupiah(getItemPrice(item))}</p>
        </div>
        <button class="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--cream)]" onclick={closeCustomize}>
          <span class="ms !text-[16px] text-[var(--espresso)]" aria-hidden="true">close</span>
        </button>
      </div>

      <!-- Scrollable modifiers -->
      <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4 space-y-5">

        <!-- Option groups -->
        {#each item.option_groups as group}
          <div>
            <p class="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
              {group.name}
              {#if group.is_required}
                <span class="ml-1 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600">{language.t('required')}</span>
              {:else}
                <span class="ml-1 font-normal normal-case text-[var(--text-muted)]"></span>
              {/if}
            </p>
            <div class="space-y-1.5">
              {#each group.choices as choice}
                {@const selected = customizeOptions[group.id] === choice.id}
                <button
                  class="flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition
                         {selected ? 'border-[var(--espresso)] bg-[var(--cream)]' : 'border-[var(--border)] hover:border-[var(--mid-brown)]'}"
                  onclick={() => { customizeOptions = { ...customizeOptions, [group.id]: choice.id }; }}
                >
                  <span class="grid h-4 w-4 shrink-0 place-items-center rounded-full border-2
                               {selected ? 'border-[var(--espresso)]' : 'border-[var(--border)]'}">
                    {#if selected}
                      <span class="h-2 w-2 rounded-full bg-[var(--espresso)]"></span>
                    {/if}
                  </span>
                  <span class="flex-1 text-sm font-semibold text-[var(--espresso)]">{choice.label}</span>
                  {#if (choice.extra_price ?? 0) > 0}
                    <span class="text-xs font-bold text-[var(--warm-brown)]">+{formatRupiah(choice.extra_price ?? 0)}</span>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/each}

        <!-- Addon groups -->
        {#each item.addon_groups as group}
          <div>
            <p class="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
              {group.name}
              {#if group.is_required && group.min_select > 0}
                <span class="ml-1 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600">{language.t('required')} {group.min_select}</span>
              {:else}
                <span class="ml-1 font-normal normal-case text-[var(--text-muted)]"></span>
              {/if}
            </p>
            <div class="space-y-1.5">
              {#each group.choices.filter(c => c.is_available) as choice}
                {@const checked = customizeAddons.has(choice.id)}
                <button
                  class="flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition
                         {checked ? 'border-[var(--espresso)] bg-[var(--cream)]' : 'border-[var(--border)] hover:border-[var(--mid-brown)]'}"
                  onclick={() => toggleAddon(choice.id)}
                >
                  <span class="grid h-4 w-4 shrink-0 place-items-center rounded border-2
                               {checked ? 'border-[var(--espresso)] bg-[var(--espresso)]' : 'border-[var(--border)]'}">
                    {#if checked}
                      <svg class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 10 10" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M1.5 5l2.5 2.5 4.5-5" />
                      </svg>
                    {/if}
                  </span>
                  <span class="flex-1 text-sm font-semibold text-[var(--espresso)]">{choice.label}</span>
                  {#if choice.extra_price > 0}
                    <span class="text-xs font-bold text-[var(--warm-brown)]">+{formatRupiah(choice.extra_price)}</span>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/each}
      </div>

      <!-- Footer: qty + confirm -->
      <div class="border-t border-[var(--border)] px-5 py-4">
        <div class="mb-4 flex items-center justify-between">
          <span class="text-sm font-bold text-[var(--text-muted)]">{language.t('quantity')}</span>
          <div class="flex items-center gap-4">
            <button
              class="grid h-9 w-9 place-items-center rounded-full bg-[var(--cream)] transition hover:bg-[var(--light-brown)] disabled:opacity-40"
              disabled={customizeQty <= 1}
              onclick={() => { if (customizeQty > 1) customizeQty--; }}
            ><span class="ms !text-[16px] text-[var(--espresso)]" aria-hidden="true">remove</span></button>
            <span class="w-6 text-center text-lg font-bold text-[var(--espresso)]">{customizeQty}</span>
            <button
              class="grid h-9 w-9 place-items-center rounded-full bg-[var(--espresso)] transition"
              onclick={() => { customizeQty++; }}
            ><span class="ms !text-[16px] text-white" aria-hidden="true">add</span></button>
          </div>
        </div>
        <button
          class="btn-primary w-full py-3.5 text-base disabled:opacity-50"
          disabled={!customizeCanAdd}
          onclick={confirmCustomize}
        >
          {customizeCanAdd
            ? `${language.t('add')} · ${formatRupiah(customizeTotal)}`
            : language.t('required')}
        </button>
      </div>
    </section>
  </div>
{/if}

<style>
  .scrollbar-none { scrollbar-width: none; }
  .scrollbar-none::-webkit-scrollbar { display: none; }
</style>
