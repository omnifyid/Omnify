<script lang="ts">
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';

  let { variant = 'card', onpick }: { variant?: 'card' | 'chip'; onpick?: () => void } = $props();

  let open = $state(false);
  let canSwitch = $derived(session.stores.length > 1);
  let current = $derived(session.selectedStore);

  function pick(id: string) {
    session.selectedStoreId = id;
    open = false;
    onpick?.();
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }
</script>

<svelte:window {onkeydown} />

<div class="relative {variant === 'card' ? 'mb-4' : 'shrink-0'}">
  {#if variant === 'card'}
    <button
      type="button"
      class="flex w-full items-center gap-2.5 rounded-xl border border-[var(--om-border)] bg-white p-2.5 text-left transition-colors {canSwitch ? 'cursor-pointer hover:border-[var(--om-ink)]' : 'cursor-default'}"
      title={canSwitch ? language.t('store') : undefined}
      aria-haspopup={canSwitch ? 'listbox' : undefined}
      aria-expanded={canSwitch ? open : undefined}
      onclick={() => { if (canSwitch) open = !open; }}
    >
      <div class="logo-font flex h-[30px] w-[30px] shrink-0 items-center justify-center gap-0.5 rounded-lg bg-[var(--om-ink)] text-[12px] text-[var(--om-brand-on-dark)]">
        <span>&gt;</span><span class="h-[13px] w-1.5 bg-[var(--om-brand-on-dark)]"></span>
      </div>
      <div class="min-w-0 flex-1">
        <div class="truncate text-[12px] font-semibold">{current?.name ?? language.t('noStoreSelected')}</div>
        <div class="truncate text-[12px] text-[var(--om-text-secondary)]">{current?.role ?? ''}</div>
      </div>
      {#if canSwitch}<span class="ms !text-[20px] text-[var(--om-text-secondary)]">unfold_more</span>{/if}
    </button>
  {:else if canSwitch}
    <button
      type="button"
      class="flex max-w-[190px] items-center gap-1.5 rounded-[10px] border border-[var(--om-border)] bg-white px-3 font-semibold"
      style="min-height: var(--om-tap)"
      aria-haspopup="listbox"
      aria-expanded={open}
      onclick={() => (open = !open)}
    >
      <span class="ms !text-[20px] text-[var(--om-brand)]">storefront</span>
      <span class="truncate text-[14px]">{current?.name}</span>
      <span class="ms !text-[20px] text-[var(--om-text-secondary)]">unfold_more</span>
    </button>
  {/if}

  {#if open && canSwitch}
    <div class="fixed inset-0 z-40" role="presentation" onclick={() => (open = false)}></div>
    <div
      role="listbox"
      aria-label={language.t('pickStore')}
      class="absolute z-50 flex w-[370px] max-w-[calc(100vw-24px)] flex-col gap-0.5 overflow-hidden rounded-[14px] border border-[var(--om-border)] bg-white p-1.5 shadow-[var(--om-sh-popover)] {variant === 'chip' ? 'right-0 top-full mt-1.5' : 'left-full top-0 ml-3'}"
      style="animation: omUp .2s ease"
    >
      <div class="px-3 pb-1.5 pt-2.5 text-[12px] text-[var(--om-text-secondary)]">{language.t('pickStore')}</div>
      {#each session.stores as store}
        {@const active = store.id === current?.id}
        <button
          type="button"
          role="option"
          aria-selected={active}
          class="flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--om-bg)] {active ? 'bg-[var(--om-fill-muted)]' : 'bg-white'}"
          style="min-height: var(--om-tap)"
          onclick={() => pick(store.id)}
        >
          <span class="ms !text-[20px] text-[var(--om-brand)]">storefront</span>
          <span class="flex min-w-0 flex-1 flex-col gap-0.5">
            <span class="truncate text-[16px] font-semibold">{store.name}</span>
            <span class="truncate text-[12px] text-[var(--om-text-secondary)]">{store.description || store.role}</span>
          </span>
          {#if active}<span class="ms !text-[20px] text-[var(--om-brand)]">check</span>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>
