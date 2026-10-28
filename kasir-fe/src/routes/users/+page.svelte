<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import type { PaginatedResponse, Role, StoreMember } from '$lib/api/types';
  import { language } from '$lib/i18n/language.svelte';
  import { session } from '$lib/stores/session.svelte';
  import { ChevronRight, KeyRound, Trash2, UserPlus, X } from 'lucide-svelte';

  let members = $state<StoreMember[]>([]);
  let loading = $state(false);
  let error = $state('');
  let page = $state(1);
  const limit = 20;
  let total = $state(0);
  let totalPages = $derived(Math.max(1, Math.ceil(total / limit)));

  const assignableRoles: Role[] = ['MANAGER', 'OPERATOR'];

  // Modal state
  let modalOpen = $state(false);
  let modalEditing = $state<StoreMember | null>(null);
  let formEmail = $state('');
  let formName = $state('');
  let formPhone = $state('');
  let formRole = $state<Role>('OPERATOR');
  let saving = $state(false);
  let modalError = $state('');

  // Confirm delete
  let deleteConfirmMember = $state<StoreMember | null>(null);
  let deleteLoading = $state(false);

  // Reset password
  const roleRank: Record<Role, number> = { OWNER: 3, MANAGER: 2, OPERATOR: 1 };
  let currentRole = $derived(session.selectedStore?.role ?? 'OPERATOR');
  let resetPwMember = $state<StoreMember | null>(null);
  let resetPwNew = $state('');
  let resetPwConfirm = $state('');
  let resetPwSaving = $state(false);
  let resetPwError = $state('');
  let resetPwSuccess = $state(false);

  function canResetPassword(member: StoreMember): boolean {
    return (roleRank[currentRole as Role] ?? 0) > (roleRank[member.role] ?? 0);
  }

  function roleLabel(role: Role): string {
    if (role === 'OWNER') return language.t('roleOwner');
    if (role === 'MANAGER') return language.t('roleManager');
    return language.t('roleOperator');
  }

  function openResetPw(member: StoreMember) {
    resetPwMember = member;
    resetPwNew = '';
    resetPwConfirm = '';
    resetPwError = '';
    resetPwSuccess = false;
    closeModal();
  }

  function closeResetPw() {
    resetPwMember = null;
    resetPwNew = '';
    resetPwConfirm = '';
    resetPwError = '';
    resetPwSuccess = false;
  }

  async function submitResetPw() {
    resetPwError = '';
    if (!resetPwNew || !resetPwConfirm) { resetPwError = language.t('allFieldsRequired'); return; }
    if (resetPwNew.length < 8) { resetPwError = language.t('atLeastEightCharacters'); return; }
    if (resetPwNew !== resetPwConfirm) { resetPwError = language.t('passwordsDoNotMatch'); return; }
    const storeId = session.selectedStore?.id;
    const member = resetPwMember;
    if (!storeId || !member) return;
    const uid = member.user_id ?? member.uid ?? member.id;
    if (!uid) return;
    resetPwSaving = true;
    try {
      await api.post(`/stores/${storeId}/members/${uid}/reset-password`, { new_password: resetPwNew });
      resetPwSuccess = true;
      resetPwNew = '';
      resetPwConfirm = '';
    } catch (err) {
      resetPwError = err instanceof Error ? err.message : language.t('error');
    } finally {
      resetPwSaving = false;
    }
  }

  async function load() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    loading = true;
    error = '';
    try {
      const res = await api.get<PaginatedResponse<StoreMember>>(`/stores/${storeId}/members?limit=${limit}&offset=${(page - 1) * limit}`);
      members = paginatedItems(res);
      total = res.total;
    } catch (err) {
      error = err instanceof Error ? err.message : language.t('error');
    } finally {
      loading = false;
    }
  }

  function openCreate() {
    formEmail = '';
    formName = '';
    formPhone = '';
    formRole = 'OPERATOR';
    modalEditing = null;
    modalError = '';
    modalOpen = true;
  }

  function openEdit(member: StoreMember) {
    if (member.role === 'OWNER') return;
    formRole = member.role;
    formEmail = member.email;
    formName = member.full_name ?? '';
    formPhone = member.phone ?? '';
    modalEditing = member;
    modalError = '';
    modalOpen = true;
  }

  function closeModal() {
    modalOpen = false;
    modalEditing = null;
    formEmail = '';
    formName = '';
    formPhone = '';
    formRole = 'OPERATOR';
    modalError = '';
  }

  async function addMember() {
    const storeId = session.selectedStore?.id;
    if (!storeId) return;
    saving = true;
    modalError = '';
    try {
      await api.post(`/stores/${storeId}/members`, {
        email: formEmail,
        role: formRole,
        full_name: formName.trim() || undefined,
        phone: formPhone.trim() || undefined,
      });
      closeModal();
      await load();
    } catch (err) {
      modalError = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  async function saveRole() {
    const storeId = session.selectedStore?.id;
    const member = modalEditing;
    if (!storeId || !member) return;
    const uid = member.user_id ?? member.uid ?? member.id;
    if (!uid) return;
    saving = true;
    modalError = '';
    try {
      await api.patch(`/stores/${storeId}/members/${uid}`, { role: formRole });
      closeModal();
      await load();
    } catch (err) {
      modalError = err instanceof Error ? err.message : language.t('error');
    } finally {
      saving = false;
    }
  }

  function openDeleteConfirm() {
    const member = modalEditing;
    if (!member) return;
    closeModal();
    deleteConfirmMember = member;
  }

  function closeDeleteConfirm() {
    deleteConfirmMember = null;
  }

  async function confirmDelete() {
    const storeId = session.selectedStore?.id;
    const member = deleteConfirmMember;
    if (!storeId || !member) return;
    const uid = member.user_id ?? member.uid ?? member.id;
    if (!uid) return;
    deleteLoading = true;
    try {
      await api.delete(`/stores/${storeId}/members/${uid}`);
      deleteConfirmMember = null;
      await load();
    } finally {
      deleteLoading = false;
    }
  }

  async function goToPage(newPage: number) {
    page = newPage;
    await load();
  }

  function initials(member: StoreMember): string {
    const name = member.full_name ?? member.email ?? '';
    return name.slice(0, 2).toUpperCase();
  }

  $effect(() => { if (session.selectedStore?.id) { page = 1; untrack(() => void load()); } });
</script>

<svelte:head><title>{language.t('users')} | Kasir</title></svelte:head>

<div class="mb-6 flex items-center justify-between gap-4">
  <div>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">{language.t('users')}</h1>
    <p class="text-[var(--text-muted)]">{language.t('inviteStaffSubtitle')}</p>
  </div>
  <button class="btn-primary flex-shrink-0 flex items-center gap-2" onclick={openCreate}>
    <UserPlus class="h-4 w-4" />
    {language.t('addMember')}
  </button>
</div>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}

<div class="card overflow-hidden">
  <div class="hidden border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid md:grid-cols-[48px_1fr_130px_40px]">
    <div></div>
    <div>{language.t('member')}</div>
    <div>{language.t('role')}</div>
    <div></div>
  </div>

  {#each members as member}
    {#snippet rowContent()}
      <!-- Avatar -->
      <div class="grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-bold
                  {member.role === 'OWNER'
                    ? 'bg-[var(--light-brown)] text-[var(--espresso)]'
                    : member.role === 'MANAGER'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-green-100 text-green-700'}">
        {initials(member)}
      </div>
      <!-- Name + email + phone -->
      <div class="min-w-0 flex-1 md:flex-none">
        <div class="truncate font-bold text-[var(--espresso)]">{member.full_name ?? member.email}</div>
        <div class="truncate text-xs text-[var(--text-muted)]">
          {member.full_name ? member.email : ''}
          {#if member.phone}<span class="ml-1">{member.full_name ? '·' : ''} {member.phone}</span>{/if}
        </div>
      </div>
      <!-- Role badge -->
      <div>
        {#if member.role === 'OWNER'}
          <span class="inline-flex items-center rounded-full bg-[var(--light-brown)] px-2.5 py-1 text-xs font-bold text-[var(--espresso)]">{language.t('roleOwner')}</span>
        {:else if member.role === 'MANAGER'}
          <span class="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold text-blue-700">{language.t('roleManager')}</span>
        {:else}
          <span class="inline-flex items-center rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-700">{language.t('roleOperator')}</span>
        {/if}
      </div>
    {/snippet}

    {#if member.role === 'OWNER'}
      <div class="flex items-center gap-3 border-b border-[var(--border)] p-3 last:border-0 opacity-75 md:grid md:grid-cols-[48px_1fr_130px_40px] md:items-center md:px-4 md:py-3">
        {@render rowContent()}
        <div class="hidden md:block"></div>
      </div>
    {:else}
      <div
        class="group flex cursor-pointer items-center gap-3 border-b border-[var(--border)] p-3 last:border-0 transition-colors hover:bg-[var(--cream)] active:bg-[var(--light-brown)]/60 md:grid md:grid-cols-[48px_1fr_130px_40px] md:items-center md:px-4 md:py-3"
        role="button"
        tabindex="0"
        onclick={() => openEdit(member)}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openEdit(member); } }}
        aria-label={`Edit ${member.full_name ?? member.email}`}
      >
        {@render rowContent()}
        <div class="hidden shrink-0 items-center justify-center md:flex">
          <ChevronRight class="h-4 w-4 text-[var(--text-muted)] opacity-25 transition-opacity group-hover:opacity-60" />
        </div>
      </div>
    {/if}
  {:else}
    <div class="p-5 text-sm text-[var(--text-muted)]">{loading ? language.t('loading') : language.t('noMembersFound')}</div>
  {/each}
</div>

{#if totalPages > 1}
  <div class="mt-4 flex items-center justify-between gap-3 text-sm">
    <span class="text-[var(--text-muted)]">{language.t('page')} {page} {language.t('of')} {totalPages}</span>
    <div class="flex gap-2">
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>{language.t('previous')}</button>
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>{language.t('next')}</button>
    </div>
  </div>
{/if}

<!-- ─── Add / Edit modal ──────────────────────────────────────────── -->
{#if modalOpen}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
       role="presentation"
       onclick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
    <section class="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
             role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font flex-1 text-2xl font-bold text-[var(--espresso)]">
          {modalEditing ? language.t('editMember') : language.t('addMember')}
        </h2>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeModal} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
      </div>

      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {#if modalError}
          <div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{modalError}</div>
        {/if}

        {#if modalEditing}
          <!-- Read-only user info -->
          <div class="flex items-center gap-3 rounded-2xl bg-[var(--cream)] px-4 py-3">
            <div class="grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-bold
                        {formRole === 'MANAGER' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}">
              {initials(modalEditing)}
            </div>
            <div class="min-w-0">
              <div class="truncate font-bold text-[var(--espresso)]">{modalEditing.full_name ?? modalEditing.email}</div>
              <div class="truncate text-xs text-[var(--text-muted)]">
                {modalEditing.email}
                {#if modalEditing.phone} · {modalEditing.phone}{/if}
              </div>
            </div>
          </div>
        {:else}
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('email')}</span>
            <input class="field" type="email" placeholder="staff@email.com" bind:value={formEmail} required />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('name')}</span>
            <input class="field" type="text" placeholder="Nama lengkap" bind:value={formName} />
          </label>
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('phone')}</span>
            <input class="field" type="tel" placeholder="08xx-xxxx-xxxx" bind:value={formPhone} />
          </label>
        {/if}

        <label class="block">
          <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('role')}</span>
          <select class="field" bind:value={formRole}>
            {#each assignableRoles as r}
              <option value={r}>{roleLabel(r)}</option>
            {/each}
          </select>
        </label>

        {#if modalEditing && canResetPassword(modalEditing)}
          <div class="flex items-center justify-between rounded-2xl border border-[var(--border)] px-4 py-3">
            <div>
              <div class="text-sm font-bold text-[var(--espresso)]">{language.t('password')}</div>
              <div class="text-xs text-[var(--text-muted)]">{language.t('resetPasswordSubtitle')}</div>
            </div>
            <button
              class="flex shrink-0 items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--cream)] px-3 py-1.5 text-sm font-bold text-[var(--espresso)] transition hover:bg-[var(--light-brown)]"
              onclick={() => modalEditing && openResetPw(modalEditing)}
            >
              <KeyRound class="h-3.5 w-3.5" />
              {language.t('reset')}
            </button>
          </div>
        {/if}
      </div>

      <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
        {#if modalEditing}
          <button
            class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100"
            onclick={openDeleteConfirm}
          >
            <Trash2 class="h-4 w-4" />
            {language.t('remove')}
          </button>
        {/if}
        <div class="flex flex-1 items-center justify-end gap-3">
          <button class="btn-primary" disabled={saving} onclick={() => modalEditing ? saveRole() : addMember()}>
            {saving ? language.t('saving') : modalEditing ? language.t('saveChanges') : language.t('addMember')}
          </button>
        </div>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Remove confirm modal ──────────────────────────────────────── -->
{#if deleteConfirmMember}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--om-scrim)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100">
          <Trash2 class="h-6 w-6 text-red-600" />
        </div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">{language.t('removeMember')}</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]">
          {language.t('remove')} <strong class="text-[var(--espresso)]">{deleteConfirmMember.full_name ?? deleteConfirmMember.email}</strong> {language.t('removeMemberConfirmSuffix')}
        </p>
      </div>
      <div class="flex gap-3 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={closeDeleteConfirm}>{language.t('cancel')}</button>
        <button
          class="flex-1 rounded-full bg-red-600 px-4 py-2.5 font-bold text-white transition hover:bg-red-700 disabled:opacity-50"
          disabled={deleteLoading}
          onclick={confirmDelete}
        >{deleteLoading ? language.t('removing') : language.t('remove')}</button>
      </div>
    </section>
  </div>
{/if}

<!-- ─── Reset password modal ───────────────────────────────────────── -->
{#if resetPwMember}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
       role="presentation"
       onclick={(e) => { if (e.target === e.currentTarget) closeResetPw(); }}>
    <section class="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
             role="dialog" aria-modal="true">
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <h2 class="display-font flex-1 text-2xl font-bold text-[var(--espresso)]">{language.t('resetPassword')}</h2>
        <button class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] transition hover:bg-[var(--cream)] hover:text-[var(--espresso)]" onclick={closeResetPw} aria-label={language.t('close')}><X class="h-4 w-4" /></button>
      </div>

      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        <!-- Member info -->
        <div class="flex items-center gap-3 rounded-2xl bg-[var(--cream)] px-4 py-3">
          <div class="grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-bold
                      {resetPwMember.role === 'MANAGER' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}">
            {(resetPwMember.full_name ?? resetPwMember.email ?? '').slice(0, 2).toUpperCase()}
          </div>
          <div class="min-w-0">
            <div class="truncate font-bold text-[var(--espresso)]">{resetPwMember.full_name ?? resetPwMember.email}</div>
            <div class="truncate text-xs text-[var(--text-muted)]">
              {resetPwMember.email}
              {#if resetPwMember.phone} · {resetPwMember.phone}{/if}
            </div>
          </div>
        </div>

        {#if resetPwSuccess}
          <div class="rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">
            {language.t('passwordResetSuccess')}
          </div>
        {/if}

        {#if resetPwError}
          <div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{resetPwError}</div>
        {/if}

        {#if !resetPwSuccess}
          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('newPassword')}</span>
            <input class="field" type="password" placeholder={language.t('atLeastEightCharacters')} bind:value={resetPwNew} autocomplete="new-password" />
          </label>

          <label class="block">
            <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">{language.t('confirmNewPassword')}</span>
            <input class="field" type="password" placeholder={language.t('repeatNewPassword')} bind:value={resetPwConfirm} autocomplete="new-password" />
          </label>
        {/if}
      </div>

      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-outline" onclick={closeResetPw}>
          {resetPwSuccess ? language.t('close') : language.t('cancel')}
        </button>
        {#if !resetPwSuccess}
          <button class="btn-primary" disabled={resetPwSaving} onclick={submitResetPw}>
            {resetPwSaving ? language.t('saving') : language.t('resetPassword')}
          </button>
        {/if}
      </div>
    </section>
  </div>
{/if}
