<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import QRCode from 'qrcode';
  import { api } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { ExternalLink, Printer, RefreshCw } from 'lucide-svelte';

  let tableCount = $derived(session.selectedStore?.pos_table_count ?? 10);
  let tablePrefix = $state('Meja');
  let qrDataUrls = $state<string[]>([]);
  let generating = $state(false);
  let printTarget = $state<number | null>(null);
  let toggling = $state(false);

  let storeId = $derived(session.selectedStore?.id ?? null);
  let selfOrderEnabled = $derived(session.selectedStore?.self_order_enabled ?? false);
  let selforderIsOpen = $derived(session.selectedStore?.selforder_is_open ?? true);
  let isOwner = $derived(session.selectedStore?.role === 'OWNER');

  async function toggleSelforder() {
    if (!storeId || toggling) return;
    toggling = true;
    try {
      await api.patch(`/stores/${storeId}/selforder`, { is_open: !selforderIsOpen });
      await session.loadStores();
    } finally {
      toggling = false;
    }
  }

  function storageKey() {
    return `selforder_settings_${storeId}`;
  }

  function loadSettings() {
    if (!browser || !storeId) return;
    const saved = localStorage.getItem(storageKey());
    if (saved) {
      try {
        const { tablePrefix: tp } = JSON.parse(saved);
        if (tp) tablePrefix = tp;
      } catch {
        // ignore corrupt storage
      }
    }
  }

  function selfOrderUrl(tableNum: number) {
    const origin = browser ? window.location.origin : '';
    return `${origin}/order/${storeId}?table=${tableNum}`;
  }

  async function generate() {
    if (!storeId) return;
    generating = true;
    if (browser) {
      localStorage.setItem(storageKey(), JSON.stringify({ tablePrefix }));
    }
    const urls: string[] = [];
    const cs = getComputedStyle(document.documentElement);
    const qrDark = cs.getPropertyValue('--espresso').trim() || '#10140F';
    const qrLight = cs.getPropertyValue('--white').trim() || '#FFFFFF';
    for (let i = 1; i <= tableCount; i++) {
      const dataUrl = await QRCode.toDataURL(selfOrderUrl(i), {
        width: 240,
        margin: 2,
        color: { dark: qrDark, light: qrLight },
      });
      urls.push(dataUrl);
    }
    qrDataUrls = urls;
    generating = false;
  }

  function openSelfOrder(tableNum: number) {
    if (browser) window.open(selfOrderUrl(tableNum), '_blank');
  }

  function printSingle(index: number) {
    printTarget = index;
    if (browser) {
      requestAnimationFrame(() => {
        window.print();
        printTarget = null;
      });
    }
  }

  function printAll() {
    printTarget = null;
    if (browser) window.print();
  }

  onMount(() => {
    loadSettings();
    if (storeId) generate();
  });
</script>

