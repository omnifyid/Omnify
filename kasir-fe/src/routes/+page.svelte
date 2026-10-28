<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  onMount(() => goto('/dashboard'));
</script>

<div class="grid min-h-screen place-items-center bg-[var(--cream)] text-[var(--espresso)]">Loading...</div>
