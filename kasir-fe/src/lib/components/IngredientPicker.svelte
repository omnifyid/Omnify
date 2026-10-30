<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Ingredient, PaginatedResponse } from '$lib/api/types';
  import { session } from '$lib/stores/session.svelte';

  // Search-as-you-type ingredient picker; loads one small page per keystroke burst.
  let {
    placeholder,
    emptyText = '',
    exclude = [],
    onPick
  }: { placeholder: string; emptyText?: string; exclude?: string[]; onPick: (ingredient: Ingredient) => void } = $props();

  let query = $state('');
  let results = $state<Ingredient[]>([]);
  let open = $state(false);
  let searched = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function search() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      const q = new URLSearchParams({ limit: '8' });
      if (query.trim()) q.set('search', query.trim());
      results = paginatedItems(await api.get<PaginatedResponse<Ingredient>>(`/stores/${storeId}/ingredients?${q}`));
    } catch {
      results = [];
    } finally {
      searched = true;
    }
  }

  $effect(() => {
    void query;
    if (!open) return;
    untrack(() => {
      clearTimeout(timer);
      timer = setTimeout(() => void search(), 300);
    });
  });

  let shown = $derived(results.filter((i) => !exclude.includes(i.id)));

  function pick(i: Ingredient) {
    onPick(i);
    query = '';
    open = false;
  }
</script>

<div class="relative">
  <input class="field py-2 text-sm" {placeholder} autocomplete="off" bind:value={query} onfocus={() => { open = true; }} onblur={() => setTimeout(() => (open = false), 150)} />
  {#if open && (shown.length || (searched && !query.trim() && emptyText))}
    <div class="absolute left-0 right-0 top-full z-10 mt-1 max-h-56 overflow-y-auto rounded-xl border border-[var(--border)] bg-white shadow-lg">
      {#each shown as i (i.id)}
        <button type="button" class="block w-full px-3 py-2 text-left text-sm hover:bg-[var(--cream)]" onmousedown={(e) => { e.preventDefault(); pick(i); }}>{i.name} <span class="text-xs text-[var(--text-muted)]">({i.unit})</span></button>
      {:else}
        <div class="px-3 py-2 text-sm text-[var(--text-muted)]">{emptyText}</div>
      {/each}
    </div>
  {/if}
</div>
