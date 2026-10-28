# Dual Language ID/EN Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add bilingual Indonesian/English UI copy with Indonesian as the default language, while keeping code variables and translation keys in English.

**Architecture:** Add a small typed frontend i18n layer in `kasir-fe/src/lib/i18n/` with English translation keys, Indonesian and English dictionaries, and a Svelte 5 rune-backed language state. UI components call `language.t('store')`, where the key stays English and the rendered copy becomes `Toko` for Indonesian or `Store` for English.

**Tech Stack:** SvelteKit 2, Svelte 5 runes, TypeScript.

---

## Scope

- Default language: Indonesian (`id`).
- Supported languages: Indonesian (`id`) and English (`en`).
- Translation key naming: English semantic keys only.
- Example mapping: `store -> Toko` in `id`, `store -> Store` in `en`.
- Persist selected language in `localStorage` so the app remembers user preference.
- Update `src/app.html` from `lang="en"` to default `lang="id"` and keep `document.documentElement.lang` in sync after language changes.
- First implementation pass covers shared shell/navigation and high-traffic screens; remaining hardcoded copy can be migrated incrementally.

## Non-Goals

- No backend schema changes.
- No translated database/user content, such as store names, item names, category names, or receipt free text.
- No route localization such as `/id/dashboard` or `/en/dashboard`.
- No external i18n dependency.
- No automated tests for this implementation; verification uses type checking, build, and manual browser checks.

---

### Task 1: Add Typed Translation Dictionaries

**Files:**
- Create: `kasir-fe/src/lib/i18n/messages.ts`

**Step 1: Create the dictionary file**

Create `kasir-fe/src/lib/i18n/messages.ts`:

```ts
export const languages = ['id', 'en'] as const;
export type Language = (typeof languages)[number];

export const DEFAULT_LANGUAGE: Language = 'id';

export const messages = {
  id: {
    account: 'Akun',
    admin: 'Admin',
    cancel: 'Batal',
    categories: 'Kategori',
    dashboard: 'Dasbor',
    discounts: 'Diskon',
    english: 'English',
    indonesian: 'Indonesia',
    language: 'Bahasa',
    logout: 'Keluar',
    logoutConfirm: 'Yakin ingin keluar dari akun ini?',
    menu: 'Menu',
    noStoreSelected: 'Belum ada toko dipilih',
    pos: 'POS',
    products: 'Produk',
    selfOrder: 'Self Order',
    settings: 'Pengaturan',
    store: 'Toko',
    superAdmin: 'Super Admin',
    transactions: 'Transaksi',
    users: 'Pengguna'
  },
  en: {
    account: 'Account',
    admin: 'Admin',
    cancel: 'Cancel',
    categories: 'Categories',
    dashboard: 'Dashboard',
    discounts: 'Discounts',
    english: 'English',
    indonesian: 'Indonesian',
    language: 'Language',
    logout: 'Logout',
    logoutConfirm: 'Are you sure you want to log out of this account?',
    menu: 'Menu',
    noStoreSelected: 'No store selected',
    pos: 'POS',
    products: 'Products',
    selfOrder: 'Self Order',
    settings: 'Settings',
    store: 'Store',
    superAdmin: 'Super Admin',
    transactions: 'Transactions',
    users: 'Users'
  }
} as const satisfies Record<Language, Record<string, string>>;

export type MessageKey = keyof typeof messages.id;

export function isLanguage(value: string): value is Language {
  return (languages as readonly string[]).includes(value);
}
```

**Step 2: Run frontend checks**

```bash
cd kasir-fe
npm run check
```

**Step 3: Commit**

```bash
git add src/lib/i18n/messages.ts
git commit -m "feat: add bilingual message dictionaries"
```

---

### Task 2: Add Language State and Translation Helper

**Files:**
- Create: `kasir-fe/src/lib/i18n/language.svelte.ts`

**Step 1: Create the language state**

Create `kasir-fe/src/lib/i18n/language.svelte.ts`:

```ts
import { browser } from '$app/environment';
import { DEFAULT_LANGUAGE, isLanguage, messages, type Language, type MessageKey } from './messages';

const STORAGE_KEY = 'kasir.language';

class LanguageState {
  current = $state<Language>(DEFAULT_LANGUAGE);

  init() {
    if (!browser) return;

    const stored = localStorage.getItem(STORAGE_KEY);
    this.current = stored && isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
    this.syncDocumentLanguage();
  }

  setLanguage(nextLanguage: Language) {
    this.current = nextLanguage;

    if (!browser) return;
    localStorage.setItem(STORAGE_KEY, nextLanguage);
    this.syncDocumentLanguage();
  }

  t(key: MessageKey) {
    return messages[this.current][key];
  }

  private syncDocumentLanguage() {
    document.documentElement.lang = this.current;
  }
}

export const language = new LanguageState();
```

