<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { Item, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';

  // Search-as-you-type product picker: only the matching page of products is ever loaded.
  let {
    id,
    value = $bindable(''),
    name = $bindable(''),
    placeholder = ''
  }: { id?: string; value: string; name: string; placeholder?: string } = $props();

  let query = $state('');
  let results = $state<Item[]>([]);
  let open = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function search() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      const q = new URLSearchParams({ limit: '8', include_groups: 'false' });
      if (query.trim()) q.set('search', query.trim());
      results = paginatedItems(await api.get<PaginatedResponse<Item>>(`/stores/${storeId}/items?${q}`));
    } catch {
      results = [];
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

  function pick(item: Item) {
    value = item.id;
    name = item.name;
    query = '';
    open = false;
  }
</script>

{#if value}
  <div class="field flex items-center justify-between gap-2">
    <span class="truncate">{name || '—'}</span>
    <button type="button" class="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[var(--text-muted)] hover:bg-[var(--cream)]" aria-label={language.t('close')} onclick={() => { value = ''; name = ''; }}><span class="ms !text-[14px]" aria-hidden="true">close</span></button>
  </div>
{:else}
  <div class="relative">
    <input {id} class="field" placeholder={placeholder || language.t('selectItem')} autocomplete="off" bind:value={query} onfocus={() => { open = true; }} onblur={() => setTimeout(() => (open = false), 150)} />
    {#if open && results.length}
      <div class="absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-y-auto rounded-xl border border-[var(--border)] bg-white shadow-lg">
        {#each results as item (item.id)}
          <button type="button" class="block w-full px-3 py-2.5 text-left text-sm hover:bg-[var(--cream)]" onmousedown={(e) => { e.preventDefault(); pick(item); }}>{item.name}</button>
        {/each}
      </div>
    {/if}
  </div>
{/if}
