<script lang="ts">
  import { page } from '$app/stores';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { session } from '$lib/stores/session.svelte';
  import ShiftChip from './ShiftChip.svelte';
  import StoreSwitcher from './StoreSwitcher.svelte';
  import { navGroups, adminGroup } from './nav';

  let now = $state(new Date());
  $effect(() => {
    const t = setInterval(() => (now = new Date()), 30_000);
    return () => clearInterval(t);
  });

  let navItem = $derived.by(() => {
    const p = $page.url.pathname;
    return [...navGroups, adminGroup].flatMap((g) => g.items).find((i) => p === i.href || p.startsWith(i.href + '/'));
  });
  let title = $derived(navItem ? language.t(navItem.labelKey) : '');
  let subtitle = $derived(navItem?.subtitleKey ? language.t(navItem.subtitleKey) : '');
  let dateLabel = $derived(now.toLocaleDateString('id-ID', { weekday: 'short', day: 'numeric', month: 'short' }));
  let timeLabel = $derived(now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', hour12: false }).replace('.', ':'));
  let roleLabel = $derived((session.selectedStore?.role ?? '').toLowerCase());
  let initial = $derived((auth.user?.full_name ?? auth.user?.email ?? '?').charAt(0).toUpperCase());
</script>

<header
  class="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--om-border)] bg-[var(--om-bg)] px-3 md:px-6"
  style="min-height: 64px"
>
  <div class="min-w-0">
    <h1 class="truncate text-xl font-semibold tracking-[-0.01em]">{title}</h1>
    {#if subtitle}
      <div class="truncate text-[12px] text-[var(--om-text-secondary)]">{subtitle}</div>
    {:else}
      <div class="truncate text-xs text-[var(--om-text-secondary)] md:hidden">{session.selectedStore?.name ?? ''}</div>
    {/if}
  </div>

  <div class="flex items-center gap-2">
    <div class="hidden items-center gap-2 whitespace-nowrap rounded-[10px] border border-[var(--om-border)] bg-white px-[14px] text-[14px] font-semibold sm:flex" style="min-height: var(--om-tap)">
      <span class="h-2 w-2 rounded-full bg-[var(--om-brand-bright)]"></span>
      <span>{dateLabel}</span><span class="text-[var(--om-text-secondary)]">·</span><span>{timeLabel}</span>
    </div>

    {#if session.selectedStore?.finance_enabled !== false}<ShiftChip />{/if}

    <div class="xl:hidden"><StoreSwitcher variant="chip" /></div>

    <div class="flex items-center gap-3 rounded-full border border-[var(--om-border)] bg-white py-1 pl-1 pr-4" style="min-height: var(--om-tap)">
      <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--om-brand-tint)] text-[16px] font-semibold text-[var(--om-brand)]">{initial}</span>
      <span class="hidden min-w-0 leading-tight sm:block">
        <span class="block text-[12px] capitalize text-[var(--om-text-secondary)]">{roleLabel}</span>
        <span class="block max-w-40 truncate text-[16px] font-semibold">{auth.user?.full_name ?? auth.user?.email ?? ''}</span>
      </span>
    </div>
  </div>
</header>
