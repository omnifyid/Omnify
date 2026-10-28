<script lang="ts">
  import { page } from '$app/stores';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import StoreSwitcher from './StoreSwitcher.svelte';
  import { visibleGroups } from './navState.svelte';

  let { open = $bindable(false), modal = false } = $props();

  let groups = $derived(visibleGroups());
  let logoutConfirm = $state(false);
  // tablet rail: expands to full width on tap
  let expanded = $state(false);
  let desktop = $state(true);
  let showFull = $derived(modal || desktop || expanded);

  $effect(() => {
    const mq = window.matchMedia('(min-width: 1200px)');
    const sync = () => { desktop = mq.matches; if (desktop) expanded = false; };
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  });

  function close() { open = false; expanded = false; }
  function isActive(href: string) {
    const p = $page.url.pathname;
    return p === href || p.startsWith(href + '/');
  }
</script>

{#snippet navBody(full: boolean)}
  <a href="/dashboard" class="logo-font mb-5 flex items-center px-2 text-2xl text-[var(--om-ink)] {full ? '' : 'justify-center'}" onclick={close}>
    {#if full}
      <span>&gt;omnify</span><span class="om-cursor ml-0.5 inline-block h-5 w-2.5 bg-[var(--om-brand-bright)]"></span>
    {:else}
      <span class="text-[var(--om-brand-bright)]">&gt;</span><span class="om-cursor inline-block h-5 w-2 bg-[var(--om-brand-bright)]"></span>
    {/if}
  </a>

  {#if full}
    <StoreSwitcher onpick={close} />
  {/if}

  <nav class="min-h-0 flex-1 overflow-y-auto">
    {#each groups as group, gi}
      {#if full}
        <div class="mb-1 mt-3 px-2.5 text-xs text-[var(--om-text-secondary)]">{language.t(group.labelKey)}</div>
      {:else if gi > 0}
        <div class="my-2 border-t border-[var(--om-border)]"></div>
      {/if}
      {#each group.items as item}
        {@const active = isActive(item.href)}
        <a
          href={item.href}
          title={language.t(item.labelKey)}
          class="mb-0.5 flex items-center gap-[11px] rounded-[10px] px-2.5 py-[9px] transition-colors
                 {full ? '' : 'justify-center'}
                 {active ? 'bg-[var(--om-brand-tint)] font-semibold text-[var(--om-ink)] hover:bg-[var(--om-brand-tint-hover)]' : 'font-medium text-[var(--om-ink-2)] hover:bg-[var(--om-fill-hover)]'}"
          style="min-height: var(--om-tap)"
          aria-current={active ? 'page' : undefined}
          onclick={close}
        >
          <span class="ms {active ? 'fill text-[var(--om-brand)]' : 'text-[var(--om-text-secondary)]'}">{item.icon}</span>
          {#if full}<span class="text-[14px]">{language.t(item.labelKey)}</span>{/if}
        </a>
      {/each}
    {/each}
  </nav>

  <div class="mt-2 border-t border-[var(--om-border)] pt-2">
    <button
      class="flex w-full items-center gap-[11px] rounded-[10px] px-2.5 py-[9px] font-medium text-[var(--om-ink-2)] transition-colors hover:bg-[var(--om-fill-hover)] {full ? '' : 'justify-center'}"
      style="min-height: var(--om-tap)"
      title={language.t('logout')}
      onclick={() => (logoutConfirm = true)}
    >
      <span class="ms text-[var(--om-text-secondary)]">logout</span>
      {#if full}<span class="text-[14px]">{language.t('logout')}</span>{/if}
    </button>
  </div>
{/snippet}

{#if modal}
  {#if open}
    <div class="fixed inset-0 z-30 bg-[var(--om-scrim)]" role="presentation" onclick={close}></div>
  {/if}
  <aside
    class="fixed inset-y-0 left-0 z-40 flex w-[244px] flex-col border-r border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-3 py-5 transition-transform duration-200 {open ? 'translate-x-0 shadow-[var(--om-sh-popover)]' : '-translate-x-full'}"
  >
    {@render navBody(true)}
  </aside>
{:else}
  <!-- placeholder keeps layout width; aside overlays when the rail expands -->
  <div class="hidden shrink-0 md:block md:w-[var(--om-rail)] xl:w-[var(--om-sidebar)]"></div>
  {#if expanded}
    <div class="fixed inset-0 z-30 xl:hidden" role="presentation" onclick={close}></div>
  {/if}
  <aside
    class="fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-[var(--om-border)] bg-[var(--om-surface-sunk)] px-3 py-5 md:flex
           xl:w-[var(--om-sidebar)] {expanded ? 'w-[var(--om-sidebar)] shadow-[8px_0_28px_rgba(16,20,15,.12)]' : 'w-[var(--om-rail)]'}"
    style="transition: width .32s cubic-bezier(.2,.8,.2,1)"
  >
    <div
      class="flex min-h-0 flex-1 flex-col"
      role="presentation"
      onclick={(e) => { if (!showFull && !(e.target as HTMLElement).closest('a,button')) expanded = true; }}
    >
      {@render navBody(showFull)}
    </div>
  </aside>
{/if}

{#if logoutConfirm}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4">
    <section class="w-full max-w-sm overflow-hidden rounded-[18px] bg-white shadow-[var(--om-sh-dialog)]" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-[var(--om-danger-tint)]">
          <span class="ms text-[var(--om-danger)]">logout</span>
        </div>
        <h2 class="text-xl font-semibold">{language.t('logout')}</h2>
        <p class="mt-2 text-sm text-[var(--om-text-secondary)]">{language.t('logoutConfirm')}</p>
      </div>
      <div class="flex gap-3 border-t border-[var(--om-border)] p-4">
        <button class="btn-outline flex-1" onclick={() => (logoutConfirm = false)}>{language.t('cancel')}</button>
        <button
          class="flex-1 rounded-[10px] bg-[var(--om-danger)] px-4 py-2.5 font-semibold text-white transition hover:opacity-90"
          onclick={() => { logoutConfirm = false; close(); auth.logout(); }}
        >{language.t('logout')}</button>
      </div>
    </section>
  </div>
{/if}

<style>
  .om-cursor { animation: omBlink 1.1s steps(1) infinite; }
</style>
