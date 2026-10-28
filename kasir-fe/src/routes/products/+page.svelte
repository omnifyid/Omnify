<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import CategoriesPanel from '$lib/components/CategoriesPanel.svelte';
  import ProductsPanel from '$lib/components/ProductsPanel.svelte';
  import { language } from '$lib/i18n/language.svelte';

  let tab = $derived($page.url.searchParams.get('tab') === 'categories' ? 'categories' : 'products');

  function setTab(next: 'products' | 'categories') {
    goto(next === 'products' ? '/products' : '/products?tab=categories', { replaceState: true, noScroll: true, keepFocus: true });
  }
</script>

<svelte:head><title>{language.t('products')} | Omnify</title></svelte:head>

{#snippet tabs()}
<div class="inline-flex rounded-[11px] bg-[var(--om-fill-muted)] p-1" role="tablist">
  {#each [['products', language.t('products')], ['categories', language.t('categories')]] as [key, label]}
    {@const active = tab === key}
    <button
      role="tab"
      aria-selected={active}
      class="rounded-[8px] px-5 text-[14px] transition-colors {active ? 'bg-[var(--om-brand-tint)] font-semibold shadow-[inset_0_0_0_2px_var(--om-brand)]' : 'font-medium text-[var(--om-ink-2)] hover:bg-[var(--om-fill-hover)]'}"
      style="min-height: calc(var(--om-tap) - 8px)"
      onclick={() => setTab(key as 'products' | 'categories')}
    >{label}</button>
  {/each}
</div>
{/snippet}

{#if tab === 'products'}
  <ProductsPanel {tabs} />
{:else}
  <CategoriesPanel {tabs} />
{/if}
