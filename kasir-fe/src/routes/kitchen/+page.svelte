<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { KitchenStatus, Order, PaginatedResponse } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';

  type Column = { status: KitchenStatus; prev: KitchenStatus | null; label: 'kitchenNew' | 'kitchenCooking' | 'kitchenReady'; next: KitchenStatus; action: 'kitchenStart' | 'kitchenMarkReady' | 'kitchenMarkServed'; icon: string; dot: string };

  const COLUMNS: Column[] = [
    { status: 'NEW', prev: null, label: 'kitchenNew', next: 'COOKING', action: 'kitchenStart', icon: 'local_fire_department', dot: 'bg-[var(--om-text-secondary)]' },
    { status: 'COOKING', prev: 'NEW', label: 'kitchenCooking', next: 'READY', action: 'kitchenMarkReady', icon: 'room_service', dot: 'bg-amber-500' },
    { status: 'READY', prev: 'COOKING', label: 'kitchenReady', next: 'SERVED', action: 'kitchenMarkServed', icon: 'done_all', dot: 'bg-[var(--om-brand-bright)]' }
  ];

  let orders = $state<Order[]>([]);
  let error = $state('');
  let busyId = $state<string | null>(null);
  let activeCol = $state<KitchenStatus>('NEW');
  let now = $state(Date.now());
  let confirmServe = $state<Order | null>(null);
  let served = $state<Order | null>(null); // last served ticket, kept for undo
  let servedTimer: ReturnType<typeof setTimeout> | undefined;

  let enabled = $derived(session.selectedStore?.kitchen_enabled ?? false);

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId || !enabled) return;
    try {
      const res = await api.get<PaginatedResponse<Order>>(`/stores/${storeId}/kitchen/orders?limit=100&offset=0`);
      orders = paginatedItems(res);
      error = '';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load tickets';
    }
  }

  function replace(updated: Order) {
    if (updated.kitchen_status === 'SERVED') orders = orders.filter((o) => o.id !== updated.id);
    else orders = orders.map((o) => (o.id === updated.id ? updated : o));
  }

  async function advance(order: Order, next: KitchenStatus) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    busyId = order.id;
    try {
      replace(await api.patch<Order>(`/stores/${storeId}/orders/${order.id}/kitchen`, { kitchen_status: next }));
      if (next === 'SERVED') {
        served = order;
        clearTimeout(servedTimer);
        servedTimer = setTimeout(() => (served = null), 8000);
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to update ticket';
    } finally {
      busyId = null;
    }
  }

  async function undoServed() {
    const storeId = session.selectedStore?.id;
    const order = served;
    if (!storeId || !order) return;
    clearTimeout(servedTimer);
    served = null;
    try {
      await api.patch<Order>(`/stores/${storeId}/orders/${order.id}/kitchen`, { kitchen_status: 'READY' });
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to undo';
    }
  }

  async function toggleItem(order: Order, itemId: string, done: boolean) {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    try {
      replace(await api.patch<Order>(`/stores/${storeId}/orders/${order.id}/items/${itemId}/kitchen`, { is_done: done }));
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to update item';
    }
  }

  function elapsed(iso?: string) {
    if (!iso) return '0:00';
    const sec = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  }

  function minutes(iso?: string) {
    return iso ? Math.floor((now - new Date(iso).getTime()) / 60000) : 0;
  }

  // ticket age tone: brand < 8 min, amber < 15, red after
  function timerTone(iso?: string) {
    const m = minutes(iso);
    return m >= 15 ? '#8E1A14' : m >= 8 ? '#6A4400' : '#1F5C12';
  }

  function where(o: Order) {
    const parts = [
      o.order_type === 'TAKE_AWAY' ? language.t('takeAway') : o.order_type === 'DINE_IN' || o.table_number ? language.t('dineIn') : '',
      o.table_number ? `T${o.table_number.padStart(2, '0')}` : '',
      o.customer_name ?? ''
    ].filter(Boolean);
    return parts.join(' · ');
  }

  function modifiers(it: NonNullable<Order['items']>[number]) {
    const labels = [...(it.options_snapshot ?? []), ...(it.addons_snapshot ?? [])]
      .map((m) => (m as { label?: string }).label)
      .filter(Boolean);
    return labels.join(', ');
  }

  let byStatus = $derived(
    Object.fromEntries(COLUMNS.map((c) => [c.status, orders.filter((o) => o.kitchen_status === c.status)])) as Record<KitchenStatus, Order[]>
  );
  let avgTicket = $derived.by(() => {
    if (!orders.length) return '0:00';
    const sec = Math.floor(orders.reduce((a, o) => a + (now - new Date(o.created_at ?? now).getTime()), 0) / orders.length / 1000);
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  });

  onMount(() => {
    const tick = setInterval(() => (now = Date.now()), 1000);
    const poll = setInterval(() => void load(), 10000);
    return () => { clearInterval(tick); clearInterval(poll); };
  });

  $effect(() => {
    if (session.selectedStore?.id && enabled) untrack(() => void load());
  });
