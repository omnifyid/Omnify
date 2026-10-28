<script lang="ts">
  import { page } from '$app/stores';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { visibleGroups } from './navState.svelte';

  const PRIMARY = 4;

  let all = $derived(visibleGroups().flatMap((g) => g.items));
  let primary = $derived(all.length > PRIMARY + 1 ? all.slice(0, PRIMARY) : all);
  let rest = $derived(all.length > PRIMARY + 1 ? all.slice(PRIMARY) : []);
  let moreOpen = $state(false);

  function isActive(href: string) {
    const p = $page.url.pathname;
    return p === href || p.startsWith(href + '/');
  }
  let moreActive = $derived(rest.some((i) => isActive(i.href)));
</script>

<nav
  class="grid shrink-0 border-t border-[var(--om-border)] bg-[var(--om-surface-sunk)] md:hidden"
  style="grid-template-columns: repeat({primary.length + (rest.length ? 1 : 0)}, 1fr); padding-bottom: env(safe-area-inset-bottom)"
>
  {#each primary as item}
    {@const active = isActive(item.href)}
    <a href={item.href} class="flex h-[54px] flex-col items-center justify-center gap-0.5" aria-current={active ? 'page' : undefined}>
      <span class="grid h-[30px] w-12 place-items-center rounded-full {active ? 'bg-[var(--om-brand-tint)]' : ''}">
        <span class="ms {active ? 'fill text-[var(--om-brand)]' : 'text-[var(--om-text-secondary)]'}">{item.icon}</span>
      </span>
      <span class="text-xs {active ? 'font-semibold' : ''}">{language.t(item.labelKey)}</span>
    </a>
  {/each}
  {#if rest.length}
    <button class="flex h-[54px] flex-col items-center justify-center gap-0.5" onclick={() => (moreOpen = true)} aria-haspopup="dialog">
      <span class="grid h-[30px] w-12 place-items-center rounded-full {moreActive ? 'bg-[var(--om-brand-tint)]' : ''}">
        <span class="ms {moreActive ? 'fill text-[var(--om-brand)]' : 'text-[var(--om-text-secondary)]'}">apps</span>
      </span>
      <span class="text-xs {moreActive ? 'font-semibold' : ''}">{language.t('more')}</span>
    </button>
  {/if}
</nav>

{#if moreOpen}
  <div class="fixed inset-0 z-50 flex items-end bg-[var(--om-scrim)]" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) moreOpen = false; }}>
    <section
      class="w-full rounded-t-[22px] bg-white p-4 shadow-[var(--om-sh-dialog)]"
      style="padding-bottom: calc(1rem + env(safe-area-inset-bottom)); animation: omUp .2s ease"
      role="dialog"
      aria-modal="true"
    >
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-xl font-semibold">{language.t('more')}</h2>
        <button class="btn-outline px-4 py-2" onclick={() => (moreOpen = false)}>{language.t('close')}</button>
      </div>
      <div class="grid grid-cols-3 gap-2.5">
        {#each rest as item}
          <a
            href={item.href}
            onclick={() => (moreOpen = false)}
            class="flex flex-col items-center gap-1.5 rounded-[14px] border border-[var(--om-border)] p-3 text-center text-[14px] font-medium {isActive(item.href) ? 'bg-[var(--om-brand-tint)]' : 'bg-[var(--om-surface-sunk)]'}"
          >
            <span class="ms text-[var(--om-brand)]">{item.icon}</span>
            {language.t(item.labelKey)}
          </a>
        {/each}
        <button
          class="flex flex-col items-center gap-1.5 rounded-[14px] border border-[var(--om-border)] bg-[var(--om-surface-sunk)] p-3 text-center text-[14px] font-medium"
          onclick={() => { moreOpen = false; auth.logout(); }}
        >
          <span class="ms text-[var(--om-danger)]">logout</span>
          {language.t('logout')}
        </button>
      </div>
    </section>
  </div>
{/if}
