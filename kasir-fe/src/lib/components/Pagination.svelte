<script lang="ts">
  import { language } from '$lib/i18n/language.svelte';
  import { pageCount, PAGE_SIZE } from '$lib/utils/paging';

  let {
    page,
    total,
    limit = PAGE_SIZE,
    loading = false,
    onPage
  }: { page: number; total: number; limit?: number; loading?: boolean; onPage: (page: number) => void } = $props();

  let pages = $derived(pageCount(total, limit));
  let current = $derived(Math.min(page, pages));
</script>

{#if pages > 1}
  <div class="mt-4 flex items-center justify-between gap-3 text-sm">
    <span class="text-[var(--text-muted)]">{language.t('page')} {current} {language.t('of')} {pages} · {total}</span>
    <div class="flex gap-2">
      <button class="btn-outline px-3 py-2 text-sm" disabled={current === 1 || loading} onclick={() => onPage(current - 1)}>{language.t('previous')}</button>
      <button class="btn-outline px-3 py-2 text-sm" disabled={current === pages || loading} onclick={() => onPage(current + 1)}>{language.t('next')}</button>
    </div>
  </div>
{/if}
