<script lang="ts">
  import { goto } from '$app/navigation';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { session } from '$lib/stores/session.svelte';

  let identifier = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');
  let showPassword = $state(false);

  async function submit() {
    loading = true;
    error = '';
    try {
      auth.init();
      await auth.login(identifier, password);
      if (auth.user?.is_superadmin) {
        await goto('/admin');
      } else {
        await session.loadStores();
        await goto('/dashboard');
      }
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>{language.t('signIn')} | Kasir</title></svelte:head>

<main class="grid min-h-screen bg-[var(--om-bg)] lg:grid-cols-2">
  <section class="hidden bg-[var(--om-ink)] p-12 text-[var(--om-on-dark)] lg:flex lg:flex-col lg:justify-between">
    <div class="logo-font text-[32px]">&gt;omnify<span class="om-cursor ml-0.5 inline-block h-7 w-3.5 bg-[var(--om-brand-bright)] align-middle"></span></div>
    <div>
      <p class="max-w-xl text-[44px] font-semibold leading-[1.08] tracking-[-0.02em]">{language.t('serviceHero')}</p>
      <p class="mt-5 max-w-lg text-[16px] text-[var(--om-on-dark-2)]">{language.t('connectedBackendCopy')}</p>
    </div>
    <div class="grid grid-cols-3 gap-3 text-[14px] text-[var(--om-on-dark-2)]">
      <div class="rounded-[14px] bg-white/10 p-4">{language.t('posCheckout')}</div>
      <div class="rounded-[14px] bg-white/10 p-4">{language.t('catalog')}</div>
      <div class="rounded-[14px] bg-white/10 p-4">{language.t('salesReports')}</div>
    </div>
  </section>

  <section class="flex flex-col">
    <div class="logo-font bg-[var(--om-ink)] px-4 py-4 text-2xl text-[var(--om-on-dark)] lg:hidden">&gt;omnify<span class="om-cursor ml-0.5 inline-block h-5 w-2.5 bg-[var(--om-brand-bright)] align-middle"></span></div>
    <div class="flex flex-1 items-center justify-center p-6">
    <form class="card w-full max-w-md p-6 sm:p-8" onsubmit={(event) => { event.preventDefault(); submit(); }}>
      <div class="mb-8">
        <h1 class="text-2xl font-semibold tracking-[-0.01em]">{language.t('welcomeBack')}</h1>
        <p class="mt-2 text-sm text-[var(--text-muted)]">{language.t('signIn')}</p>
      </div>

      {#if error}
        <div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</div>
      {/if}

      <label class="mb-4 block text-sm font-bold text-[var(--espresso)]">
        {language.t('emailOrPhone')}
        <input class="field mt-2" type="text" inputmode="text" autocomplete="username" bind:value={identifier} required />
      </label>
      <label class="mb-3 block text-sm font-bold text-[var(--espresso)]">
        {language.t('password')}
        <div class="relative mt-2">
          <input class="field w-full pr-11" type={showPassword ? 'text' : 'password'} bind:value={password} autocomplete="current-password" required />
          <button
            type="button"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--espresso)] transition-colors"
            onclick={() => (showPassword = !showPassword)}
            aria-label={showPassword ? language.t('hidePassword') : language.t('showPassword')}
          >
            {#if showPassword}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            {:else}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            {/if}
          </button>
        </div>
      </label>

      <a class="mb-6 inline-block text-sm font-semibold text-[var(--om-brand)] hover:underline" href="/forgot-password">
        {language.t('forgotPassword')}
      </a>

      <button class="btn-primary w-full" disabled={loading}>{loading ? language.t('signingIn') : language.t('signIn')}</button>
    </form>
    </div>
  </section>
</main>

<style>
  .om-cursor { animation: omBlink 1.1s steps(1) infinite; }
</style>
