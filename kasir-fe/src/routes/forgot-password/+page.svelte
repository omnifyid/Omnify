<script lang="ts">
  import { api } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';

  let email = $state('');
  let loading = $state(false);
  let sent = $state(false);
  let error = $state('');

  async function submit() {
    loading = true;
    error = '';
    try {
      await api.post('/auth/forgot-password', { email });
      sent = true;
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>{language.t('forgotPassword')} | Kasir</title></svelte:head>

<main class="flex min-h-screen items-center justify-center bg-[var(--cream)] p-6">
  <form class="card w-full max-w-md p-8" onsubmit={(event) => { event.preventDefault(); submit(); }}>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('resetPassword')}</h1>
    <p class="mt-2 text-sm text-[var(--text-muted)]">
      {language.t('enterEmailReset')}
    </p>

    {#if sent}
      <div class="mt-6 rounded-xl border border-green-200 bg-green-50 p-3 text-sm font-semibold text-green-700">
        {language.t('checkEmailReset')}
      </div>
    {:else}
      {#if error}
        <div class="mt-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</div>
      {/if}

      <label class="mt-6 block text-sm font-bold text-[var(--espresso)]">
        {language.t('email')}
        <input class="field mt-2" type="email" bind:value={email} autocomplete="email" required />
      </label>

      <button class="btn-primary mt-6 w-full" disabled={loading}>
        {loading ? language.t('sending') : language.t('sendResetLink')}
      </button>
    {/if}

    <a class="mt-6 inline-block text-sm font-semibold text-[var(--mid-brown)] hover:underline" href="/login">
      {language.t('backToLogin')}
    </a>
  </form>
</main>
