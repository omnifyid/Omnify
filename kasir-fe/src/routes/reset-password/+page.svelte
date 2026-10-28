<script lang="ts">
  import { page } from '$app/state';
  import { api } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';

  let password = $state('');
  let confirmPassword = $state('');
  let loading = $state(false);
  let success = $state(false);
  let error = $state('');

  let token = $derived(page.url.searchParams.get('token') ?? '');

  async function submit() {
    error = '';
    if (!token) {
      error = language.t('error');
      return;
    }
    if (password.length < 8) {
      error = language.t('atLeastEightCharacters');
      return;
    }
    if (password !== confirmPassword) {
      error = language.t('passwordsDoNotMatch');
      return;
    }

    loading = true;
    try {
      await api.post('/auth/reset-password', { token, password });
      password = '';
      confirmPassword = '';
      success = true;
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>{language.t('resetPassword')} | Kasir</title></svelte:head>

<main class="flex min-h-screen items-center justify-center bg-[var(--cream)] p-6">
  <form class="card w-full max-w-md p-8" onsubmit={(event) => { event.preventDefault(); submit(); }}>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('chooseNewPassword')}</h1>

    {#if success}
      <div class="mt-6 rounded-xl border border-green-200 bg-green-50 p-3 text-sm font-semibold text-green-700">
        {language.t('passwordUpdated')}
      </div>
      <a class="btn-primary mt-6 block text-center" href="/login">{language.t('goToLogin')}</a>
    {:else}
      {#if error}
        <div class="mt-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</div>
      {/if}

      <label class="mt-6 block text-sm font-bold text-[var(--espresso)]">
        {language.t('newPassword')}
        <input class="field mt-2" type="password" bind:value={password} autocomplete="new-password" required />
      </label>

      <label class="mt-4 block text-sm font-bold text-[var(--espresso)]">
        {language.t('confirmNewPassword')}
        <input class="field mt-2" type="password" bind:value={confirmPassword} autocomplete="new-password" required />
      </label>

      <button class="btn-primary mt-6 w-full" disabled={loading || !token}>
        {loading ? language.t('saving') : language.t('updatePassword')}
      </button>
    {/if}
  </form>
</main>
