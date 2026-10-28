# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev          # start dev server (http://localhost:5173)
npm run build        # production build
npm run check        # svelte-kit sync + type check
npm run test         # run all tests with vitest
npx vitest run src/lib/utils/format.test.ts  # run a single test file
```

## Tech Stack

- **SvelteKit 2 + Svelte 5** with TypeScript — CSR only (`ssr = false` in layout)
- **Tailwind CSS v4** (Vite plugin, no config file)
- **lucide-svelte** for icons
- **vitest** for unit tests

## Architecture

This is the frontend for **Kasir**, a multi-tenant POS SaaS. The backend is a FastAPI REST API (documented in `be.md`); the base URL defaults to `http://localhost:8000/api/v1` and is overridden by `VITE_API_BASE_URL`.

### State management

Two singleton Svelte 5 rune classes (`.svelte.ts` files) hold global state:

- **`$lib/stores/auth.svelte.ts`** — `auth` singleton. Manages access/refresh tokens in `localStorage` (`kasir.accessToken`, `kasir.refreshToken`), the current user object, and exposes `login`, `logout`, `refresh`. Must call `auth.init()` on mount before any API call.
- **`$lib/stores/session.svelte.ts`** — `session` singleton. Holds the user's stores list and the active `selectedStoreId`. All store-scoped API calls read `session.selectedStore?.id`.
- **`$lib/i18n/messages.ts`** — typed bilingual UI dictionaries. Keys are English semantic identifiers; values are localized strings. Default language is Indonesian (`id`).
- **`$lib/i18n/language.svelte.ts`** — global Svelte 5 rune language state with `language.t(key)` and persisted user language preference.

### API layer

- **`$lib/api/client.ts`** — `apiRequest` / `api` helpers. Automatically injects `Authorization: Bearer` header, handles 401 → silent refresh retry, and throws `ApiError` on non-2xx responses. Auth callbacks are injected via `configureApiAuth` (called inside `auth.init()`).
- **`$lib/api/types.ts`** — shared TypeScript types mirroring the backend schema (e.g. `Item`, `Order`, `Store`). Note: some fields exist in dual forms (`price`/`base_price`, `name`/`label`, `choices`/`option_choices`) because the API returns different shapes in list vs detail responses.
- **`$lib/api/catalog.ts`** and **`$lib/api/orders.ts`** — payload builder helpers that normalize frontend data to the exact shape expected by the backend.

### Utility helpers

- **`$lib/utils/catalog.ts`** — `getItemPrice`: resolves `item.price ?? item.base_price`.
- **`$lib/utils/modifiers.ts`** — helpers for option/addon groups (`getGroupChoices`, `getGroupLabel`, `getChoiceLabel`, `getChoicePrice`, `getAddonPriceTotal`). Handles both `choices`/`option_choices`/`addon_choices` field variants.
- **`$lib/utils/format.ts`** — `formatRupiah` (IDR currency), `formatDateTime` (id-ID locale).

### Routing

| Route | Notes |
|---|---|
| `/` | Redirects to `/dashboard` |
| `/login` | No AppShell wrapper |
| `/pos` | Full-screen POS, no AppShell wrapper |
| `/dashboard`, `/products`, `/categories`, `/transactions`, `/users` | Wrapped in `AppShell` (Sidebar + Topbar) |

Auth guard is in the root layout: unauthenticated users are sent to `/login`; authenticated users visiting `/login` are sent to `/dashboard`.

### Styling conventions

All CSS custom properties are defined in `src/app.css` (`--cream`, `--espresso`, `--warm-brown`, etc.). Shared utility classes (`.card`, `.btn-primary`, `.btn-outline`, `.field`, `.status-badge`) are also defined there. Use these classes and CSS variables rather than arbitrary Tailwind values when they apply.

The `display-font` class switches to Playfair Display (serif); the default body font is DM Sans.

### Monetary values

All prices are **integers (rupiah)**. No floats. Percentage discounts from the API are stored as **basis points** (1000 = 10%).

## Backend context

See `be.md` for the full API reference including all endpoints, role permissions (`OWNER` / `MANAGER` / `OPERATOR`), order creation flow, and data design decisions.
