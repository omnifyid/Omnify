<script lang="ts">
  import Toggle from '$lib/components/Toggle.svelte';
  import { api, apiRequest } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import type { ChannelSetting } from '$lib/api/types';
  import { formatDigits, parseAmount } from '$lib/utils/finance';
  import { formatRupiah } from '$lib/utils/format';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  // ── Form state ────────────────────────────────────────────
  let storeName = $state('');
  let showLogo = $state(true);
  let receiptHeader = $state('');
  let receiptFooter = $state('');

  // ── POS settings ──────────────────────────────────────────
  let posDineIn = $state(false);
  let posTable = $state(false);
  let posTableCount = $state(10);
  let posCustomerName = $state(false);
  let kitchenEnabled = $state(false);

  // ── Online platforms (Owner only) ─────────────────────────
  type ChannelForm = { channel: ChannelSetting['channel']; enabled: boolean; commission: string; markup: string; lag: string };
  const CHANNEL_NAMES: Record<string, string> = { GOFOOD: 'GoFood', GRABFOOD: 'GrabFood', SHOPEEFOOD: 'ShopeeFood' };
  let channelForms = $state<ChannelForm[]>([]);
  let taxPct = $state('');
  let servicePct = $state('');
  let pb1Pct = $state('');
  let shiftThreshold = $state('');
  let defaultFloat = $state('');
  let isOwner = $derived(session.selectedStore?.role === 'OWNER');
  let branchName = $state('');
  let addingBranch = $state(false);
  let branchError = $state('');

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

  // ── Logo upload ───────────────────────────────────────────
  let logoUrl = $state<string | null>(null);
  let logoPreviewUrl = $state<string | null>(null);
  let uploading = $state(false);
  let uploadError = $state('');

  // ── Save state ────────────────────────────────────────────
  let saving = $state(false);
  let saveError = $state('');
  let saveSuccess = $state('');

  // ── Char-count helpers ────────────────────────────────────
  const THERMAL_WIDTH = 32;

  function lineWidths(text: string): number[] {
    return text.split('\n').map((l) => l.length);
  }

  let headerLines = $derived(lineWidths(receiptHeader));
  let footerLines = $derived(lineWidths(receiptFooter));
  let headerOverflow = $derived(headerLines.some((w) => w > THERMAL_WIDTH));
  let footerOverflow = $derived(footerLines.some((w) => w > THERMAL_WIDTH));

  // ── Load ──────────────────────────────────────────────────
  function initFromStore() {
    const s = session.selectedStore;
    if (!s) return;
    storeName = s.name;
    showLogo = s.show_logo !== false;
    receiptHeader = s.receipt_header ?? '';
    receiptFooter = s.receipt_footer ?? '';
    logoUrl = s.logo_url ?? null;
    logoPreviewUrl = null;
    posDineIn = s.pos_dine_in_enabled ?? false;
    posTable = s.pos_table_enabled ?? false;
    posTableCount = s.pos_table_count ?? 10;
    posCustomerName = s.pos_customer_name_enabled ?? false;
    kitchenEnabled = s.kitchen_enabled ?? false;
    taxPct = pctText(s.tax_bp ?? 0);
    servicePct = pctText(s.service_bp ?? 0);
    pb1Pct = pctText(s.pb1_bp ?? 0);
    shiftThreshold = formatDigits(String(s.shift_variance_threshold ?? 20000));
    defaultFloat = formatDigits(String(s.default_float ?? 0));
    void loadChannels();
  }

  onMount(() => {
    const role = session.selectedStore?.role;
    if (role !== 'OWNER' && role !== 'MANAGER') { goto('/dashboard'); return; }
    initFromStore();
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
        show_logo: showLogo,
        receipt_header: receiptHeader || null,
        receipt_footer: receiptFooter || null,
        pos_dine_in_enabled: posDineIn,
        pos_table_enabled: posTable,
        pos_table_count: posTableCount,
        pos_customer_name_enabled: posCustomerName,
        kitchen_enabled: kitchenEnabled,
        ...(isOwner ? { tax_bp: toBp(taxPct), service_bp: toBp(servicePct), pb1_bp: toBp(pb1Pct), shift_variance_threshold: parseAmount(shiftThreshold), default_float: parseAmount(defaultFloat) } : {}),
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

  // ── Sample data for receipt preview ──────────────────────
  const SAMPLE_ITEMS = [
    { name: 'Kopi Susu', qty: 1, price: 30000 },
    { name: 'Americano', qty: 2, price: 20000 },
  ];
  const SAMPLE_CUSTOMER = 'Budi Santoso';
  const SAMPLE_TABLE = '5';
</script>

<svelte:head><title>{language.t('settings')} | Kasir</title></svelte:head>

<div class="mb-8">
  <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('settings')}</h1>
  <p class="mt-1 text-[var(--text-muted)]">{language.t('settingsSubtitle')}</p>
</div>

<div class="settings-layout">
  <!-- ── Form column ───────────────────────────────────────── -->
  <div class="form-col">

    <!-- ── Store ──────────────────────────────────────────── -->
    <div class="mb-8">
      <p class="section-label">{language.t('store')}</p>
      <div class="card p-5">

        <label for="store-name" class="block mb-5">
          <span class="field-label">{language.t('storeName')}</span>
          <input id="store-name" class="field mt-1" bind:value={storeName} />
        </label>

        <div class="border-t border-[var(--border)] mb-5"></div>

        <!-- Logo upload -->
        <input
          id="logo-file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style="display:none"
          onchange={handleLogoFile}
        />

        <div class="mb-4 flex items-center gap-4">
          <div class="logo-thumb">
            {#if displayLogoUrl}
              <img src={displayLogoUrl} alt="Store logo" class="h-full w-full object-contain p-1" />
            {:else}
              <div class="logo-placeholder">{(storeName || 'S').charAt(0).toUpperCase()}</div>
            {/if}
          </div>
          <div class="flex-1 min-w-0">
            <span class="field-label mb-2 block">Logo</span>
            <button
              type="button"
              class="btn-outline text-sm {uploading ? 'opacity-50 pointer-events-none' : ''}"
              onclick={() => (document.getElementById('logo-file-input') as HTMLInputElement)?.click()}
              disabled={uploading}
            >
              {uploading ? language.t('loading') : language.t('chooseImage')}
            </button>
            <p class="mt-1 text-xs text-[var(--text-muted)]">JPEG · PNG · WebP · max 2 MB</p>
            {#if uploadError}<p class="mt-1 text-xs text-red-600">{uploadError}</p>{/if}
          </div>
        </div>

        <label class="flex cursor-pointer items-center gap-3 rounded-xl border border-[var(--border)] p-3">
          <Toggle bind:checked={showLogo} />
          <span class="text-sm font-semibold text-[var(--espresso)]">{language.t('showLogoOnReceipt')}</span>
        </label>

      </div>
    </div>

    <!-- ── Receipt ─────────────────────────────────────────── -->
    <div class="mb-8">
      <p class="section-label">{language.t('receipt')}</p>
      <div class="card p-5">

        <!-- Header -->
        <div class="mb-5">
          <span class="field-label">{language.t('receiptHeader')}</span>
          <textarea
            class="field font-mono text-sm mt-1"
            rows="3"
            placeholder={"e.g. Selamat datang!\nWiFi: KopiSenja123"}
            bind:value={receiptHeader}
          ></textarea>
          {#if receiptHeader.trim()}
            <div class="mt-2 space-y-0.5">
              {#each headerLines as len, i}
                <div class="flex items-center gap-2 text-xs">
                  <span class="w-14 text-[var(--text-muted)]">Line {i + 1}:</span>
                  <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--cream)]">
                    <div
                      class="h-full rounded-full transition-all {len > THERMAL_WIDTH ? 'bg-red-400' : 'bg-green-400'}"
                      style="width: {Math.min(100, (len / THERMAL_WIDTH) * 100)}%"
                    ></div>
                  </div>
                  <span class="{len > THERMAL_WIDTH ? 'text-red-500 font-bold' : 'text-[var(--text-muted)]'}">{len}/{THERMAL_WIDTH}</span>
                </div>
              {/each}
              {#if headerOverflow}
                <p class="text-xs font-semibold text-red-500">Lines over 32 chars may wrap on 58mm paper.</p>
              {/if}
            </div>
          {/if}
        </div>

        <div class="border-t border-[var(--border)] mb-5"></div>

        <!-- Footer -->
        <div>
          <span class="field-label">{language.t('receiptFooter')}</span>
          <textarea
            class="field font-mono text-sm mt-1"
            rows="3"
            placeholder={"e.g. Terima kasih!\nIG: @kopi.senja"}
            bind:value={receiptFooter}
          ></textarea>
          {#if receiptFooter.trim()}
            <div class="mt-2 space-y-0.5">
              {#each footerLines as len, i}
                <div class="flex items-center gap-2 text-xs">
                  <span class="w-14 text-[var(--text-muted)]">Line {i + 1}:</span>
                  <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--cream)]">
                    <div
                      class="h-full rounded-full transition-all {len > THERMAL_WIDTH ? 'bg-red-400' : 'bg-green-400'}"
                      style="width: {Math.min(100, (len / THERMAL_WIDTH) * 100)}%"
                    ></div>
                  </div>
                  <span class="{len > THERMAL_WIDTH ? 'text-red-500 font-bold' : 'text-[var(--text-muted)]'}">{len}/{THERMAL_WIDTH}</span>
                </div>
              {/each}
              {#if footerOverflow}
                <p class="text-xs font-semibold text-red-500">Lines over 32 chars may wrap on 58mm paper.</p>
              {/if}
            </div>
          {/if}
        </div>

      </div>
    </div>

    <!-- ── POS ─────────────────────────────────────────────── -->
    <div class="mb-8">
      <p class="section-label">POS</p>
      <div class="card p-5 space-y-3">

        <label class="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-[var(--border)] p-3">
          <div class="text-sm font-semibold text-[var(--espresso)]">{language.t('serviceOptionTitle')}</div>
          <Toggle bind:checked={posDineIn} />
        </label>

        <div class="rounded-xl border border-[var(--border)] p-3">
          <label class="flex cursor-pointer items-center justify-between gap-3">
            <div class="text-sm font-semibold text-[var(--espresso)]">{language.t('tableNumber')}</div>
            <Toggle bind:checked={posTable} />
          </label>
          {#if posTable}
            <div class="mt-3">
              <label class="block">
                <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('tableCount')}</span>
                <input class="field w-28" type="number" min="1" max="200" bind:value={posTableCount} />
              </label>
            </div>
          {/if}
        </div>

        <label class="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-[var(--border)] p-3">
          <div class="text-sm font-semibold text-[var(--espresso)]">{language.t('customerName')}</div>
          <Toggle bind:checked={posCustomerName} />
        </label>

      </div>
    </div>

    <!-- ── Kitchen ─────────────────────────────────────────── -->
    <div class="mb-8">
      <p class="section-label">{language.t('kitchen')}</p>
      <div class="card p-5">
        <label class="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-[var(--border)] p-3">
          <div>
            <div class="text-sm font-semibold text-[var(--espresso)]">{language.t('kitchenManagement')}</div>
            <div class="text-xs text-[var(--text-muted)]">{language.t('kitchenManagementDesc')}</div>
          </div>
          <Toggle bind:checked={kitchenEnabled} />
        </label>
      </div>
    </div>

    <!-- ── Online platforms (Owner) ────────────────────────── -->
    {#if isOwner && channelForms.length}
      <div class="mb-8">
        <p class="section-label">{language.t('channelsSettings')}</p>
        <div class="card space-y-3 p-5">
          <p class="text-xs text-[var(--text-muted)]">{language.t('channelsSettingsDesc')}</p>
          {#each channelForms as c (c.channel)}
            <div class="rounded-xl border border-[var(--border)] p-3">
              <label class="flex cursor-pointer items-center justify-between gap-3">
                <span class="text-sm font-semibold text-[var(--espresso)]">{CHANNEL_NAMES[c.channel]}</span>
                <Toggle bind:checked={c.enabled} />
              </label>
              {#if c.enabled}
                <div class="mt-3 grid grid-cols-2 gap-3">
                  <label class="block">
                    <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('channelCommission')}</span>
                    <input class="field" inputmode="decimal" placeholder="0" bind:value={c.commission} />
                  </label>
                  <label class="block">
                    <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('channelMarkup')}</span>
                    <input class="field" inputmode="decimal" placeholder="0" bind:value={c.markup} />
                  </label>
                  <label class="col-span-2 block">
                    <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('channelPayoutLag')}</span>
                    <input class="field" inputmode="numeric" placeholder="2" bind:value={c.lag} />
                  </label>
                </div>
              {/if}
            </div>
          {/each}
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('taxRate')}</span>
            <input class="field max-w-[10rem]" inputmode="decimal" placeholder="0" bind:value={taxPct} />
            <span class="mt-1 block text-xs text-[var(--text-muted)]">{language.t('taxRateDesc')}</span>
          </label>
        </div>
      </div>
    {/if}

    <!-- ── Service charge & PB1 (Owner) ────────────────────── -->
    {#if isOwner}
      <div class="mb-8">
        <p class="section-label">{language.t('serviceLabel')} & {language.t('pb1Label')}</p>
        <div class="card grid gap-3 p-5 sm:grid-cols-2">
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('settingsServicePct')}</span>
            <input class="field" inputmode="decimal" placeholder="0" bind:value={servicePct} />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('settingsPb1Pct')}</span>
            <input class="field" inputmode="decimal" placeholder="0" bind:value={pb1Pct} />
          </label>
          <p class="text-xs text-[var(--text-muted)] sm:col-span-2">{language.t('settingsFeesHint')}</p>
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

    <!-- ── Branches (Owner) ────────────────────────────────── -->
    {#if isOwner}
      <div class="mb-8">
        <p class="section-label">{language.t('branches')}</p>
        <div class="card space-y-3 p-5">
          <p class="text-xs text-[var(--text-muted)]">{language.t('branchesDesc')}</p>
          <ul class="divide-y divide-[var(--border)]">
            {#each session.stores as st (st.id)}
              <li class="flex items-center gap-2 py-2 text-sm font-semibold"><span class="ms !text-[20px] text-[var(--om-brand)]">storefront</span>{st.name}</li>
            {/each}
          </ul>
          {#if branchError}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{branchError}</div>{/if}
          <div class="flex gap-2">
            <input class="field min-w-0 flex-1" placeholder={language.t('branchName')} bind:value={branchName} onkeydown={(e) => { if (e.key === 'Enter') addBranch(); }} />
            <button type="button" class="btn-primary shrink-0" disabled={addingBranch || !branchName.trim()} onclick={addBranch}>{language.t('addBranch')}</button>
          </div>
        </div>
      </div>
    {/if}

    <!-- ── Save ────────────────────────────────────────────── -->
    {#if saveError}
      <div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{saveError}</div>
    {/if}
    {#if saveSuccess}
      <div class="mb-4 rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">{saveSuccess}</div>
    {/if}
    <button class="btn-primary w-full" onclick={save} disabled={saving}>
      {saving ? language.t('saving') : language.t('saveChanges')}
    </button>

  </div>

  <!-- ── Preview column ────────────────────────────────────── -->
  <div class="preview-col">
    <div class="preview-sticky">
      <p class="mb-3 text-[11px] font-bold uppercase tracking-widest text-[var(--text-muted)]">{language.t('livePreview')}</p>

      <div class="receipt-preview">
        <!-- Logo -->
        {#if showLogo && displayLogoUrl}
          <img src={displayLogoUrl} alt="logo" class="preview-logo" />
        {/if}

        <!-- Store name + order meta -->
        <div class="preview-store">{storeName || language.t('storeName')}</div>
        <div class="preview-meta">19 May 2026 · 10:30</div>
        <div class="preview-meta">#0001</div>

        <!-- POS info block — shown only when a POS option is enabled -->
        {#if posCustomerName || posDineIn || posTable}
          <div class="preview-pos-block">
            {#if posCustomerName}
              <div class="preview-pos-row">
                <span>{language.t('customerName')}</span>
                <span>{SAMPLE_CUSTOMER}</span>
              </div>
            {/if}
            {#if posDineIn}
              <div class="preview-pos-row">
                <span>{language.t('serviceOption')}</span>
                <span>{language.t('dineIn')}</span>
              </div>
            {/if}
            {#if posTable}
              <div class="preview-pos-row">
                <span>{language.t('table')}</span>
                <span>{SAMPLE_TABLE}</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Receipt header text -->
        {#if receiptHeader.trim()}
          <div class="preview-header-text">{receiptHeader}</div>
        {/if}

        <div class="preview-sep">— — — — — — — — — — — —</div>

        <!-- Items -->
        {#each SAMPLE_ITEMS as item}
          <div class="preview-item-row">
            <span>{item.name} ×{item.qty}</span>
            <span>{formatRupiah(item.price * item.qty)}</span>
          </div>
        {/each}

        <div class="preview-sep">— — — — — — — — — — — —</div>

        <!-- Totals -->
        <div class="preview-total-row preview-grand">
          <span>Total</span>
          <span>{formatRupiah(SAMPLE_ITEMS.reduce((s, i) => s + i.price * i.qty, 0))}</span>
        </div>
        <div class="preview-total-row">
          <span>{language.t('payment')}</span>
          <span class="font-bold">CASH</span>
        </div>

        <div class="preview-sep">— — — — — — — — — — — —</div>

        <!-- Footer -->
        {#if receiptFooter.trim()}
          <div class="preview-footer-text">{receiptFooter}</div>
        {:else}
          <div class="preview-thanks">Terima kasih! ☕</div>
        {/if}
      </div>
    </div>
  </div>
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

  .form-col { min-width: 0; }
  .preview-col { min-width: 0; }

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
  .receipt-preview {
    width: 100%;
    max-width: 280px;
    margin: 0 auto;
    background: white;
    border-radius: 16px;
    border: 1.5px solid var(--border);
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 20px 16px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 12px;
    color: #1a1a1a;
    line-height: 1.5;
  }

  .preview-logo {
    display: block;
    max-height: 52px;
    max-width: 120px;
    object-fit: contain;
    margin: 0 auto 10px;
  }

  .preview-store {
    text-align: center;
    font-weight: 800;
    font-size: 13px;
    color: var(--espresso);
    margin-bottom: 2px;
  }

  .preview-meta {
    text-align: center;
    color: #888;
    font-size: 11px;
  }

  .preview-pos-block {
    margin: 7px 0 2px;
    padding: 5px 0;
    border-top: 1px dashed #ddd;
    border-bottom: 1px dashed #ddd;
  }

  .preview-pos-row {
    display: flex;
    justify-content: space-between;
    font-size: 10.5px;
    color: #555;
    padding: 1.5px 0;
  }

  .preview-header-text {
    text-align: center;
    margin-top: 8px;
    font-size: 11px;
    color: #555;
    white-space: pre-line;
  }

  .preview-sep {
    text-align: center;
    color: #ccc;
    margin: 8px 0;
    font-size: 11px;
    letter-spacing: 0.05em;
  }

  .preview-item-row {
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    padding: 1px 0;
  }

  .preview-total-row {
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    color: #555;
    padding: 1px 0;
  }

  .preview-grand {
    font-weight: 800;
    font-size: 13px;
    color: var(--espresso);
    padding: 4px 0;
  }

  .preview-footer-text {
    text-align: center;
    font-size: 11px;
    color: #555;
    white-space: pre-line;
    margin-top: 4px;
  }

  .preview-thanks {
    text-align: center;
    font-size: 11px;
    color: #888;
    margin-top: 4px;
  }
</style>
