<script lang="ts">
  import BottomTabs from './BottomTabs.svelte';
  import Sidebar from './Sidebar.svelte';
  import Topbar from './Topbar.svelte';

  let { children } = $props();
</script>

<div class="flex h-screen overflow-hidden bg-[var(--om-bg)]">
  <Sidebar />
  <div class="flex min-w-0 flex-1 flex-col">
    <Topbar />
    <main class="min-h-0 flex-1 overflow-auto" style="padding: var(--om-page-pad); grid-auto-rows: max-content">
      {@render children()}
    </main>
    <BottomTabs />
  </div>
</div>
