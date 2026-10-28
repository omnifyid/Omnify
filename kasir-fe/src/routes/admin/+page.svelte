<script lang="ts">
  import Toggle from '$lib/components/Toggle.svelte';
  import { api } from '$lib/api/client';
  import { paginatedItems } from '$lib/api/pagination';
  import { auth } from '$lib/stores/auth.svelte';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import type { AdminStore, User, PaginatedResponse } from '$lib/api/types';
  import { ChevronRight, X, Search } from 'lucide-svelte';

  // ── Stats ─────────────────────────────────────────────────
  let statsStores = $state<number | null>(null);
  let statsOwners = $state<number | null>(null);

  async function loadStats() {
    try {
      const res = await api.get<{ store_count: number; owner_count: number }>('/admin/stores/stats');
      statsStores = res.store_count;
      statsOwners = res.owner_count;
    } catch { /* non-critical */ }
  }

  // ── Store list ────────────────────────────────────────────
  let stores = $state<AdminStore[]>([]);
  let loading = $state(false);
  let error = $state('');
  let page = $state(1);
  const LIMIT = 20;
  let total = $state(0);
  let totalPages = $derived(Math.max(1, Math.ceil(total / LIMIT)));

  let search = $state('');
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Create Store modal ────────────────────────────────────
  let storeModalOpen = $state(false);
  let storeName = $state('');
  let storeSlug = $state('');
  let storeDesc = $state('');
  let ownerEmail = $state('');
  let ownerQuery = $state('');
  let ownerResults = $state<User[]>([]);
  let ownerDropdownOpen = $state(false);
  let ownerSearching = $state(false);
  let ownerSearchTimer: ReturnType<typeof setTimeout> | null = null;
  let storeCreating = $state(false);
  let storeError = $state('');

  // ── Edit Store modal ──────────────────────────────────────
  let editStore = $state<AdminStore | null>(null);
  let editName = $state('');
  let editSlug = $state('');
  let editDesc = $state('');
  let editIsActive = $state(true);
  let editSelfOrderEnabled = $state(false);
  let editSaving = $state(false);
  let editError = $state('');
  let editSuccess = $state('');

  // ── Edit User (Owner) modal ───────────────────────────────
  let editUser = $state<User | null>(null);
  let editUserName = $state('');
  let editUserEmail = $state('');
  let editUserPhone = $state('');
  let editUserSuperadmin = $state(false);
  let editUserActive = $state(true);
  let editUserSaving = $state(false);
  let editUserError = $state('');
  let editUserSuccess = $state('');
  let editUserResetPw = $state('');
  let editUserResetting = $state(false);
  let editUserResetError = $state('');
  let editUserResetSuccess = $state('');

  let editUserLoading = $state(false);

  async function openOwnerEdit(ownerId: string) {
    editUserLoading = true;
    editUserError = ''; editUserSuccess = '';
    editUserResetPw = ''; editUserResetError = ''; editUserResetSuccess = '';
    try {
      const u = await api.get<User>(`/admin/users/${ownerId}`);
      editUser = u;
      editUserName = u.full_name ?? '';
      editUserEmail = u.email;
      editUserPhone = u.phone ?? '';
      editUserSuperadmin = u.is_superadmin ?? false;
      editUserActive = u.is_active ?? true;
    } catch (err) {
      editUserError = err instanceof Error ? err.message : 'Failed to load user';
    } finally {
      editUserLoading = false;
    }
  }

  function closeEditUser() { editUser = null; }

  async function saveEditUser() {
    if (!editUser) return;
    editUserError = ''; editUserSuccess = '';
    editUserSaving = true;
    try {
      const updated = await api.patch<User>(`/admin/users/${editUser.id}`, {
        full_name: editUserName || undefined,
        email: editUserEmail || undefined,
        phone: editUserPhone || undefined,
        is_active: editUserActive,
      });
      editUserSuccess = 'Saved.';
      editUser = updated;
      await load();
    } catch (err) {
      editUserError = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      editUserSaving = false;
    }
  }

  async function resetEditUserPassword() {
    if (!editUser || editUserResetPw.length < 8) return;
    editUserResetError = ''; editUserResetSuccess = '';
    editUserResetting = true;
    try {
      await api.post(`/admin/users/${editUser.id}/reset-password`, { new_password: editUserResetPw });
      editUserResetSuccess = 'Password reset.';
      editUserResetPw = '';
    } catch (err) {
      editUserResetError = err instanceof Error ? err.message : 'Failed to reset password';
    } finally {
      editUserResetting = false;
    }
  }

  // ── Create User modal ─────────────────────────────────────
  let userModalOpen = $state(false);
  let newEmail = $state('');
  let newFullName = $state('');
  let newPhone = $state('');
  let newPassword = $state('');
  let userCreating = $state(false);
  let userError = $state('');

  // ── Data loading ──────────────────────────────────────────
  async function load() {
    loading = true;
    error = '';
    try {
      const q = search ? `&search=${encodeURIComponent(search)}` : '';
      const res = await api.get<PaginatedResponse<AdminStore>>(
        `/admin/stores?limit=${LIMIT}&offset=${(page - 1) * LIMIT}${q}`
      );
      stores = paginatedItems(res);
      total = res.total;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load stores';
    } finally {
      loading = false;
    }
  }

  async function goToPage(p: number) {
    page = p;
    await load();
  }

  function onSearchInput() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      page = 1;
      await load();
    }, 350);
  }

  // ── Owner search combobox ─────────────────────────────────
  function onOwnerInput() {
    ownerEmail = '';
    ownerResults = [];
    ownerDropdownOpen = false;
    if (ownerSearchTimer) clearTimeout(ownerSearchTimer);
    if (ownerQuery.length < 3) return;
    ownerSearchTimer = setTimeout(async () => {
      ownerSearching = true;
      try {
        const res = await api.get<PaginatedResponse<User>>(
          `/admin/users?search=${encodeURIComponent(ownerQuery)}&limit=10`
        );
        ownerResults = paginatedItems(res);
        ownerDropdownOpen = ownerResults.length > 0;
      } catch {
        ownerResults = [];
      } finally {
        ownerSearching = false;
      }
    }, 300);
  }

  function selectOwner(u: User) {
    ownerEmail = u.email;
    ownerQuery = u.email;
    ownerResults = [];
    ownerDropdownOpen = false;
  }

  // ── Create Store ──────────────────────────────────────────
  function openStoreModal() {
    storeName = ''; storeSlug = ''; storeDesc = '';
    ownerEmail = ''; ownerQuery = ''; ownerResults = []; ownerDropdownOpen = false;
    storeError = '';
    storeModalOpen = true;
  }

  function closeStoreModal() { storeModalOpen = false; }

  async function submitCreateStore() {
    if (!ownerEmail) { storeError = 'Please select an owner from the search results.'; return; }
    storeError = '';
    storeCreating = true;
    try {
      await api.post('/admin/stores', {
        name: storeName, slug: storeSlug,
        description: storeDesc || null, owner_email: ownerEmail,
      });
      closeStoreModal();
      await load();
    } catch (err) {
      storeError = err instanceof Error ? err.message : 'Failed to create store';
    } finally {
      storeCreating = false;
    }
  }

  // ── Edit Store ────────────────────────────────────────────
  function openEdit(s: AdminStore) {
    editStore = s;
    editName = s.name;
    editSlug = s.slug;
    editDesc = s.description ?? '';
    editIsActive = s.is_active;
    editSelfOrderEnabled = s.self_order_enabled;
    editError = ''; editSuccess = '';
  }

  function closeEdit() { editStore = null; }

  async function saveEdit() {
    if (!editStore) return;
    editError = ''; editSuccess = '';
    editSaving = true;
    try {
      await api.patch(`/admin/stores/${editStore.id}`, {
        name: editName,
        slug: editSlug,
        description: editDesc || null,
        is_active: editIsActive,
        self_order_enabled: editSelfOrderEnabled,
      });
      editSuccess = 'Saved.';
      await load();
      // refresh the editStore ref so status badge in modal stays in sync
      editStore = stores.find(s => s.id === editStore!.id) ?? editStore;
    } catch (err) {
      editError = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      editSaving = false;
    }
  }

  // ── Create User ───────────────────────────────────────────
  function openUserModal() {
    newEmail = ''; newFullName = ''; newPhone = ''; newPassword = '';
    userError = '';
    userModalOpen = true;
  }

  function closeUserModal() { userModalOpen = false; }

  async function submitCreateUser() {
    userError = '';
    userCreating = true;
    try {
      await api.post('/admin/users', {
        email: newEmail, full_name: newFullName,
        phone: newPhone || undefined, password: newPassword
      });
      closeUserModal();
    } catch (err) {
      userError = err instanceof Error ? err.message : 'Failed to create user';
    } finally {
      userCreating = false;
    }
  }

  onMount(async () => {
    if (!auth.user?.is_superadmin) { await goto('/dashboard'); return; }
    await Promise.all([load(), loadStats()]);
  });