**Step 2: Run frontend checks**

```bash
cd kasir-fe
npm run check
```

**Step 3: Commit**

```bash
git add src/lib/i18n/language.svelte.ts
git commit -m "feat: add persisted language state"
```

---

### Task 3: Initialize Indonesian as the Default App Language

**Files:**
- Modify: `kasir-fe/src/app.html`
- Modify: `kasir-fe/src/routes/+layout.svelte`

**Step 1: Set static HTML default**

Modify `kasir-fe/src/app.html`:

```html
<html lang="id">
```

**Step 2: Initialize language state during app startup**

Modify `kasir-fe/src/routes/+layout.svelte`:

```ts
import { language } from '$lib/i18n/language.svelte';
```

Call `language.init()` at the start of the existing `onMount` callback:

```ts
onMount(async () => {
  language.init();
  auth.init();
  if (auth.isAuthenticated) {
    await Promise.allSettled([auth.loadMe(), session.loadStores()]);
  }
  if (!auth.isAuthenticated && !isPublicAuth && !isOrder) await goto('/login');
  if (auth.isAuthenticated && isPublicAuth) await goto('/dashboard');
});
```

**Step 3: Run frontend checks**

```bash
cd kasir-fe
npm run check
```

**Step 4: Commit**

```bash
git add src/app.html src/routes/+layout.svelte
git commit -m "feat: default app language to Indonesian"
```

---

### Task 4: Add a Language Selector to the Topbar

**Files:**
- Modify: `kasir-fe/src/lib/components/Topbar.svelte`

**Step 1: Add imports**

```ts
import { language } from '$lib/i18n/language.svelte';
import { languages, messages, type Language } from '$lib/i18n/messages';
```

**Step 2: Add a language change handler**

```ts
function updateLanguage(event: Event) {
  language.setLanguage((event.currentTarget as HTMLSelectElement).value as Language);
}
```

**Step 3: Replace the empty store fallback**

```svelte
{session.selectedStore?.name ?? language.t('noStoreSelected')}
```

**Step 4: Add the selector beside the store selector**

```svelte
<select
  class="field max-w-36 py-2 text-sm"
  aria-label={language.t('language')}
  value={language.current}
  onchange={updateLanguage}
>
  {#each languages as option}
    <option value={option}>{messages[language.current][option === 'id' ? 'indonesian' : 'english']}</option>
  {/each}
</select>
```

**Step 5: Run frontend checks**

```bash
cd kasir-fe
npm run check
```

**Step 6: Commit**

```bash
git add src/lib/components/Topbar.svelte
git commit -m "feat: add language selector"
```

---

### Task 5: Migrate Shared Shell Labels

**Files:**
- Modify: `kasir-fe/src/lib/components/Sidebar.svelte`

**Step 1: Convert navigation labels to translation keys**

Add imports:

```ts
import { language } from '$lib/i18n/language.svelte';
import type { MessageKey } from '$lib/i18n/messages';
```

Update the nav type and entries:

```ts
const nav: { href: string; labelKey: MessageKey; icon: typeof BarChart3; roles: Role[] }[] = [
  { href: '/dashboard', labelKey: 'dashboard', icon: BarChart3, roles: ['OWNER', 'MANAGER', 'OPERATOR'] },
  { href: '/pos', labelKey: 'pos', icon: ShoppingCart, roles: ['OWNER', 'MANAGER', 'OPERATOR'] },
  { href: '/categories', labelKey: 'categories', icon: Tags, roles: ['OWNER', 'MANAGER'] },
  { href: '/products', labelKey: 'products', icon: Package, roles: ['OWNER', 'MANAGER'] },
  { href: '/discounts', labelKey: 'discounts', icon: Percent, roles: ['OWNER', 'MANAGER'] },
  { href: '/users', labelKey: 'users', icon: Users, roles: ['OWNER', 'MANAGER'] },
  { href: '/transactions', labelKey: 'transactions', icon: History, roles: ['OWNER', 'MANAGER', 'OPERATOR'] },
  { href: '/selforder', labelKey: 'selfOrder', icon: QrCode, roles: ['OWNER', 'MANAGER'] },
  { href: '/settings', labelKey: 'settings', icon: Settings, roles: ['OWNER', 'MANAGER'] },
  { href: '/account', labelKey: 'account', icon: KeyRound, roles: ['OWNER', 'MANAGER', 'OPERATOR'] }
];
```