{#if !selfOrderEnabled}
  <div class="mb-6">
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('selfOrderQr')}</h1>
    <p class="mt-2 text-[var(--text-muted)]">{language.t('qrSelfOrderDisabled')}</p>
  </div>
{:else}
<div class="print-area" class:has-print-target={printTarget !== null}>
  <!-- Page header (hidden when printing) -->
  <div class="no-print mb-6 flex items-center justify-between gap-4">
    <div>
      <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('selfOrderQr')}</h1>
      <p class="text-[var(--text-muted)]">{language.t('qrSubtitle')}</p>
    </div>
    {#if qrDataUrls.length > 0}
      <button class="btn-primary no-print flex-shrink-0 flex items-center gap-2" onclick={printAll}>
        <Printer class="h-4 w-4" />
        {language.t('printAll')}
      </button>
    {/if}
  </div>

  <!-- Owner-only status toggle -->
  {#if isOwner}
    <div class="no-print mb-6 flex items-center justify-between gap-4 rounded-2xl border px-5 py-4
                {selforderIsOpen
                  ? 'border-green-200 bg-green-50'
                  : 'border-amber-200 bg-amber-50'}">
      <div>
        <div class="font-bold {selforderIsOpen ? 'text-green-800' : 'text-amber-800'}">
          {selforderIsOpen ? language.t('selfOrderActive') : language.t('selfOrderPaused')}
        </div>
        <div class="text-sm {selforderIsOpen ? 'text-green-700' : 'text-amber-700'}">
          {selforderIsOpen
            ? language.t('selfOrderCustomersCanOrder')
            : language.t('selfOrderCustomersCannotOrder')}
        </div>
      </div>
      <button
        class="{selforderIsOpen ? 'btn-outline' : 'btn-primary'} flex-shrink-0 disabled:opacity-50"
        disabled={toggling}
        onclick={toggleSelforder}
      >
        {toggling ? language.t('saving') : selforderIsOpen ? language.t('selfOrderPaused') : language.t('selfOrderActive')}
      </button>
    </div>
  {/if}

  <!-- Settings card (hidden when printing) -->
  <div class="card no-print mb-6 p-5">
    <div class="flex flex-wrap items-end gap-4">
      <label class="block">
        <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('tableLabel')}</span>
        <input
          class="field w-36"
          type="text"
          placeholder={language.t('table')}
          bind:value={tablePrefix}
        />
      </label>
      <div class="block">
        <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('tableCount')}</span>
        <div class="flex h-[2.6rem] items-center rounded-[0.85rem] border-1.5 border-[var(--border)] bg-[var(--cream)] px-[0.9rem] text-sm font-bold text-[var(--espresso)]">
          {tableCount}
        </div>
      </div>
      <button
        class="btn-primary flex items-center gap-2 disabled:opacity-50"
        disabled={generating || !storeId}
        onclick={generate}
      >
        <RefreshCw class="h-4 w-4 {generating ? 'animate-spin' : ''}" />
        {generating ? language.t('generating') : language.t('generate')}
      </button>
    </div>
    <p class="mt-3 text-xs text-[var(--text-muted)]">{language.t('tableCount')} <a href="/settings" class="font-bold text-[var(--warm-brown)] hover:underline">{language.t('settings')}</a>.</p>
  </div>

  <!-- QR grid -->
  {#if generating && qrDataUrls.length === 0}
    <div class="py-16 text-center text-[var(--text-muted)]">{language.t('generatingQrCodes')}</div>
  {:else if qrDataUrls.length > 0}
    <div class="qr-grid">
      {#each qrDataUrls as dataUrl, i}
        <div
          class="qr-card card flex flex-col items-center gap-3 p-5"
          class:print-target={printTarget === i}
        >
          <img src={dataUrl} alt="{tablePrefix} {i + 1}" class="h-48 w-48 rounded-xl" />
          <div class="display-font text-xl font-bold text-[var(--espresso)]">{tablePrefix} {i + 1}</div>
          <div class="no-print flex w-full gap-2">
            <button
              class="btn-outline flex flex-1 items-center justify-center gap-1.5 text-sm"
              onclick={() => openSelfOrder(i + 1)}
            >
              <ExternalLink class="h-3.5 w-3.5" />
              {language.t('open')}
            </button>
            <button
              class="btn-outline flex flex-1 items-center justify-center gap-1.5 text-sm"
              onclick={() => printSingle(i)}
            >
              <Printer class="h-3.5 w-3.5" />
              {language.t('print')}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {:else if !storeId}
    <div class="py-16 text-center text-[var(--text-muted)]">{language.t('noStoreSelected')}</div>
  {/if}
</div>
{/if}

<style>
  .qr-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
    gap: 1rem;
  }

  @media print {
    :global(body) {
      background: white !important;
    }

    /* Hide everything outside our print area */
    :global(*) {
      visibility: hidden;
    }
    .print-area {
      visibility: visible;
      position: fixed;
      inset: 0;
      padding: 1rem;
    }
    .print-area * {
      visibility: visible;
    }

    /* When printing a single card, hide the rest */
    .has-print-target .qr-card:not(.print-target) {
      display: none !important;
    }

    /* Always hide UI-only elements */
    .no-print {
      display: none !important;
    }

    .qr-grid {
      grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
    }

    .qr-card {
      break-inside: avoid;
    }
  }
</style>
