<script lang="ts">
  import { api } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { languages, messages, type Language } from '$lib/i18n/messages';
  import { auth } from '$lib/stores/auth.svelte';

  let oldPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let saving = $state(false);
  let error = $state('');
  let success = $state(false);

  async function changePassword() {
    error = '';
    success = false;

    if (!oldPassword || !newPassword || !confirmPassword) {
      error = language.t('allFieldsRequired');
      return;
    }
    if (newPassword.length < 8) {
      error = language.t('newPasswordAtLeastEight');
      return;
    }
    if (newPassword !== confirmPassword) {
      error = language.t('newPasswordsDoNotMatch');
      return;
    }

    saving = true;
    try {
      await api.patch('/users/me', { old_password: oldPassword, password: newPassword });
      oldPassword = '';
      newPassword = '';
      confirmPassword = '';
      success = true;
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head><title>{language.t('account')} | Kasir</title></svelte:head>

<div class="mb-6">
  <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('account')}</h1>
  <p class="text-[var(--text-muted)]">{language.t('accountSettingsSubtitle')}</p>
</div>

<!-- User info card -->
<div class="card mb-6 px-5 py-4">
  <div class="flex items-center gap-4">
    <div class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[var(--light-brown)] text-lg font-bold text-[var(--espresso)]">
      {(auth.user?.full_name ?? auth.user?.email ?? '?').slice(0, 2).toUpperCase()}
    </div>
    <div class="min-w-0">
      <div class="truncate font-bold text-[var(--espresso)]">{auth.user?.full_name ?? '—'}</div>
      <div class="truncate text-sm text-[var(--text-muted)]">{auth.user?.email ?? '—'}</div>
    </div>
  </div>
</div>

<!-- Preferences card -->
<div class="card mb-6 px-5 py-5">
  <h2 class="display-font mb-4 text-xl font-bold text-[var(--espresso)]">{language.t('preferences')}</h2>

  <div class="space-y-5">
    <!-- Language -->
    <div>
      <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
        {language.t('language')}
      </span>
      <div class="flex gap-2">
        {#each languages as lang}
          <button
            class="rounded-full border px-4 py-1.5 text-sm font-bold transition
                   {language.current === lang
                     ? 'border-[var(--espresso)] bg-[var(--espresso)] text-white'
                     : 'border-[var(--border)] bg-[var(--white)] text-[var(--espresso)] hover:bg-[var(--cream)]'}"
            onclick={() => language.setLanguage(lang as Language)}
          >
            {messages[language.current][lang === 'id' ? 'indonesian' : 'english']}
          </button>
        {/each}
      </div>
    </div>
  </div>
</div>

<!-- Change password card -->
<div class="card px-5 py-5">
  <h2 class="display-font mb-4 text-xl font-bold text-[var(--espresso)]">{language.t('changePassword')}</h2>

  {#if success}
    <div class="mb-4 rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">
      {language.t('passwordChangedSuccessfully')}
    </div>
  {/if}

  {#if error}
    <div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
  {/if}

  <div class="space-y-3">
    <label class="block">
      <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('password')}</span>
      <input
        class="field"
        type="password"
        placeholder={language.t('enterCurrentPassword')}
        bind:value={oldPassword}
        autocomplete="current-password"
      />
    </label>

    <label class="block">
      <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('newPassword')}</span>
      <input
        class="field"
        type="password"
        placeholder={language.t('atLeastEightCharacters')}
        bind:value={newPassword}
        autocomplete="new-password"
      />
    </label>

    <label class="block">
      <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('confirmNewPassword')}</span>
      <input
        class="field"
        type="password"
        placeholder={language.t('repeatNewPassword')}
        bind:value={confirmPassword}
        autocomplete="new-password"
      />
    </label>
  </div>

  <div class="mt-5 flex justify-end">
    <button class="btn-primary" disabled={saving} onclick={changePassword}>
      {saving ? language.t('saving') : language.t('changePassword')}
    </button>
  </div>
</div>