Render labels:

```svelte
{language.t(item.labelKey)}
```

**Step 2: Replace hardcoded shared shell copy**

Use these replacements:

```svelte
{language.t('admin')}
{language.t('menu')}
{language.t('superAdmin')}
{language.t('logout')}
{language.t('logoutConfirm')}
{language.t('cancel')}
```

**Step 3: Run frontend checks**

```bash
cd kasir-fe
npm run check
```

**Step 4: Commit**

```bash
git add src/lib/components/Sidebar.svelte
git commit -m "feat: translate app shell labels"
```

---

### Task 6: Migrate High-Traffic Page Copy Incrementally

**Files:**
- Modify first pass:
  - `kasir-fe/src/routes/dashboard/+page.svelte`
  - `kasir-fe/src/routes/pos/+page.svelte`
  - `kasir-fe/src/routes/settings/+page.svelte`
  - `kasir-fe/src/routes/products/+page.svelte`
  - `kasir-fe/src/routes/categories/+page.svelte`
  - `kasir-fe/src/routes/transactions/+page.svelte`
- Modify as needed:
  - `kasir-fe/src/lib/i18n/messages.ts`

**Step 1: Pick one page at a time**

For each page:

- Import `language` from `$lib/i18n/language.svelte`.
- Add new English semantic keys to `messages.ts`.
- Add both `id` and `en` values in the same commit.
- Replace hardcoded UI copy with `language.t('keyName')`.
- Keep variable names English.

Example:

```ts
// messages.ts
id: {
  storeName: 'Nama Toko'
},
en: {
  storeName: 'Store Name'
}
```

```svelte
<label for="store-name">{language.t('storeName')}</label>
```

**Step 2: Run frontend checks after each page**

```bash
cd kasir-fe
npm run check
```

**Step 3: Commit each page separately**

```bash
git add src/routes/settings/+page.svelte src/lib/i18n/messages.ts
git commit -m "feat: translate settings page"
```

```bash
git add src/routes/pos/+page.svelte src/lib/i18n/messages.ts
git commit -m "feat: translate pos page"
```

---

### Task 7: Document i18n Conventions

**Files:**
- Modify: `doc/conventions.md`
- Modify: `kasir-fe/AGENTS.md`

**Step 1: Add frontend i18n convention**

Add to `doc/conventions.md` under Frontend:

```md
- **i18n**: UI copy uses `$lib/i18n/language.svelte` and typed English keys from `$lib/i18n/messages.ts`. Indonesian (`id`) is the default language. Keep code variables and message keys in English, e.g. `store -> Toko` for `id` and `store -> Store` for `en`.
```

Add to `kasir-fe/AGENTS.md` under Architecture or Utility helpers:

```md
- **`$lib/i18n/messages.ts`** — typed bilingual UI dictionaries. Keys are English semantic identifiers; values are localized strings. Default language is Indonesian (`id`).
- **`$lib/i18n/language.svelte.ts`** — global Svelte 5 rune language state with `language.t(key)` and persisted user language preference.
```

**Step 2: Run frontend checks**

```bash
cd kasir-fe
npm run check
```

**Step 3: Commit**

```bash
git add ../doc/conventions.md AGENTS.md
git commit -m "docs: document frontend i18n conventions"
```

---

### Task 8: Final Verification

**Step 1: Run full frontend verification**

```bash
cd kasir-fe
npm run check
npm run build
```

**Step 2: Manual browser verification**

Run:

```bash
cd kasir-fe
npm run dev
```

Open the dev server and verify:

- Initial document language is `id`.
- Initial UI copy is Indonesian.
- `store` concept renders as `Toko` in Indonesian-facing labels.
- Language selector switches visible shared UI copy to English.
- Language choice survives refresh.
- Store names, product names, category names, and receipt custom content remain unchanged.

**Step 3: Final commit if needed**

```bash
git status --short
git add <remaining-files>
git commit -m "chore: verify bilingual frontend defaults"
```

---

## Rollout Notes

- This can be shipped incrementally after Tasks 1-5 because the shell becomes bilingual and Indonesian defaults are in place.
- Page-level migrations in Task 6 should continue until hardcoded user-facing strings in `src/routes` and `src/lib/components` are moved into `messages.ts`.
- Do not translate backend enum values, route paths, API payload keys, TypeScript variable names, or user/database content.
