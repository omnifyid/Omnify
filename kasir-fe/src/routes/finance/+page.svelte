<script lang="ts">
  import ExpensesPanel from '$lib/components/ExpensesPanel.svelte';
  import ShiftsPanel from '$lib/components/ShiftsPanel.svelte';
  import SettlementsPanel from '$lib/components/SettlementsPanel.svelte';
  import { language } from '$lib/i18n/language.svelte';

  let tab = $state<'shift' | 'expenses' | 'settle'>('shift');
  const tabs = [
    { id: 'shift', key: 'finTabShift' },
    { id: 'expenses', key: 'finTabExpenses' },
    { id: 'settle', key: 'finTabSettle' }
  ] as const;
</script>

<svelte:head><title>{language.t('finance')} | Omnify</title></svelte:head>

<div class="mb-4 inline-flex gap-1 rounded-[11px] bg-[#EDECE7] p-1">
  {#each tabs as t (t.id)}
    <button
      class="rounded-lg px-4 py-2 text-sm font-semibold transition {tab === t.id ? 'bg-white shadow-sm' : 'text-[var(--text-muted)]'}"
      onclick={() => (tab = t.id)}
    >{language.t(t.key)}</button>
  {/each}
</div>

{#if tab === 'shift'}
  <ShiftsPanel />
{:else if tab === 'expenses'}
  <ExpensesPanel />
{:else}
  <SettlementsPanel />
{/if}