</script>

<svelte:head><title>Super Admin | Kasir</title></svelte:head>

<div class="mb-6 flex items-center justify-between gap-4">
  <div>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">Super Admin</h1>
    <p class="text-[var(--text-muted)]">Manage stores and users.</p>
  </div>
  <div class="flex flex-shrink-0 gap-2">
    <button class="btn-outline" onclick={openUserModal}>Add User</button>
    <button class="btn-primary" onclick={openStoreModal}>Add Store</button>
  </div>
</div>

<div class="mb-6 grid grid-cols-2 gap-4 sm:max-w-xs">
  <div class="card p-5">
    <div class="text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">Stores</div>
    <div class="display-font mt-1 text-4xl font-bold text-[var(--espresso)]">
      {statsStores ?? '—'}
    </div>
  </div>
  <div class="card p-5">
    <div class="text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">Owners</div>
    <div class="display-font mt-1 text-4xl font-bold text-[var(--espresso)]">
      {statsOwners ?? '—'}
    </div>
  </div>
</div>

{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}

<div class="card overflow-hidden">
  <!-- Search bar -->
  <div class="border-b border-[var(--border)] p-4">
    <div class="relative max-w-sm">
      <Search size={15} class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
      <input
        class="field pl-9"
        type="text"
        placeholder="Search by store name or owner email…"
        bind:value={search}
        oninput={onSearchInput}
      />
    </div>
  </div>

  <!-- Table header -->
  <div class="grid grid-cols-[1fr_150px_90px_72px] border-b border-[var(--border)] bg-[var(--cream)] px-4 py-3 text-xs font-bold text-[var(--text-muted)] max-md:grid-cols-[1fr_90px_72px]">
    <div>Store</div>
    <div class="max-md:hidden">Owner</div>
    <div>Status</div>
    <div></div>
  </div>

  {#if loading}
    <div class="p-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
  {:else}
    {#each stores as store}
      <div class="grid grid-cols-[1fr_150px_90px_72px] items-center gap-2 border-b border-[var(--border)] px-4 py-3 last:border-0 max-md:grid-cols-[1fr_90px_72px]">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="truncate font-semibold text-[var(--espresso)]">{store.name}</span>
            {#if store.self_order_enabled}
              <span class="shrink-0 rounded-full bg-[var(--light-brown)] px-2 py-0.5 text-[10px] font-bold text-[var(--espresso)]">Self Order</span>
            {/if}
          </div>
          <div class="truncate font-mono text-xs text-[var(--text-muted)]">{store.slug}</div>
          {#if store.owner_email}
            <div class="truncate text-xs text-[var(--text-muted)] md:hidden">{store.owner_email}</div>
          {/if}
        </div>
        <div class="max-md:hidden min-w-0">
          <div class="truncate text-sm text-[var(--text-muted)]">{store.owner_email ?? '—'}</div>
        </div>
        <div>
          {#if store.is_active}
            <span class="rounded-full bg-green-100 px-2 py-0.5 text-xs font-bold text-green-700">Active</span>
          {:else}
            <span class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold text-gray-500">Inactive</span>
          {/if}
        </div>
        <div class="flex justify-end">
          <button class="btn-outline py-1 text-xs" onclick={() => openEdit(store)}>Edit</button>
        </div>
      </div>
    {:else}
      <div class="p-8 text-center text-sm text-[var(--text-muted)]">
        {search ? 'No stores match your search.' : 'No stores yet.'}
      </div>
    {/each}
  {/if}

  {#if totalPages > 1}
    <div class="flex items-center justify-between gap-3 border-t border-[var(--border)] p-4 text-sm">
      <span class="text-[var(--text-muted)]">Page {page} of {totalPages} · {total} stores</span>
      <div class="flex gap-2">
        <button class="btn-outline py-1" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>Previous</button>
        <button class="btn-outline py-1" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>Next</button>
      </div>
    </div>
  {/if}
</div>

<!-- ── Create Store modal ─────────────────────────────────── -->
{#if storeModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeStoreModal(); }}
  >
    <section
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
      role="dialog" aria-modal="true" tabindex="-1"
    >
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">Add Store</h2>
          <p class="text-sm text-[var(--text-muted)]">Create a new store and assign an owner.</p>
        </div>
        <button class="icon-btn flex-shrink-0" onclick={closeStoreModal}><X size={18} /></button>
      </div>

      <form class="min-h-0 flex-1 overflow-y-auto p-5" onsubmit={(e) => { e.preventDefault(); submitCreateStore(); }}>
        {#if storeError}
          <div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{storeError}</div>
        {/if}
        <div class="grid gap-3">
          <div>
            <label for="s-name" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Store Name</label>
            <input id="s-name" class="field" placeholder="e.g. Kopi Senja" bind:value={storeName} required />
          </div>
          <div>
            <label for="s-slug" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Slug</label>
            <input id="s-slug" class="field" placeholder="e.g. kopi-senja" bind:value={storeSlug} required pattern="[a-z0-9-]+" />
            <p class="mt-1 text-xs text-[var(--text-muted)]">Lowercase letters, numbers, hyphens only.</p>
          </div>
          <div>
            <label for="s-desc" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Description <span class="font-normal">(optional)</span></label>
            <input id="s-desc" class="field" placeholder="Short description" bind:value={storeDesc} />
          </div>
          <div>
            <label for="s-owner" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Owner</label>
            <div class="relative">
              <input
                id="s-owner"
                class="field pr-8"
                type="text"
                placeholder="Search by email (min. 3 characters)"
                bind:value={ownerQuery}
                oninput={onOwnerInput}
                onblur={() => setTimeout(() => { ownerDropdownOpen = false; }, 150)}
                autocomplete="off"
              />
              {#if ownerSearching}
                <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[var(--text-muted)]">…</span>
              {/if}
              {#if ownerDropdownOpen}
                <ul class="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--white)] shadow-lg">
                  {#each ownerResults as u}
                    <li>
                      <button type="button" class="w-full px-4 py-2.5 text-left hover:bg-[var(--cream)]"
                        onmousedown={() => selectOwner(u)}>
                        <div class="text-sm font-semibold text-[var(--espresso)]">{u.email}</div>
                        {#if u.full_name}<div class="text-xs text-[var(--text-muted)]">{u.full_name}</div>{/if}
                      </button>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
            {#if ownerQuery.length > 0 && ownerQuery.length < 3}
              <p class="mt-1 text-xs text-[var(--text-muted)]">Type at least 3 characters to search.</p>
            {:else if ownerQuery.length >= 3 && !ownerSearching && ownerResults.length === 0 && !ownerEmail}
              <p class="mt-1 text-xs text-[var(--text-muted)]">No users found.</p>
            {:else if ownerEmail}
              <p class="mt-1 text-xs font-semibold text-green-700">Selected: {ownerEmail}</p>
            {/if}
          </div>
        </div>
      </form>

      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-primary" onclick={submitCreateStore} disabled={storeCreating}>
          {storeCreating ? 'Creating…' : 'Create Store'}
        </button>
      </div>
    </section>
  </div>
{/if}

<!-- ── Edit Store modal ───────────────────────────────────── -->
{#if editStore}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeEdit(); }}
  >
    <section
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
      role="dialog" aria-modal="true" tabindex="-1"
    >
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">Edit Store</h2>
          <p class="truncate text-sm text-[var(--text-muted)]">{editStore.name}</p>
          {#if editStore.owner_email && editStore.owner_id}
            <button
              class="mt-0.5 flex items-center gap-0.5 text-xs font-semibold text-[var(--warm-brown)] transition-colors hover:text-[var(--espresso)] disabled:opacity-50"
              onclick={() => { if (editStore?.owner_id) void openOwnerEdit(editStore.owner_id); }}
              disabled={editUserLoading}
            >
              {editUserLoading ? 'Loading…' : editStore.owner_email}
              {#if !editUserLoading}<ChevronRight class="h-3 w-3" />{/if}
            </button>
          {/if}
        </div>
        <button class="icon-btn flex-shrink-0" onclick={closeEdit}><X size={18} /></button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto p-5">

        <!-- Store details section -->
        <div class="grid gap-3">
          <div>
            <label for="e-name" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Store Name</label>
            <input id="e-name" class="field" bind:value={editName} required />
          </div>
          <div>
            <label for="e-slug" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Slug</label>
            <input id="e-slug" class="field" bind:value={editSlug} required pattern="[a-z0-9-]+" />
          </div>
          <div>
            <label for="e-desc" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Description <span class="font-normal">(optional)</span></label>
            <input id="e-desc" class="field" placeholder="Short description" bind:value={editDesc} />
          </div>
          <label class="flex cursor-pointer items-center gap-3 rounded-xl border border-[var(--border)] p-3">
            <Toggle bind:checked={editIsActive} />
            <div>
              <div class="text-sm font-semibold text-[var(--espresso)]">Active</div>
              <div class="text-xs text-[var(--text-muted)]">Inactive stores block all member access and transactions.</div>
            </div>
          </label>
          <label class="flex cursor-pointer items-center gap-3 rounded-xl border border-[var(--border)] p-3">
            <Toggle bind:checked={editSelfOrderEnabled} />
            <div>
              <div class="text-sm font-semibold text-[var(--espresso)]">Self Order (Premium)</div>
              <div class="text-xs text-[var(--text-muted)]">Allow customers to order via QR code. Hides menu and blocks public endpoints when disabled.</div>
            </div>
          </label>
        </div>

      </div>

      <div class="flex flex-col gap-2 border-t border-[var(--border)] p-5">
        {#if editError}
          <div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{editError}</div>
        {/if}
        {#if editSuccess}
          <div class="rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">{editSuccess}</div>
        {/if}
        <button class="btn-primary" onclick={saveEdit} disabled={editSaving}>
          {editSaving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>

    </section>
  </div>
{/if}

<!-- ── Create User modal ──────────────────────────────────── -->
{#if userModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeUserModal(); }}
  >
    <section
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
      role="dialog" aria-modal="true" tabindex="-1"
    >
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">Add User</h2>
          <p class="text-sm text-[var(--text-muted)]">Create a new user account.</p>
        </div>
        <button class="icon-btn flex-shrink-0" onclick={closeUserModal}><X size={18} /></button>
      </div>

      <form class="min-h-0 flex-1 overflow-y-auto p-5" onsubmit={(e) => { e.preventDefault(); submitCreateUser(); }}>
        {#if userError}
          <div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{userError}</div>
        {/if}
        <div class="grid gap-3">
          <div>
            <label for="u-email" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Email</label>
            <input id="u-email" class="field" type="email" placeholder="user@example.com" bind:value={newEmail} required />
          </div>
          <div>
            <label for="u-name" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Full Name</label>
            <input id="u-name" class="field" placeholder="Full name" bind:value={newFullName} required />
          </div>
          <div>
            <label for="u-phone" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Phone <span class="font-normal">(optional)</span></label>
            <input id="u-phone" class="field" type="tel" placeholder="08xx-xxxx-xxxx" bind:value={newPhone} />
          </div>
          <div>
            <label for="u-pw" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Password</label>
            <input id="u-pw" class="field" type="password" placeholder="Min. 8 characters" bind:value={newPassword} required minlength="8" />
          </div>
        </div>
      </form>

      <div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
        <button class="btn-primary" onclick={submitCreateUser} disabled={userCreating}>
          {userCreating ? 'Creating…' : 'Create User'}
        </button>
      </div>
    </section>
  </div>
{/if}

<!-- ── Edit User modal ────────────────────────────────────── -->
{#if editUser}
  <div
    class="fixed inset-0 z-50 flex items-end justify-center bg-[var(--om-scrim)] md:items-center"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) closeEditUser(); }}
  >
    <section
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
      role="dialog" aria-modal="true" tabindex="-1"
    >
      <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
        <div class="min-w-0 flex-1">
          <h2 class="display-font text-xl font-bold text-[var(--espresso)]">Edit Owner</h2>
          <p class="truncate text-sm text-[var(--text-muted)]">{editUser.email}</p>
        </div>
        <button class="icon-btn flex-shrink-0" onclick={closeEditUser} aria-label="Tutup"><X size={18} /></button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto p-5 space-y-4">
        {#if editUserError}
          <div class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{editUserError}</div>
        {/if}
        {#if editUserSuccess}
          <div class="rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">{editUserSuccess}</div>
        {/if}

        <div class="grid gap-3">
          <div>
            <label for="eu-name" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Full Name</label>
            <input id="eu-name" class="field" placeholder="Full name" bind:value={editUserName} />
          </div>
          <div>
            <label for="eu-email" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Email</label>
            <input id="eu-email" class="field" type="email" bind:value={editUserEmail} required />
          </div>
          <div>
            <label for="eu-phone" class="mb-1 block text-xs font-semibold text-[var(--text-muted)]">Phone <span class="font-normal">(optional)</span></label>
            <input id="eu-phone" class="field" type="tel" placeholder="08xx-xxxx-xxxx" bind:value={editUserPhone} />
          </div>
          <label class="flex cursor-pointer items-center gap-3 rounded-xl border border-[var(--border)] p-3">
            <Toggle bind:checked={editUserActive} />
            <div>
              <div class="text-sm font-semibold text-[var(--espresso)]">Active</div>
              <div class="text-xs text-[var(--text-muted)]">Inactive users cannot log in.</div>
            </div>
          </label>
        </div>

        <div class="flex justify-end">
          <button class="btn-primary" onclick={saveEditUser} disabled={editUserSaving}>
            {editUserSaving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>

        <!-- Reset password -->
        <div class="border-t border-[var(--border)] pt-4">
          <p class="mb-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">Reset Password</p>
          <div class="flex gap-2">
            <input
              class="field flex-1"
              type="password"
              placeholder="New password (min. 8 chars)"
              bind:value={editUserResetPw}
              minlength="8"
            />
            <button
              class="btn-outline flex-shrink-0"
              onclick={resetEditUserPassword}
              disabled={editUserResetting || editUserResetPw.length < 8}
            >{editUserResetting ? '…' : 'Reset'}</button>
          </div>
          {#if editUserResetError}<p class="mt-2 text-xs text-red-600">{editUserResetError}</p>{/if}
          {#if editUserResetSuccess}<p class="mt-2 text-xs font-semibold text-green-700">{editUserResetSuccess}</p>{/if}
        </div>
      </div>
    </section>
  </div>
{/if}

<style>
  .icon-btn {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--white);
    color: var(--espresso);
    cursor: pointer;
    transition: background 0.15s;
  }
  .icon-btn:hover { background: var(--cream); }
</style>
