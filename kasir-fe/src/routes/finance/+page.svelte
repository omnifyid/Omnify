<script lang="ts">
  import { goto } from '$app/navigation';
  import ExpensesPanel from '$lib/components/ExpensesPanel.svelte';
  import ShiftsPanel from '$lib/components/ShiftsPanel.svelte';
  import SettlementsPanel from '$lib/components/SettlementsPanel.svelte';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { seg, SEG_GROUP } from '$lib/utils/ui';

  let tab = $state<'shift' | 'expenses' | 'settle'>('shift');
  const tabs = [
    { id: 'shift', key: 'finTabShift' },
    { id: 'expenses', key: 'finTabExpenses' },
    { id: 'settle', key: 'finTabSettle' }
  ] as const;

  // module switched off in Settings: leave the page
  $effect(() => {
    if (session.selectedStore?.finance_enabled === false) void goto('/dashboard');
  });
</script>

<svelte:head><title>{language.t('finance')} | Omnify</title></svelte:head>

<div class="mb-4 inline-flex {SEG_GROUP}" role="tablist">
  {#each tabs as t (t.id)}
    <button role="tab" aria-selected={tab === t.id} class={seg(tab === t.id)} style="height: var(--om-tap)" onclick={() => (tab = t.id)}>{language.t(t.key)}</button>
  {/each}
</div>

{#if tab === 'shift'}
  <ShiftsPanel />
{:else if tab === 'expenses'}
  <ExpensesPanel />
{:else}
  <SettlementsPanel />
{/if}
