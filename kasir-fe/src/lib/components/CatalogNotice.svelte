<script lang="ts">
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';

  let store = $derived(session.selectedStore);
</script>

{#if store?.has_branches}
  <div class="mb-4 flex items-start gap-2 rounded-[12px] bg-[var(--om-brand-tint)] p-3 text-[14px]" role="note">
    <span class="ms !text-[20px] text-[var(--om-brand)]">{store.is_parent ? 'hub' : 'link'}</span>
    <span>
      {#if store.is_parent}
        <strong>{language.t('parentStore')}.</strong> {language.t('catalogParentNotice')}
      {:else}
        <strong>{language.t('catalogBranchTitle')} {store.parent_store_name}.</strong> {language.t('catalogBranchNotice')}
      {/if}
    </span>
  </div>
{/if}
