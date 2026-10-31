<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { language } from '$lib/i18n/language.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { session } from '$lib/stores/session.svelte';

  type DemoAccount = { email: string; full_name: string; role: 'OWNER' | 'MANAGER' | 'OPERATOR'; stores: string[] };
  type DemoAccounts = { demo_mode: boolean; password: string | null; accounts: DemoAccount[] };

  let identifier = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');
  let showPassword = $state(false);

  // demo shortcuts: only returned when the server runs with DEMO_MODE=true
  let demo = $state<DemoAccounts>({ demo_mode: false, password: null, accounts: [] });
  let sugOpen = $state(false);
  let sugIndex = $state(-1);
  let suggestions = $derived.by(() => {
    const q = identifier.trim().toLowerCase();
    return demo.accounts.filter((a) => !q || a.email.includes(q) || a.full_name.toLowerCase().includes(q));
  });
  const roleLabel = (role: DemoAccount['role']) =>
    role === 'OWNER' ? language.t('roleOwner') : role === 'MANAGER' ? language.t('roleManager') : language.t('roleOperator');

  // live clock for the left panel
  let now = $state(new Date());
  let clock = $derived(now.toLocaleTimeString(language.current === 'id' ? 'id-ID' : 'en-US', { hour: '2-digit', minute: '2-digit', hour12: false }).replace('.', ':'));
  let dateLabel = $derived(now.toLocaleDateString(language.current === 'id' ? 'id-ID' : 'en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));

  onMount(() => {
    const timer = setInterval(() => (now = new Date()), 1000);
    api.get<DemoAccounts>('/auth/demo-accounts').then((r) => (demo = r)).catch(() => {});
    return () => clearInterval(timer);
  });

  function pick(account: DemoAccount) {
    identifier = account.email;
    password = demo.password ?? '';
    sugOpen = false;
    sugIndex = -1;
  }

  function onIdentifierKey(e: KeyboardEvent) {
    if (!demo.demo_mode) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      sugOpen = true;
      const n = suggestions.length;
      if (n) sugIndex = (sugIndex + (e.key === 'ArrowDown' ? 1 : -1) + n) % n;
    } else if (e.key === 'Enter' && sugOpen && sugIndex >= 0 && suggestions[sugIndex]) {
      e.preventDefault();
      pick(suggestions[sugIndex]);
    } else if (e.key === 'Escape') {
      sugOpen = false;
    }
  }

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
  <section class="om-side relative hidden overflow-hidden p-12 text-[var(--om-on-dark)] lg:flex lg:flex-col lg:justify-between">
    <div class="om-dots"></div>
    <div class="logo-font relative flex items-center gap-2.5 text-[32px]">
      <span class="text-[var(--om-brand-on-dark)]">&gt;</span><span>omnify</span><span class="om-cursor inline-block h-7 w-3.5 bg-[var(--om-brand-on-dark)]"></span>
    </div>
    <div class="relative flex flex-col gap-2.5">
      <div class="font-semibold leading-none tracking-[-0.045em] tabular-nums" style="font-size: clamp(56px, 7vw, 96px)">{clock}</div>
      <div class="text-[16px] text-[var(--om-on-dark-2)]">{dateLabel}</div>
    </div>
  </section>

  <section class="flex flex-col">
    <div class="logo-font flex items-center justify-between bg-[var(--om-ink)] px-4 py-4 text-2xl text-[var(--om-on-dark)] lg:hidden">
      <span class="flex items-center gap-1.5"><span class="text-[var(--om-brand-on-dark)]">&gt;</span>omnify<span class="om-cursor inline-block h-5 w-2.5 bg-[var(--om-brand-on-dark)]"></span></span>
      <span class="font-sans text-[12px] tabular-nums text-[var(--om-on-dark-2)]">{clock}</span>
    </div>

    <div class="flex flex-1 items-center justify-center p-6 lg:p-12">
      <form class="flex w-full max-w-[400px] flex-col gap-6" onsubmit={(event) => { event.preventDefault(); submit(); }}>
        <div class="flex flex-col gap-2">
          <h1 class="text-[28px] font-semibold leading-[1.15] tracking-[-0.02em]">{language.t('loginTitle')}</h1>
          <p class="text-sm leading-relaxed text-[var(--om-text-secondary)]">{language.t('loginSubtitle')}</p>
        </div>

        <div class="flex flex-col gap-4">
          <div class="relative flex flex-col gap-1.5">
            <label for="om-identifier" class="text-sm font-medium">{language.t('emailOrPhone')}</label>
            <div class="relative">
              <span class="ms pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--om-text-secondary)]" aria-hidden="true">mail</span>
              <input
                id="om-identifier"
                class="om-input pl-12"
                type="text"
                inputmode="email"
                autocomplete={demo.demo_mode ? 'off' : 'username'}
                autocapitalize="off"
                spellcheck="false"
                placeholder="nama@perusahaan.id"
                role={demo.demo_mode ? 'combobox' : undefined}
                aria-autocomplete={demo.demo_mode ? 'list' : undefined}
                aria-controls={demo.demo_mode ? 'om-demo-accounts' : undefined}
                aria-expanded={demo.demo_mode ? sugOpen : undefined}
                bind:value={identifier}
                oninput={() => { sugOpen = demo.demo_mode; sugIndex = -1; }}
                onfocus={() => (sugOpen = demo.demo_mode)}
                onclick={() => (sugOpen = demo.demo_mode)}
                onblur={() => setTimeout(() => (sugOpen = false), 120)}
                onkeydown={onIdentifierKey}
                required
              />
            </div>

            {#if sugOpen && suggestions.length}
              <div id="om-demo-accounts" role="listbox" aria-label={language.t('demoAccounts')} class="absolute left-0 right-0 top-[calc(100%+6px)] z-20 max-h-[360px] overflow-auto rounded-[14px] border border-[var(--om-border)] bg-white p-1.5 shadow-[var(--om-sh-popover)]">
                <div class="px-2.5 pb-1.5 pt-2 text-[12px] text-[var(--om-text-secondary)]">{language.t('demoAccounts')}</div>
                {#each suggestions as account, i (account.email)}
                  <div
                    role="option"
                    tabindex="-1"
                    aria-selected={i === sugIndex}
                    class="flex min-h-[56px] cursor-pointer items-center gap-3 rounded-[10px] px-2.5 py-2 hover:bg-[var(--om-bg)] {i === sugIndex ? 'bg-[var(--om-fill-muted)]' : ''}"
                    onmousedown={(e) => { e.preventDefault(); pick(account); }}
                  >
                    <div class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--om-brand-tint)] text-[14px] font-bold text-[var(--om-brand)]">{account.full_name.charAt(0).toUpperCase()}</div>
                    <div class="flex min-w-0 flex-1 flex-col gap-px">
                      <span class="truncate text-sm font-semibold">{account.full_name} <span class="font-normal text-[var(--om-text-secondary)]">· {roleLabel(account.role)}</span></span>
                      <span class="truncate text-[12px] text-[var(--om-text-secondary)]">{account.email}</span>
                    </div>
                    <span class="max-w-[40%] shrink-0 text-right text-[12px] text-[var(--om-text-secondary)]">{account.stores.map((s) => s.replace(/^Kopi Senja /, '')).join(', ')}</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="om-password" class="text-sm font-medium">{language.t('password')}</label>
            <div class="relative">
              <span class="ms pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--om-text-secondary)]" aria-hidden="true">lock</span>
              <input
                id="om-password"
                class="om-input px-12"
                type={showPassword ? 'text' : 'password'}
                autocomplete="current-password"
                placeholder={language.t('passwordPlaceholder')}
                bind:value={password}
                required
              />
              <button
                type="button"
                class="absolute right-1 top-1/2 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-[10px] text-[var(--om-text-secondary)] hover:text-[var(--om-ink)]"
                onclick={() => (showPassword = !showPassword)}
                aria-label={showPassword ? language.t('hidePassword') : language.t('showPassword')}
              ><span class="ms">{showPassword ? 'visibility_off' : 'visibility'}</span></button>
            </div>
          </div>

          {#if error}
            <div role="alert" class="flex items-start gap-2 rounded-[10px] bg-[var(--om-danger-tint)] p-3 text-sm font-semibold text-[var(--om-danger)]"><span class="ms !text-[20px] shrink-0">error</span><span>{error}</span></div>
          {/if}

          <button class="btn-primary !h-[52px] !rounded-[12px] !text-[16px]" disabled={loading}>{loading ? language.t('signingIn') : language.t('signIn')}</button>
        </div>

        <a class="text-sm font-semibold text-[var(--om-brand)] hover:underline" href="/forgot-password">{language.t('forgotPassword')}</a>
        <p class="text-[12px] leading-relaxed text-[var(--om-text-secondary)]">{language.t('loginHelp')}</p>
      </form>
    </div>
  </section>
</main>

<style>
  .om-cursor { animation: omBlink 1.1s steps(1) infinite; }
  /* left panel from new-ui: bottom-right and top-left green glows, fading dots */
  .om-side {
    background:
      radial-gradient(90% 70% at 85% 105%, #2f7a1f 0%, rgba(47, 122, 31, 0) 60%),
      radial-gradient(70% 55% at 0% 0%, #1b3a17 0%, rgba(27, 58, 23, 0) 65%),
      linear-gradient(160deg, #10140f 30%, #16301a 100%);
  }
  .om-dots {
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image: radial-gradient(rgba(234, 243, 230, 0.22) 1px, transparent 1.5px);
    background-size: 14px 14px;
    -webkit-mask-image: linear-gradient(20deg, #000 0%, rgba(0, 0, 0, 0) 45%);
    mask-image: linear-gradient(20deg, #000 0%, rgba(0, 0, 0, 0) 45%);
  }
  .om-input {
    width: 100%;
    height: 52px;
    border: 1.5px solid #d7d5ce;
    border-radius: 12px;
    background: #fff;
    font-size: 16px;
    outline: none;
    transition: border-color 0.15s;
  }
  .om-input:focus { border-color: var(--om-ink); }
</style>
