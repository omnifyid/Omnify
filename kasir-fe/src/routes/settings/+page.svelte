<script lang="ts">
  import Toggle from '$lib/components/Toggle.svelte';
  import { api, apiRequest } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import type { ChannelSetting } from '$lib/api/types';
  import { formatDigits, parseAmount } from '$lib/utils/finance';
  import { formatRupiah } from '$lib/utils/format';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { SEG_GROUP, seg, chip } from '$lib/utils/ui';
  import { DEFAULT_EXPENSE_CATEGORIES, expenseCategories } from '$lib/utils/finance';
  import { BANK_PRESETS, QRIS_WALLET_PRESETS, paymentOptions, type MethodVariants, type PaymentOptions } from '$lib/utils/payment';
  import ReceiptView from '$lib/components/ReceiptView.svelte';
  import { customerReceipt, kitchenTicket, paperChars, RECEIPT_DEFAULTS, receiptOptions, sampleOrder, type ReceiptOptions } from '$lib/utils/receipt';
  import type { MessageKey } from '$lib/i18n/messages';

  // ── Form state ────────────────────────────────────────────
  let storeName = $state('');
  let address = $state('');
  let phone = $state('');
  // what the customer receipt and kitchen ticket print; saved with the Nota tab
  let rc = $state<ReceiptOptions>({ ...RECEIPT_DEFAULTS });
  let previewTab = $state<'customer' | 'kitchen'>('customer');

  // ── POS settings ──────────────────────────────────────────
  let posDineIn = $state(false);
    let posTableCount = $state(10);
  let posCustomerName = $state(false);
  // module switches save immediately (tab Modul); selforder = accepting QR orders now
  let mods = $state({ selforder: false, tables: false, kitchen: false, inventory: true, finance: true });
  let moduleBusy = $state(false);
  let moduleNotice = $state('');

  // ── Online platforms (Owner only) ─────────────────────────
  type ChannelForm = { channel: ChannelSetting['channel']; enabled: boolean; commission: string; markup: string; lag: string };
  const CHANNEL_NAMES: Record<string, string> = { GOFOOD: 'GoFood', GRABFOOD: 'GrabFood', SHOPEEFOOD: 'ShopeeFood' };
  let channelForms = $state<ChannelForm[]>([]);
  let taxPct = $state('');
  let servicePct = $state('');
  let pb1Pct = $state('');
  let expCats = $state<string[]>([]);
  let newCat = $state('');
  let pay = $state<PaymentOptions>(paymentOptions(null));
  let payCustom = $state({ edc: '', qris: '' });
  let feeOn = $state({ service: false, pb1: false });
  let shiftThreshold = $state('');
  let defaultFloat = $state('');
  let isOwner = $derived(session.selectedStore?.role === 'OWNER');
  let branchName = $state('');
  let addingBranch = $state(false);
  let branchError = $state('');
  let branchOpen = $state(false);
  let openBusy = $state<string | null>(null);
  let editingId = $state<string | null>(null); // expanded outlet card

  async function setOutletOpen(id: string, open: boolean) {
    openBusy = id;
    try {
      await api.patch(`/stores/${id}`, { is_open: open });
      await session.loadStores();
    } catch (e) {
      saveError = e instanceof Error ? e.message : String(e);
    } finally {
      openBusy = null;
    }
  }

  async function addBranch() {
    const storeId = session.selectedStore?.id;
    const name = branchName.trim();
    if (!storeId || !name) return;
    addingBranch = true;
    branchError = '';
    try {
      const created = await api.post<{ id: string }>(`/stores/${storeId}/branches`, { name });
      await session.loadStores();
      session.selectedStoreId = created.id;
      branchName = '';
      branchOpen = false;
    } catch (e) {
      branchError = e instanceof Error ? e.message : String(e);
    } finally {
      addingBranch = false;
    }
  }
  const pctText = (bp: number) => (bp ? String(bp / 100) : '');
  const toBp = (v: string) => Math.max(0, Math.round((parseFloat(v.replace(',', '.')) || 0) * 100));

  async function loadChannels() {
    const storeId = session.selectedStore?.id;
    if (!storeId || session.selectedStore?.role !== 'OWNER') { channelForms = []; return; }
    try {
      const list = await api.get<ChannelSetting[]>(`/stores/${storeId}/channels`);
      channelForms = list.map((c) => ({ channel: c.channel, enabled: c.enabled, commission: pctText(c.commission_bp), markup: pctText(c.markup_bp), lag: String(c.payout_lag_days) }));
    } catch { channelForms = []; }
  }


  // ── Tabs (like new-ui) ────────────────────────────────────
  type Tab = 'modules' | 'store' | 'receipt' | 'pos' | 'payment' | 'channels' | 'policy';
  let tabs = $derived<[Tab, MessageKey][]>([
    ['modules', 'settingsTabModules'],
    ['store', 'settingsTabStore'],
    ['receipt', 'settingsTabReceipt'],
    ['pos', 'settingsTabPos'],
    ['payment', 'settingsTabPay'],
    ...(isOwner && channelForms.length ? ([['channels', 'settingsTabChannels']] as [Tab, MessageKey][]) : []),
    ...(isOwner ? ([['policy', 'settingsTabPolicy']] as [Tab, MessageKey][]) : [])
  ]);
  let tab = $derived<Tab>((() => {
    const t = $page.url.searchParams.get('tab') as Tab | null;
    return t && tabs.some(([k]) => k === t) ? t : 'modules';
  })());
  function setTab(next: Tab) {
    goto(next === 'modules' ? '/settings' : `/settings?tab=${next}`, { replaceState: true, noScroll: true, keepFocus: true });
  }
  let hasPreview = $derived(tab === 'receipt');

  // ── Modules ───────────────────────────────────────────────
  type ModKey = keyof typeof mods;
  let modules = $derived<{ key: ModKey; icon: string; name: MessageKey; desc: MessageKey; locked?: MessageKey }[]>([
    {
      key: 'selforder', icon: 'qr_code_2', name: 'modSelfOrder', desc: 'modSelfOrderDesc',
      locked: !session.selectedStore?.self_order_enabled ? 'modLockedAdmin' : !isOwner ? 'modOwnerOnly' : undefined
    },
    { key: 'tables', icon: 'table_restaurant', name: 'modTables', desc: 'modTablesDesc' },
    { key: 'kitchen', icon: 'coffee_maker', name: 'kitchenManagement', desc: 'kitchenManagementDesc' },
    { key: 'inventory', icon: 'inventory_2', name: 'inventory', desc: 'modInventoryDesc' },
    { key: 'finance', icon: 'account_balance_wallet', name: 'finance', desc: 'modFinanceDesc' }
  ]);
  let modulesOn = $derived(modules.filter((m) => !m.locked && mods[m.key]).length);

  async function setModule(key: ModKey, value: boolean) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    moduleBusy = true;
    saveError = '';
    moduleNotice = '';
    try {
      if (key === 'selforder') await api.patch(`/stores/${storeId}/selforder`, { is_open: value });
      else {
        const field = { tables: 'pos_table_enabled', kitchen: 'kitchen_enabled', inventory: 'inventory_enabled', finance: 'finance_enabled' }[key];
        await api.patch(`/stores/${storeId}`, { [field]: value });
      }
      await session.loadStores();
      moduleNotice = language.t('modSaved');
      setTimeout(() => (moduleNotice = ''), 3000);
    } catch (err) {
      mods[key] = !value;
      saveError = err instanceof Error ? err.message : 'Save failed';
    } finally {
      moduleBusy = false;
    }
  }

  // ── Logo upload ───────────────────────────────────────────
  let logoUrl = $state<string | null>(null);
  let logoPreviewUrl = $state<string | null>(null);
  let uploading = $state(false);
  let uploadError = $state('');

  // ── Save state ────────────────────────────────────────────
  let saving = $state(false);
  let saveError = $state('');
  let saveSuccess = $state('');

  // ── Load ──────────────────────────────────────────────────
  function initFromStore() {
    const s = session.selectedStore;
    if (!s) return;
    storeName = s.name;
    address = s.address ?? '';
    phone = s.phone ?? '';
    rc = receiptOptions(s);
    pay = paymentOptions(s);
    expCats = [...expenseCategories(s)];
    logoUrl = s.logo_url ?? null;
    logoPreviewUrl = null;
    posDineIn = s.pos_dine_in_enabled ?? false;
    mods.tables = s.pos_table_enabled ?? false;
    posTableCount = s.pos_table_count ?? 10;
    posCustomerName = s.pos_customer_name_enabled ?? false;
    mods.kitchen = s.kitchen_enabled ?? false;
    mods.inventory = s.inventory_enabled !== false;
    mods.finance = s.finance_enabled !== false;
    mods.selforder = s.selforder_is_open !== false;
    taxPct = pctText(s.tax_bp ?? 0);
    servicePct = pctText(s.service_bp ?? 0);
    pb1Pct = pctText(s.pb1_bp ?? 0);
    feeOn = { service: (s.service_bp ?? 0) > 0, pb1: (s.pb1_bp ?? 0) > 0 };
    shiftThreshold = formatDigits(String(s.shift_variance_threshold ?? 20000));
    defaultFloat = formatDigits(String(s.default_float ?? 0));
    void loadChannels();
  }

  // wait for the store list before judging the role (direct URL loads start with no store)
  $effect(() => {
    const role = session.selectedStore?.role;
    if (session.selectedStore && role !== 'OWNER' && role !== 'MANAGER') void goto('/dashboard');
  });

  let lastStoreId = $state('');
  $effect(() => {
    const id = session.selectedStore?.id ?? '';
    if (id && id !== lastStoreId) { lastStoreId = id; initFromStore(); }
  });

  // ── Logo file select ──────────────────────────────────────
  async function handleLogoFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      uploadError = 'Only JPEG, PNG, and WebP files are allowed.';
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      uploadError = 'File must be under 2 MB.';
      return;
    }

    uploadError = '';
    logoPreviewUrl = URL.createObjectURL(file);

    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    uploading = true;
    try {
      const formData = new FormData();
      formData.append('file', file);
      const updated = await apiRequest<{ logo_url: string }>(`/stores/${storeId}/logo`, {
        method: 'POST',
        body: formData,
      });
      logoUrl = updated.logo_url;
      await session.loadStores();
    } catch (err) {
      uploadError = err instanceof Error ? err.message : 'Upload failed';
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  // ── Save ──────────────────────────────────────────────────
  async function save() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    saveError = ''; saveSuccess = '';
    saving = true;
    try {
      await api.patch(`/stores/${storeId}`, {
        name: storeName,
        address: address.trim() || null,
        phone: phone.trim() || null,
        payment_options: $state.snapshot(pay),
        ...(isOwner && expCats.length ? { expense_categories: $state.snapshot(expCats) } : {}),
        receipt_options: { ...rc, k_title: rc.k_title.trim() || RECEIPT_DEFAULTS.k_title },
        pos_dine_in_enabled: posDineIn,
        pos_table_enabled: mods.tables,
        pos_table_count: posTableCount,
        pos_customer_name_enabled: posCustomerName,
        kitchen_enabled: mods.kitchen,
        inventory_enabled: mods.inventory,
        finance_enabled: mods.finance,
        ...(isOwner ? { tax_bp: toBp(taxPct), service_bp: feeOn.service ? toBp(servicePct) : 0, pb1_bp: feeOn.pb1 ? toBp(pb1Pct) : 0, shift_variance_threshold: parseAmount(shiftThreshold), default_float: parseAmount(defaultFloat) } : {}),
      });
      if (isOwner) {
        await Promise.all(
          channelForms.map((c) =>
            api.patch(`/stores/${storeId}/channels/${c.channel}`, {
              enabled: c.enabled,
              commission_bp: toBp(c.commission),
              markup_bp: toBp(c.markup),
              payout_lag_days: Math.max(0, parseInt(c.lag, 10) || 0)
            })
          )
        );
      }
      saveSuccess = language.t('savedSuccessfully');
      await session.loadStores();
    } catch (err) {
      saveError = err instanceof Error ? err.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  // ── Logo display URL ──────────────────────────────────────
  const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') ?? 'http://localhost:8000';
  let displayLogoUrl = $derived(
    logoPreviewUrl
      ? logoPreviewUrl
      : logoUrl
        ? (logoUrl.startsWith('http') ? logoUrl : `${API_BASE}${logoUrl}`)
        : null
  );

  // ── Live preview: a sample order with the form values ────
  let previewStore = $derived({
    name: storeName || language.t('storeName'),
    logo_url: displayLogoUrl,
    address,
    phone,
    receipt_options: rc
  });
  let previewLines = $derived(
    previewTab === 'kitchen' ? kitchenTicket(sampleOrder(), previewStore, rc) : customerReceipt(sampleOrder(), previewStore, rc)
  );

</script>

<svelte:head><title>{language.t('settings')} | Kasir</title></svelte:head>

<div class="mb-8">
  <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('settings')}</h1>
  <p class="mt-1 text-[var(--text-muted)]">{language.t('settingsSubtitle')}</p>
</div>

<div class="settings-layout" class:single={!hasPreview}>
  <!-- ── Form column ───────────────────────────────────────── -->
  <div class="form-col">

    <div class="{SEG_GROUP} mb-6" role="tablist" aria-label={language.t('settings')}>
      {#each tabs as [key, label] (key)}
        <button role="tab" aria-selected={tab === key} class="{seg(tab === key)} !px-4" style="min-height: var(--om-tap)" onclick={() => setTab(key)}>{language.t(label)}</button>
      {/each}
    </div>

    {#if tab === 'modules'}
    <!-- ── Modules ─────────────────────────────────────────── -->
    <div class="mb-8">
      <div class="mb-4 flex flex-col gap-1">
        <span class="text-[16px] font-semibold">{language.t('modulesActive')} · {modulesOn}/{modules.length}</span>
        <span class="text-[var(--om-text-secondary)]">{language.t('modulesHint')}</span>
      </div>
      {#if moduleNotice}
        <div class="mb-4 rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700" role="status">{moduleNotice}</div>
      {/if}
      {#if saveError}
        <div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{saveError}</div>
      {/if}
      <div class="grid gap-3" style="grid-template-columns: repeat(auto-fill, minmax(min(100%, 380px), 1fr))">
        {#each modules as m (m.key)}
          {@const on = mods[m.key] && !m.locked}
          <div class="flex items-center gap-4 rounded-[14px] border-[1.5px] bg-white p-4 {on ? 'border-[var(--om-brand)]' : 'border-[var(--om-border)]'}">
            <div class="grid h-11 w-11 shrink-0 place-items-center rounded-xl {on ? 'bg-[var(--om-brand-tint)] text-[var(--om-brand)]' : 'bg-[var(--om-fill-muted)] text-[var(--om-text-secondary)]'}"><span class="ms" aria-hidden="true">{m.icon}</span></div>
            <div class="flex min-w-0 flex-1 flex-col gap-0.5">
              <span class="font-semibold">{language.t(m.name)}</span>
              <span class="text-xs leading-snug text-[var(--om-text-secondary)]">{language.t(m.desc)}</span>
              <span class="text-xs {on ? 'text-[var(--om-brand)]' : 'text-[var(--om-text-secondary)]'}">{m.locked ? language.t(m.locked) : on ? language.t('modOn') : language.t('modOff')}</span>
            </div>
            <Toggle bind:checked={mods[m.key]} disabled={moduleBusy || !!m.locked} label={language.t(m.name)} onchange={(v) => setModule(m.key, v)} />
          </div>
        {/each}
      </div>
    </div>

    {:else if tab === 'store'}
    <!-- ── Outlets (parent + branches) ─────────────────────── -->
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <p class="min-w-[16rem] flex-1 text-sm leading-relaxed text-[var(--text-muted)]">{language.t('outletIntro')}</p>
      {#if isOwner}
        <button type="button" class="btn-primary flex shrink-0 items-center gap-1.5" onclick={() => { branchName = ''; branchError = ''; branchOpen = true; }}>
          <span class="ms" aria-hidden="true">add</span>{language.t('addBranch')}
        </button>
      {/if}
    </div>

    <div class="space-y-3">
      {#each session.stores as st (st.id)}
        {@const isCurrent = st.id === session.selectedStore?.id}
        {@const editing = isCurrent && editingId === st.id}
        <div class="card p-4 {isCurrent ? '!border-[var(--om-brand)]' : ''}">
          <div class="flex flex-wrap items-start gap-3.5">
            <div class="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-[var(--om-ink)] text-[var(--om-brand-bright)]"><span class="ms" aria-hidden="true">storefront</span></div>
            <div class="flex min-w-0 flex-1 basis-[16rem] flex-col gap-1.5">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-base font-semibold">{isCurrent ? storeName || st.name : st.name}</span>
                <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold {st.is_parent ? 'bg-[var(--om-brand-tint)] text-[var(--om-brand)]' : 'bg-[var(--om-fill-muted)] text-[var(--om-text-secondary)]'}">{st.is_parent ? language.t('parentBadge') : language.t('branchBadge')}</span>
                {#if isCurrent}<span class="rounded-full border border-[var(--om-brand)] px-2.5 py-0.5 text-xs font-semibold text-[var(--om-brand)]">{language.t('active')}</span>{/if}
              </div>
              <span class="text-xs text-[var(--text-muted)]">
                {#if st.is_parent}
                  {st.has_branches ? language.t('parentInfo') : language.t('parentOnlyInfo')}
                {:else}
                  {language.t('branchInfo').replace('{parent}', st.parent_store_name ?? '')}
                {/if}
              </span>
              <span class="text-xs text-[#3B3F38]">{[st.address, st.phone].filter(Boolean).join(' · ') || '—'}</span>
              <div class="flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#3B3F38]">
                <span>{language.t('pb1Label')} <strong>{(isCurrent ? (feeOn.pb1 ? Number(pb1Pct.replace(',', '.')) || 0 : 0) : (st.pb1_bp ?? 0) / 100)}%</strong></span>
                <span>{language.t('serviceLabel')} <strong>{(isCurrent ? (feeOn.service ? Number(servicePct.replace(',', '.')) || 0 : 0) : (st.service_bp ?? 0) / 100)}%</strong></span>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <label class="flex cursor-pointer items-center gap-2 text-xs font-semibold {st.is_open === false ? 'text-red-700' : 'text-[var(--om-brand)]'}" title={st.is_open === false ? language.t('outletClosedHint') : ''}>
                {st.is_open === false ? language.t('outletClosed') : language.t('outletOpen')}
                <Toggle compact checked={st.is_open !== false} disabled={openBusy === st.id} label={st.name} onchange={(v) => setOutletOpen(st.id, v)} />
              </label>
              <button type="button" class="btn-outline" aria-expanded={editing} onclick={() => { if (editing) editingId = null; else { saveError = ''; session.selectedStoreId = st.id; editingId = st.id; } }}>{editing ? language.t('close') : language.t('edit')}</button>
            </div>
          </div>

          {#if editing}
            <div class="mt-4 grid gap-4 border-t border-[var(--border)] pt-4 sm:grid-cols-2">
              <label for="store-name" class="block">
                <span class="field-label">{language.t('storeName')}</span>
                <input id="store-name" class="field mt-1" bind:value={storeName} />
              </label>
              <label for="store-phone" class="block">
                <span class="field-label">{language.t('storePhone')}</span>
                <input id="store-phone" class="field mt-1" type="tel" maxlength="30" bind:value={phone} />
              </label>
              <label for="store-address" class="block sm:col-span-2">
                <span class="field-label">{language.t('storeAddress')}</span>
                <textarea id="store-address" class="field mt-1" rows="2" maxlength="300" bind:value={address}></textarea>
              </label>
              {#if isOwner}
                <div class="sm:col-span-2">
                  {#each [['service', 'serviceLabel'], ['pb1', 'pb1Label']] as [key, label] (key)}
                    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm last:border-0">
                      <label class="flex flex-1 cursor-pointer items-center justify-between gap-3">
                        <span class="font-semibold text-[var(--espresso)]">{language.t(label as MessageKey)}</span>
                        <Toggle compact bind:checked={feeOn[key as 'service' | 'pb1']} />
                      </label>
                      {#if feeOn[key as 'service' | 'pb1']}
                        <div class="flex items-center gap-1.5">
                          {#if key === 'service'}
                            <input class="field !min-h-0 h-9 w-24 !py-0 text-right" inputmode="decimal" placeholder="0" aria-label={language.t('settingsServicePct')} bind:value={servicePct} />
                          {:else}
                            <input class="field !min-h-0 h-9 w-24 !py-0 text-right" inputmode="decimal" placeholder="0" aria-label={language.t('settingsPb1Pct')} bind:value={pb1Pct} />
                          {/if}
                          <span class="text-sm text-[var(--text-muted)]">%</span>
                        </div>
                      {/if}
                    </div>
                  {/each}
                  <p class="pt-2 text-xs text-[var(--text-muted)]">{language.t('settingsFeesHint')}</p>
                </div>
              {/if}
              <div class="flex flex-col gap-2 sm:col-span-2">
                {#if saveError}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{saveError}</div>{/if}
                <div class="flex justify-end gap-3">
                  <button type="button" class="btn-outline" onclick={() => { editingId = null; saveError = ''; initFromStore(); }}>{language.t('cancel')}</button>
                  <button type="button" class="btn-primary" disabled={saving} onclick={async () => { await save(); if (!saveError) editingId = null; }}>{saving ? language.t('saving') : language.t('saveChanges')}</button>
                </div>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    {#if branchOpen}
      <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) branchOpen = false; }}>
        <section class="flex w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
          <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
            <h2 class="display-font min-w-0 flex-1 truncate text-2xl font-bold text-[var(--espresso)]">{language.t('addBranch')}</h2>
            <button class="btn-outline px-4 py-2" onclick={() => (branchOpen = false)}>{language.t('close')}</button>
          </div>
          <div class="space-y-3 p-5">
            <p class="text-xs text-[var(--text-muted)]">{language.t('branchesDesc')}</p>
            {#if branchError}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{branchError}</div>{/if}
            <label class="block">
              <span class="field-label">{language.t('branchName')}</span>
              <input class="field mt-1" bind:value={branchName} onkeydown={(e) => { if (e.key === 'Enter') addBranch(); }} />
            </label>
          </div>
          <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
            <button class="btn-outline" onclick={() => (branchOpen = false)}>{language.t('cancel')}</button>
            <button class="btn-primary" disabled={addingBranch || !branchName.trim()} onclick={addBranch}>{language.t('addBranch')}</button>
          </div>
        </section>
      </div>
    {/if}

    {:else if tab === 'receipt'}
    {#snippet paperRow()}
          <div class="flex items-center gap-2.5">
            <span class="field-label">{language.t('rcPaper')}</span>
            <div class={SEG_GROUP} role="group" aria-label={language.t('rcPaper')}>
              {#each ['58', '80'] as w (w)}
                <button type="button" class="{seg(rc.paper === w)} !px-3 text-sm" style="min-height: 36px" aria-pressed={rc.paper === w} onclick={() => (rc.paper = w as ReceiptOptions['paper'])}>{w} mm</button>
              {/each}
            </div>
          </div>
    {/snippet}

    <div class="{SEG_GROUP} mb-4 lg:hidden" role="tablist" aria-label={language.t('receipt')}>
      {#each [['customer', 'rcCustomer'], ['kitchen', 'rcKitchen']] as [key, label] (key)}
        <button role="tab" aria-selected={previewTab === key} class="{seg(previewTab === key)} !px-4" style="min-height: var(--om-tap)" onclick={() => (previewTab = key as typeof previewTab)}>{language.t(label as MessageKey)}</button>
      {/each}
    </div>

    {#if previewTab === 'customer'}
    <div class="mb-5">
      <div class="card space-y-4 p-4">
        <div class="flex flex-wrap items-center gap-x-6 gap-y-3">
          {@render paperRow()}
        </div>
      </div>
    </div>


    <div class="mb-5">
      <div class="card grid gap-x-8 px-4 py-1 sm:grid-cols-2">
        {#each [['show_addr', 'rcShowAddr'], ['show_phone', 'rcShowPhone'], ['show_cashier', 'rcShowCashier'], ['show_cust', 'rcShowCust'], ['show_no', 'rcShowNo'], ['show_mods', 'rcShowMods'], ['show_tax', 'rcShowTax'], ['show_pay', 'rcShowPay']] as [key, label] (key)}
          <label class="flex cursor-pointer items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
            <span class="text-[var(--espresso)]">{language.t(label as MessageKey)}</span>
            <Toggle compact bind:checked={rc[key as keyof ReceiptOptions] as boolean} />
          </label>
        {/each}
      </div>
    </div>


    {:else}
    <div class="mb-5">
      <div class="card p-4">
        {@render paperRow()}
      </div>
    </div>

    <div class="mb-5">
      <div class="card space-y-2 p-4">
        <label class="flex flex-wrap items-center gap-3">
          <span class="field-label">{language.t('rcKitchenTitle')}</span>
          <input class="field !min-h-0 h-9 max-w-[14rem] !py-0" maxlength="30" bind:value={rc.k_title} />
        </label>
        <div class="grid gap-x-8 sm:grid-cols-2">
          {#each [['k_outlet', 'rcKOutlet'], ['k_server', 'rcKServer'], ['k_cust', 'rcKCust']] as [key, label] (key)}
            <label class="flex cursor-pointer items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
              <span class="text-[var(--espresso)]">{language.t(label as MessageKey)}</span>
              <Toggle compact bind:checked={rc[key as keyof ReceiptOptions] as boolean} />
            </label>
          {/each}
        </div>
        <p class="text-xs text-[var(--text-muted)]">{language.t('rcKitchenNote')}</p>
      </div>
    </div>
    {/if}
    {:else if tab === 'pos'}
    <!-- ── POS ─────────────────────────────────────────────── -->
    <div class="mb-5">
      <p class="section-label">POS</p>
      <div class="card px-4 py-1">
        <label class="flex cursor-pointer items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
          <span class="font-semibold text-[var(--espresso)]">{language.t('serviceOptionTitle')}</span>
          <Toggle compact bind:checked={posDineIn} />
        </label>
        <div class="flex items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
          <label class="flex flex-1 cursor-pointer items-center justify-between gap-3">
            <span class="font-semibold text-[var(--espresso)]">{language.t('tableNumber')}</span>
            <Toggle compact bind:checked={mods.tables} />
          </label>
          {#if mods.tables}
            <input class="field !min-h-0 h-9 w-20 !py-0" type="number" min="1" max="200" aria-label={language.t('tableCount')} title={language.t('tableCount')} bind:value={posTableCount} />
          {/if}
        </div>
        <label class="flex cursor-pointer items-center justify-between gap-3 py-2 text-sm">
          <span class="font-semibold text-[var(--espresso)]">{language.t('customerName')}</span>
          <Toggle compact bind:checked={posCustomerName} />
        </label>
      </div>
    </div>

    {:else if tab === 'payment'}
    <!-- ── Payment methods ─────────────────────────────────── -->
    {#snippet variantEditor(v: MethodVariants, kind: 'edc' | 'qris', groups: [string, string[]][])}
      {@const known = groups.flatMap(([, items]) => items)}
      {@const others = v.options.filter((o) => !known.includes(o))}
      <div class="space-y-2 pb-3">
        {#each groups as [label, items] (label)}
          <div>
            <span class="mb-1 block text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{label}</span>
            <div class="flex flex-wrap gap-1.5">
              {#each items as name (name)}
                {@const on = v.options.includes(name)}
                <button type="button" aria-pressed={on} class="{chip(on)} h-8 text-xs" onclick={() => (v.options = on ? v.options.filter((o) => o !== name) : [...v.options, name])}>{name}</button>
              {/each}
            </div>
          </div>
        {/each}
        <div>
          <span class="mb-1 block text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('payOthers')}</span>
          <div class="flex flex-wrap items-center gap-1.5">
            {#each others as name (name)}
              <button type="button" class="{chip(true)} h-8 text-xs" aria-label={name} onclick={() => (v.options = v.options.filter((o) => o !== name))}>{name}<span class="ms !text-[14px]" aria-hidden="true">close</span></button>
            {/each}
            <input
              class="field !min-h-0 h-8 w-40 !py-0 text-xs"
              maxlength="40"
              placeholder={language.t('payAddOther')}
              bind:value={payCustom[kind]}
              onkeydown={(e) => {
                if (e.key !== 'Enter') return;
                e.preventDefault();
                const name = payCustom[kind].trim();
                if (name && !v.options.some((o) => o.toLowerCase() === name.toLowerCase())) v.options = [...v.options, name];
                payCustom[kind] = '';
              }}
            />
          </div>
        </div>
      </div>
    {/snippet}

    <div class="mb-5">
      <p class="section-label">{language.t('settingsTabPay')}</p>
      <div class="card px-4 py-1">
        <label class="flex cursor-pointer items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
          <span class="font-semibold text-[var(--espresso)]">{language.t('cash')}</span>
          <Toggle compact bind:checked={pay.cash} />
        </label>
        <div class="border-b border-[var(--border)]">
          <label class="flex cursor-pointer items-center justify-between gap-3 py-2 text-sm">
            <span class="font-semibold text-[var(--espresso)]">{language.t('payEdc')}</span>
            <Toggle compact bind:checked={pay.edc.enabled} />
          </label>
          {#if pay.edc.enabled}{@render variantEditor(pay.edc, 'edc', [[language.t('payBanks'), BANK_PRESETS]])}{/if}
        </div>
        <div class="border-b border-[var(--border)]">
          <label class="flex cursor-pointer items-center justify-between gap-3 py-2 text-sm">
            <span class="font-semibold text-[var(--espresso)]">{language.t('payQris')}</span>
            <Toggle compact bind:checked={pay.qris.enabled} />
          </label>
          {#if pay.qris.enabled}{@render variantEditor(pay.qris, 'qris', [[language.t('payBanks'), BANK_PRESETS], [language.t('payWallets'), QRIS_WALLET_PRESETS]])}{/if}
        </div>
        <label class="flex cursor-pointer items-center justify-between gap-3 py-2 text-sm">
          <span class="font-semibold text-[var(--espresso)]">{language.t('transfer')}</span>
          <Toggle compact bind:checked={pay.transfer} />
        </label>
      </div>
      <p class="mt-2 px-1 text-xs text-[var(--text-muted)]">{language.t('payHint')}</p>
    </div>

    {:else if tab === 'channels'}
    <!-- ── Online platforms (Owner) ────────────────────────── -->
    {#if isOwner && channelForms.length}
      <div class="mb-5">
        <p class="section-label">{language.t('channelsSettings')}</p>
        <div class="card px-4 py-1">
          <p class="border-b border-[var(--border)] py-2 text-xs text-[var(--text-muted)]">{language.t('channelsSettingsDesc')}</p>
          {#each channelForms as c (c.channel)}
            <div class="border-b border-[var(--border)] py-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 text-sm">
                <span class="font-semibold text-[var(--espresso)]">{CHANNEL_NAMES[c.channel]}</span>
                <Toggle compact bind:checked={c.enabled} />
              </label>
              {#if c.enabled}
                <div class="mt-2 grid grid-cols-3 gap-2">
                  <label class="block min-w-0">
                    <span class="mb-0.5 block truncate text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('channelCommission')}</span>
                    <input class="field !min-h-0 h-9 !py-0 text-right" inputmode="decimal" placeholder="0" bind:value={c.commission} />
                  </label>
                  <label class="block min-w-0">
                    <span class="mb-0.5 block truncate text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('channelMarkup')}</span>
                    <input class="field !min-h-0 h-9 !py-0 text-right" inputmode="decimal" placeholder="0" bind:value={c.markup} />
                  </label>
                  <label class="block min-w-0">
                    <span class="mb-0.5 block truncate text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('channelPayoutLag')}</span>
                    <input class="field !min-h-0 h-9 !py-0 text-right" inputmode="numeric" placeholder="2" bind:value={c.lag} />
                  </label>
                </div>
              {/if}
            </div>
          {/each}
          <div class="py-2">
            <div class="flex items-center justify-between gap-3 text-sm">
              <span class="font-semibold text-[var(--espresso)]">{language.t('taxRate')}</span>
              <input class="field !min-h-0 h-9 w-24 !py-0 text-right" inputmode="decimal" placeholder="0" aria-label={language.t('taxRate')} bind:value={taxPct} />
            </div>
            <span class="mt-1 block text-xs text-[var(--text-muted)]">{language.t('taxRateDesc')}</span>
          </div>
        </div>
      </div>
    {/if}

    {:else if tab === 'policy'}
    {#if isOwner}
      <div class="mb-5">
        <p class="section-label">{language.t('expCatTitle')}</p>
        <div class="card space-y-3 p-4">
          <div class="flex flex-wrap items-center gap-1.5">
            {#each expCats as name (name)}
              <button type="button" class="{chip(true)} h-8 text-xs" aria-label={name} disabled={expCats.length <= 1} onclick={() => (expCats = expCats.filter((c) => c !== name))}>{name}<span class="ms !text-[14px]" aria-hidden="true">close</span></button>
            {/each}
            <input
              class="field !min-h-0 h-8 w-40 !py-0 text-xs"
              maxlength="50"
              placeholder={language.t('expCatAdd')}
              bind:value={newCat}
              onkeydown={(e) => {
                if (e.key !== 'Enter') return;
                e.preventDefault();
                const name = newCat.trim();
                if (name && expCats.length < 40 && !expCats.some((c) => c.toLowerCase() === name.toLowerCase())) expCats = [...expCats, name];
                newCat = '';
              }}
            />
          </div>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-xs text-[var(--text-muted)]">{language.t('expCatHint')}</p>
            <button type="button" class="text-xs font-bold text-[var(--warm-brown)]" onclick={() => (expCats = [...DEFAULT_EXPENSE_CATEGORIES])}>{language.t('expCatReset')}</button>
          </div>
        </div>
      </div>
    {/if}

    <!-- ── Shift & cash (Owner) ────────────────────────────── -->
    {#if isOwner}
      <div class="mb-8">
        <p class="section-label">{language.t('finTabShift')}</p>
        <div class="card grid gap-3 p-5 sm:grid-cols-2">
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('settingsShiftThreshold')}</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={shiftThreshold} oninput={(e) => { shiftThreshold = formatDigits(e.currentTarget.value); e.currentTarget.value = shiftThreshold; }} />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('settingsDefaultFloat')}</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={defaultFloat} oninput={(e) => { defaultFloat = formatDigits(e.currentTarget.value); e.currentTarget.value = defaultFloat; }} />
          </label>
          <p class="text-xs text-[var(--text-muted)] sm:col-span-2">{language.t('settingsShiftHint')}</p>
        </div>
      </div>
    {/if}

    {/if}

    {#if tab !== 'modules' && tab !== 'store'}
    <!-- ── Save (floating) ─────────────────────────────────── -->
    <div class="sticky bottom-4 z-30 mt-6 space-y-2">
      {#if saveError}
        <div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 shadow-lg">{saveError}</div>
      {/if}
      {#if saveSuccess}
        <div class="rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700 shadow-lg">{saveSuccess}</div>
      {/if}
      <button class="btn-primary w-full shadow-lg" onclick={save} disabled={saving}>
        {saving ? language.t('saving') : language.t('saveChanges')}
      </button>
    </div>

    {/if}
  </div>

  <!-- ── Preview column ────────────────────────────────────── -->
  {#if hasPreview}
  <div class="preview-col">
    <div class="preview-sticky">
      <div class="{SEG_GROUP} mb-3 hidden lg:flex" role="tablist" aria-label={language.t('livePreview')}>
        {#each [['customer', 'rcCustomer'], ['kitchen', 'rcKitchen']] as [key, label] (key)}
          <button role="tab" aria-selected={previewTab === key} class="{seg(previewTab === key)} !px-4" style="min-height: var(--om-tap)" onclick={() => (previewTab = key as typeof previewTab)}>{language.t(label as MessageKey)}</button>
        {/each}
      </div>
      <div class="preview-paper">
        <ReceiptView lines={previewLines} paper={rc.paper} />
      </div>
    </div>
  </div>
  {/if}
</div>

<style>
  .settings-layout {
    display: grid;
    gap: 2rem;
    align-items: start;
  }
  @media (min-width: 1024px) {
    .settings-layout { grid-template-columns: 1fr 300px; }
  }

  .settings-layout.single { grid-template-columns: minmax(0, 920px); }
  .form-col { min-width: 0; }
  .preview-col { min-width: 0; align-self: stretch; } /* full height so the preview can stick while scrolling */

  .preview-sticky {
    position: sticky;
    top: 1.5rem;
  }

  .section-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
    padding-left: 0.25rem;
  }

  .field-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .logo-thumb {
    width: 72px;
    height: 72px;
    flex-shrink: 0;
    border-radius: 14px;
    border: 1.5px solid var(--border);
    background: var(--cream);
    display: grid;
    place-items: center;
    overflow: hidden;
  }

  .logo-placeholder {
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    background: var(--espresso);
    color: #fff;
    font-family: var(--om-font);
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1;
    border-radius: 14px;
  }

  /* ── Receipt preview ──────────────────────────────────── */
  .preview-paper {
    background: #fff;
    border: 1px solid var(--om-border);
    border-radius: 14px;
    padding: 16px 12px;
    overflow-x: auto;
  }
</style>
