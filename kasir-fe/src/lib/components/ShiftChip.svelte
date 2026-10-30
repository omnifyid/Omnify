<script lang="ts">
  import { untrack } from 'svelte';
  import { ArrowDownLeft, ArrowUpRight, Lock, Wallet } from 'lucide-svelte';
  import { api } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { shiftState } from '$lib/stores/shift.svelte';
  import { CASH_IN_CATEGORIES, CASH_OUT_TRANSFERS, EXPENSE_CATEGORIES, formatDigits, parseAmount } from '$lib/utils/finance';
  import { formatRupiah } from '$lib/utils/format';

  type Mode = 'open' | 'close' | 'in' | 'out' | null;

  let mode = $state<Mode>(null);
  let menuOpen = $state(false);
  let amount = $state('');
  let category = $state('');
  let text = $state('');
  let error = $state('');
  let saving = $state(false);
  let closedCash = $state<number | null>(null);

  let cur = $derived(shiftState.current);
  let shift = $derived(cur?.shift ?? null);
  let cashLabel = $derived(cur?.cash_on_hand != null ? formatRupiah(cur.cash_on_hand) : '–');
  let sinceLabel = $derived(
    shift ? new Date(shift.opened_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', hour12: false }).replace('.', ':') : ''
  );
  let counted = $derived(parseAmount(amount));
  let variance = $derived(shift?.expected_cash != null ? counted - shift.expected_cash : 0);
  let overLimit = $derived(!!cur && Math.abs(variance) > cur.variance_threshold);
  let categories = $derived(mode === 'in' ? CASH_IN_CATEGORIES : [...CASH_OUT_TRANSFERS, ...EXPENSE_CATEGORIES]);

  $effect(() => {
    void session.selectedStore?.id;
    untrack(() => void shiftState.load());
    const t = setInterval(() => void shiftState.load(), 30_000);
    return () => clearInterval(t);
  });

  function show(next: Exclude<Mode, null>) {
    menuOpen = false;
    error = '';
    category = '';
    text = '';
    closedCash = null;
    if (next === 'open') {
      const suggest = cur?.cash_on_hand ?? cur?.default_float ?? 0;
      amount = suggest ? suggest.toLocaleString('id-ID') : '';
    } else {
      amount = '';
    }
    mode = next;
  }

  function onChip() {
    if (shift) menuOpen = !menuOpen;
    else show('open');
  }

  async function submit() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !mode) return;
    error = '';
    saving = true;
    try {
      if (mode === 'open') {
        if (amount === '') return void (error = language.t('finErrAmount'));
        await api.post(`/stores/${storeId}/shifts`, { opening_cash: counted });
        mode = null;
      } else if (mode === 'close' && shift) {
        if (amount === '') return void (error = language.t('finErrAmount'));
        if (overLimit && !text.trim()) return void (error = language.t('shiftOverMsg'));
        await api.post(`/stores/${storeId}/shifts/${shift.id}/close`, { counted, note: text.trim() || null });
        closedCash = counted;
      } else if (shift) {
        if (!category) return void (error = language.t('finErrCategory'));
        if (!text.trim()) return void (error = language.t('finErrDescription'));
        if (counted <= 0) return void (error = language.t('finErrAmount'));
        await api.post(`/stores/${storeId}/shifts/${shift.id}/cash-movements`, {
          type: mode === 'in' ? 'IN' : 'OUT',
          amount: counted,
          category,
          reason: text.trim()
        });
        mode = null;
      }
      await shiftState.load();
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  const chip = (on: boolean) =>
    `h-9 shrink-0 whitespace-nowrap rounded-full border px-3 text-sm font-medium transition ${on ? 'border-[var(--om-ink)] bg-[var(--om-ink)] text-white' : 'border-[var(--border)] bg-white text-[var(--espresso)]'}`;
  const label = 'mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]';
  const title = $derived(
    mode === 'open' ? 'shiftOpenTitle' : mode === 'close' ? 'shiftCloseTitle' : mode === 'in' ? 'shiftCashIn' : 'shiftCashOut'
  );
</script>

<div class="relative">
  <button
    class="flex items-center gap-2 whitespace-nowrap rounded-[10px] border px-[14px] text-[14px] font-semibold {shift ? 'border-[var(--om-border)] bg-white' : 'border-[var(--om-brand)] bg-[var(--om-brand-tint)] text-[var(--om-brand)]'}"
    style="min-height: var(--om-tap)"
    onclick={onChip}
  >
    <Wallet class="h-4 w-4" />
    {#if shift}
      <span class="hidden lg:inline">{shift.opened_by_name ?? ''} · {language.t('shiftSince')} {sinceLabel} ·</span>
      <span class="tabular-nums">{cashLabel}</span>
    {:else}
      <span>{language.t('shiftOpenBtn')}</span>
    {/if}
  </button>

  {#if menuOpen && shift}
    <div class="absolute right-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-xl border border-[var(--border)] bg-white shadow-lg">
      <div class="border-b border-[var(--border)] p-3 text-sm">
        <div class="text-xs text-[var(--text-muted)]">{language.t('shiftCashOnHand')}</div>
        <div class="text-xl font-bold tabular-nums">{cashLabel}</div>
      </div>
      <button class="flex w-full items-center gap-2 px-3 py-3 text-left text-sm hover:bg-[var(--cream)]" onclick={() => show('in')}><ArrowDownLeft class="h-4 w-4" />{language.t('shiftCashIn')}</button>
      <button class="flex w-full items-center gap-2 px-3 py-3 text-left text-sm hover:bg-[var(--cream)]" onclick={() => show('out')}><ArrowUpRight class="h-4 w-4" />{language.t('shiftCashOut')}</button>
      <button class="flex w-full items-center gap-2 px-3 py-3 text-left text-sm font-semibold text-red-700 hover:bg-red-50" onclick={() => show('close')}><Lock class="h-4 w-4" />{language.t('shiftClose')}</button>
    </div>
  {/if}
</div>

{#if mode}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] backdrop-blur-sm md:items-center" role="presentation" onclick={(e) => { if (e.target === e.currentTarget && closedCash === null) mode = null; }}>
    <section class="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl" role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font min-w-0 flex-1 truncate text-2xl font-bold text-[var(--espresso)]">{language.t(title)}</h2>
        {#if closedCash === null}<button class="btn-outline px-4 py-2" onclick={() => (mode = null)}>{language.t('close')}</button>{/if}
      </div>

      {#if closedCash !== null}
        <div class="space-y-2 p-5 text-center">
          <div class="text-sm text-[var(--text-muted)]">{language.t('shiftClosedMsg')}</div>
          <div class="text-3xl font-bold tabular-nums">{formatRupiah(closedCash)}</div>
          <div class="text-xs text-[var(--text-muted)]">{language.t('shiftNextHint')}</div>
        </div>
        <div class="flex justify-end border-t border-[var(--border)] p-5"><button class="btn-primary" onclick={() => (mode = null)}>{language.t('close')}</button></div>
      {:else}
        <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
          {#if error}<div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>{/if}

          {#if mode === 'open'}
            <p class="text-sm text-[var(--text-muted)]">{language.t('shiftOpeningHint')}</p>
            <div class="rounded-xl bg-[var(--cream)] p-3 text-sm">
              <div class="flex justify-between"><span class="text-[var(--text-muted)]">{language.t('shiftEstimate')}</span><span class="font-semibold tabular-nums">{cur?.cash_on_hand != null ? formatRupiah(cur.cash_on_hand) : '–'}</span></div>
              {#if cur?.cash_on_hand == null}<div class="mt-1 text-xs text-[var(--text-muted)]">{language.t('shiftNoEstimate')}</div>{/if}
            </div>
          {:else if mode === 'close' && shift}
            <div class="rounded-xl bg-[var(--cream)] p-3 text-sm">
              <div class="flex justify-between"><span class="text-[var(--text-muted)]">{language.t('shiftOpeningBalance')}</span><span class="tabular-nums">{formatRupiah(shift.opening_cash)}</span></div>
              <div class="flex justify-between"><span class="text-[var(--text-muted)]">+ {language.t('shiftCashSales')}</span><span class="tabular-nums">{formatRupiah(cur?.cash_sales ?? 0)}</span></div>
              {#if cur?.cash_refunds}<div class="flex justify-between"><span class="text-[var(--text-muted)]">− {language.t('shiftCashRefunds')}</span><span class="tabular-nums">{formatRupiah(cur.cash_refunds)}</span></div>{/if}
              <div class="flex justify-between"><span class="text-[var(--text-muted)]">+ {language.t('shiftCashIn')}</span><span class="tabular-nums">{formatRupiah(cur?.cash_in ?? 0)}</span></div>
              <div class="flex justify-between"><span class="text-[var(--text-muted)]">− {language.t('shiftCashOut')}</span><span class="tabular-nums">{formatRupiah(cur?.cash_out ?? 0)}</span></div>
              <div class="mt-1 flex justify-between border-t border-[var(--border)] pt-1 font-bold"><span>{language.t('shiftExpected')}</span><span class="tabular-nums">{formatRupiah(shift.expected_cash ?? 0)}</span></div>
            </div>
          {:else}
            <div>
              <span class={label}>{language.t('shiftMovCategory')}</span>
              <div class="flex flex-wrap gap-1.5">{#each categories as c}<button class={chip(category === c)} onclick={() => (category = c)}>{c}</button>{/each}</div>
              {#if mode === 'out' && EXPENSE_CATEGORIES.includes(category)}<div class="mt-1 text-xs text-[var(--text-muted)]">→ {language.t('finTabExpenses')}</div>{/if}
            </div>
            <label class="block"><span class={label}>{language.t('shiftMovReason')}</span><input class="field" maxlength="200" bind:value={text} /></label>
          {/if}

          <label class="block">
            <span class={label}>{language.t(mode === 'open' ? 'shiftOpeningCash' : mode === 'close' ? 'shiftCounted' : 'finAmount')}</span>
            <input class="field" type="text" inputmode="numeric" placeholder="0" value={amount} oninput={(e) => { amount = formatDigits(e.currentTarget.value); e.currentTarget.value = amount; }} />
          </label>

          {#if mode === 'close' && amount !== ''}
            <div class="flex justify-between text-sm font-semibold">
              <span>{language.t('shiftVariance')}</span>
              <span class="tabular-nums {overLimit ? 'text-red-700' : variance ? 'text-amber-700' : 'text-[var(--om-brand)]'}">
                {variance === 0 ? language.t('shiftExact') : `${variance > 0 ? '+' : '−'}${formatRupiah(Math.abs(variance))} · ${language.t(variance < 0 ? 'shiftShort' : 'shiftOver')}`}
              </span>
            </div>
            {#if overLimit}<div class="text-xs text-red-700">{language.t('shiftOverMsg')}</div>{/if}
            <label class="block"><span class={label}>{language.t(overLimit ? 'shiftNoteRequired' : 'shiftNoteOptional')}</span><input class="field" maxlength="300" bind:value={text} /></label>
          {/if}
        </div>
        <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
          <button class="btn-outline" onclick={() => (mode = null)}>{language.t('cancel')}</button>
          <button class="btn-primary disabled:opacity-50" disabled={saving} onclick={submit}>{saving ? language.t('saving') : language.t(mode === 'close' ? 'shiftClose' : mode === 'open' ? 'shiftOpenBtn' : 'shiftSave')}</button>
        </div>
      {/if}
    </section>
  </div>
{/if}