</script>

<svelte:head><title>{language.t('kitchen')} | Omnify</title></svelte:head>

{#if enabled}
  <div class="mb-3 flex justify-end gap-4 text-xs text-[var(--text-muted)] tabular-nums">
    <span>{language.t('kitchenAvgTicket')} <strong class="text-[var(--espresso)]">{avgTicket}</strong></span>
    <span>{language.t('kitchenActive')} <strong class="text-[var(--espresso)]">{orders.length}</strong></span>
  </div>
{/if}

{#if !enabled}
  <div class="rounded-xl border border-[var(--border)] bg-[var(--white)] p-5 text-[var(--text-muted)]">{language.t('kitchenDisabled')}</div>
{:else}
  {#if error}
    <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
  {/if}

  <div class="mb-3 grid grid-cols-3 gap-1.5 md:hidden">
    {#each COLUMNS as col (col.status)}
      <button
        class="flex h-11 items-center justify-center gap-1.5 rounded-xl border text-sm font-semibold {activeCol === col.status ? 'border-[var(--om-brand)] bg-[var(--light-brown)] text-[var(--om-brand)]' : 'border-[var(--border)] bg-[var(--white)] text-[var(--text-muted)]'}"
        onclick={() => (activeCol = col.status)}
      >
        <span class="h-2 w-2 rounded-full {col.dot}"></span>{language.t(col.label)}
        <span class="text-xs tabular-nums opacity-70">{byStatus[col.status].length}</span>
      </button>
    {/each}
  </div>

  <div class="grid items-stretch gap-3.5 md:grid-cols-3">
    {#each COLUMNS as col (col.status)}
      <section class="min-h-[calc(100vh-11rem)] flex-col rounded-t-2xl bg-[#EFEEE9] p-2.5 pb-4 {activeCol === col.status ? 'flex' : 'hidden md:flex'}">
        <header class="flex items-center gap-2 px-1.5 pb-3 pt-1">
          <span class="h-2 w-2 rounded-full {col.dot}"></span>
          <span class="font-semibold">{language.t(col.label)}</span>
          <span class="text-xs tabular-nums text-[var(--text-muted)]">{byStatus[col.status].length}</span>
        </header>

        <div class="flex flex-col gap-3">
          {#each byStatus[col.status] as o (o.id)}
            <article class="card overflow-hidden border-t-4" style="border-top-color: {timerTone(o.created_at)}">
              <div class="flex items-start justify-between gap-2 border-b border-dashed border-[var(--border)] px-3.5 pb-2.5 pt-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-1.5">
                    <span class="text-xl font-extrabold tabular-nums">#{o.order_number?.split('-').pop()}</span>
                    {#if !o.operator_id}<span class="rounded-[5px] bg-[var(--om-brand-tint)] px-1.5 py-0.5 text-xs font-bold text-[var(--om-brand)]">{language.t('selfOrder')}</span>{/if}
                  </div>
                  <div class="truncate text-xs text-[var(--text-muted)]">{where(o)}</div>
                </div>
                <div class="flex items-center gap-1 font-bold tabular-nums" style="color: {timerTone(o.created_at)}">
                  <span class="ms text-base">timer</span>{elapsed(o.created_at)}
                </div>
              </div>

              <ul class="px-3.5 py-1.5">
                {#each o.items ?? [] as it (it.id)}
                  <li>
                    <button
                      class="flex min-h-11 w-full items-start gap-2.5 py-2 text-left {it.is_done ? 'opacity-55' : ''}"
                      onclick={() => toggleItem(o, it.id, !it.is_done)}
                    >
                      <span class="ms text-xl {it.is_done ? 'fill text-[var(--om-brand-bright)]' : 'text-[#C9C7C0]'}">{it.is_done ? 'check_circle' : 'radio_button_unchecked'}</span>
                      <span class="w-6 font-bold tabular-nums">{it.quantity}×</span>
                      <span class="min-w-0 flex-1">
                        <span class="block {it.is_done ? 'line-through' : ''}">{it.item_name_snapshot}</span>
                        {#if modifiers(it)}<span class="block text-xs font-medium text-[#6A4400]">{modifiers(it)}</span>{/if}
                      </span>
                    </button>
                  </li>
                {/each}
              </ul>

              {#if o.notes}
                <p class="mx-3.5 mb-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-800">“{o.notes}”</p>
              {/if}

              <div class="flex gap-2 p-3 pt-1">
                {#if col.prev}
                  <button
                    class="btn-outline grid w-11 shrink-0 place-items-center px-0 disabled:opacity-50"
                    title={language.t('kitchenBack')}
                    aria-label={language.t('kitchenBack')}
                    disabled={busyId === o.id}
                    onclick={() => advance(o, col.prev!)}
                  ><span class="ms text-base">undo</span></button>
                {/if}
                <button
                  class="{col.status === 'READY' ? 'btn-outline' : 'btn-primary'} flex min-w-0 flex-1 items-center justify-center gap-2 disabled:opacity-50"
                  disabled={busyId === o.id}
                  onclick={() => (col.next === 'SERVED' ? (confirmServe = o) : advance(o, col.next))}
                >
                  <span class="ms text-base">{col.icon}</span>{language.t(col.action)}
                </button>
              </div>
            </article>
          {:else}
            <p class="py-6 text-center text-sm text-[var(--text-muted)]">{language.t('kitchenNoTickets')}</p>
          {/each}
        </div>
      </section>
    {/each}
  </div>
{/if}

{#if served}
  <div class="fixed bottom-5 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full bg-[var(--om-ink)] px-4 py-2.5 text-sm text-white shadow-lg">
    <span>{language.t('kitchenServedToast')} #{served.order_number?.split('-').pop()}</span>
    <button class="font-bold text-[var(--om-brand-bright)]" onclick={undoServed}>{language.t('kitchenUndo')}</button>
  </div>
{/if}

{#if confirmServe}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) confirmServe = null; }}>
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-[var(--light-brown)]">
          <span class="ms text-2xl text-[var(--om-brand)]">done_all</span>
        </div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('kitchenConfirmServeTitle')}</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]">
          <strong class="text-[var(--espresso)]">#{confirmServe.order_number?.split('-').pop()}</strong> · {language.t('kitchenConfirmServeBody')}
        </p>
      </div>
      <div class="flex gap-3 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={() => (confirmServe = null)}>{language.t('cancel')}</button>
        <button class="btn-primary flex-1" onclick={() => { const o = confirmServe!; confirmServe = null; void advance(o, 'SERVED'); }}>{language.t('kitchenMarkServed')}</button>
      </div>
    </section>
  </div>
{/if}
