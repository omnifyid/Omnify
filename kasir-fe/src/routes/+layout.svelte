<script lang="ts">
  import '../app.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import AppShell from '$lib/components/AppShell.svelte';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { session } from '$lib/stores/session.svelte';

  const OPERATOR_ROUTES = ['/dashboard', '/pos', '/transactions'];

  let { children } = $props();
  let currentPath = $derived($page.url.pathname);
  let isPublicAuth = $derived(
    currentPath === '/login' ||
    currentPath === '/forgot-password' ||
    currentPath === '/reset-password'
  );
  let isPos = $derived(currentPath === '/pos');
  let isOrders = $derived(currentPath === '/transactions');
  let isOrder = $derived(currentPath.startsWith('/order'));

  onMount(async () => {
    language.init();
    auth.init();
    if (auth.isAuthenticated) {
      await Promise.allSettled([auth.loadMe(), session.loadStores()]);
    }
    if (!auth.isAuthenticated && !isPublicAuth && !isOrder) await goto('/login');
    if (auth.isAuthenticated && isPublicAuth) await goto('/dashboard');
  });

  $effect(() => {
    if (!auth.ready || !auth.user) return;
    if (currentPath.startsWith('/admin') && !auth.user.is_superadmin) {
      goto('/dashboard');
    }
  });

  $effect(() => {
    const role = session.selectedStore?.role;
    if (!role || role === 'OWNER' || role === 'MANAGER') return;
    const allowed = OPERATOR_ROUTES.some((r) => currentPath === r || currentPath.startsWith(r + '/'));
    if (!allowed) goto('/dashboard');
  });
</script>

{#if isPublicAuth || isOrder}
  {@render children()}
{:else if auth.ready && auth.isAuthenticated}
  <AppShell flush={isPos || isOrders}>
    {@render children()}
  </AppShell>
{:else}
  <div class="grid min-h-screen place-items-center bg-[var(--cream)] text-[var(--espresso)]">
    <div class="logo-font text-2xl">&gt;omnify</div>
  </div>
{/if}
