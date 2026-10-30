# Design System

## Source of truth

Design spec and prototype: `doc/new-ui/` (`README.md`, `tokens.css`, `Omnify.dc.html`). Tokens live in `kasir-fe/src/app.css` as `--om-*` variables; legacy names (`--espresso`, `--cream`, `--warm-brown`, `--border`, `--text-muted`, …) are aliases onto the same palette, so existing markup keeps working.

## Fonts & icons

| Role | Family |
|------|--------|
| UI / body / headings | `Geist` (400–700) |
| Wordmark `>omnify▌` | `JetBrains Mono` 800 — class `.logo-font` |
| Shell icons | Material Symbols Rounded — `<span class="ms">icon_name</span>` (`.fill` for active). Page content still uses `lucide-svelte`. |

Numbers use tabular figures (set on `body`). Type scale: 12 · 14 · 16 · 20 · 24 px (plus 28+ for display).

## Palette (alias → token)

| Variable | Token | Role |
|----------|-------|------|
| `--espresso`, `--dark` | `--om-ink` `#10140F` | Primary text |
| `--text-muted` | `--om-text-secondary` `#4A4E47` | Secondary text |
| `--warm-brown`, `--primary` | `--om-brand` `#1F5C12` | Buttons, links, accents |
| `--mid-brown` | `--om-brand-bright` `#45A02E` | Live dots, charts |
| `--light-brown` | `--om-brand-tint` `#E6F4DF` | Active fills, icon tiles |
| `--cream` | `--om-surface-sunk` `#FBFAF7` | Sidebar, table headers |
| `--background` | `--om-bg` `#F6F5F1` | App background |
| `--white`, `--card` | `--om-surface` `#FFF` | Cards, modals |
| `--border` | `--om-border` `#E7E5DF` | Dividers, card borders |

Modal scrim: `bg-[var(--om-scrim)]`. There is one theme; no theme switcher.

## Shell

- Desktop ≥1200: 244px sidebar. Tablet 768–1199: 84px icon rail that expands on tap. Mobile <768: bottom tab bar (4 items + "Lainnya" sheet).
- Nav items are defined in `$lib/components/nav.ts` (groups: Operasional, Menu, Tim & pengaturan); visibility via `navState.svelte.ts`.
- Header shows page title, date·clock chip, store switcher, user pill.

## Global Utility Classes

Defined in `app.css`: `.card` (radius 14), `.btn-primary` (brand green), `.btn-outline`, `.field` (radius 11, min-height tap), `.status-completed/pending/cancelled`, `.display-font` (Geist), `.logo-font`, `.ms`.

## Page Header Pattern

Every management page uses a flex header with a primary action:

```svelte
<div class="mb-6 flex items-center justify-between gap-4">
  <div>
    <h1 class="display-font text-4xl font-bold text-[var(--espresso)]">Title</h1>
    <p class="text-[var(--text-muted)]">Subtitle — hint about row-click affordance if applicable.</p>
  </div>
  <button class="btn-primary flex-shrink-0">Add X</button>
</div>
```

## Error Banner

```svelte
{#if error}
  <div class="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>
{/if}
```

---

## Table Pattern

### Header row

```svelte
<div class="hidden grid-cols-[...] border-b border-[var(--border)] bg-[var(--cream)]
            px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)] md:grid">
  <div>Column</div>
  ...
</div>
```

### Clickable row (standard)

Every list row is clickable to open the edit modal. Rows use `role="button"` with keyboard support. Inline interactive controls (toggles, reorder arrows) use `e.stopPropagation()` — never a wrapper `<div onclick>`.

```svelte
<div
  class="group flex cursor-pointer items-center gap-3 border-b border-[var(--border)] p-3
         last:border-0 transition-colors hover:bg-[var(--cream)] active:bg-[var(--light-brown)]/60
         xl:grid xl:grid-cols-[...] xl:px-4 xl:py-3"
  role="button"
  tabindex="0"
  onclick={() => openEditModal(item)}
  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openEditModal(item); } }}
  aria-label={`Edit ${item.name}`}
>
  <!-- content -->

  <!-- Inline action that must NOT open the modal (e.g. toggle, reorder) -->
  <button onclick={(e) => { e.stopPropagation(); doAction(); }}>...</button>

  <!-- Optional chevron hint — fades in on hover -->
  <ChevronRight class="h-4 w-4 text-[var(--text-muted)] opacity-25 transition-opacity group-hover:opacity-60" />
</div>
```

**Rules:**
- Never put `onclick` on a wrapper `<div>` inside the row (triggers a11y warning). Use `stopPropagation` directly on the `<button>`.
- The chevron is decorative — `aria-hidden` is implied; the `aria-label` on the row already describes the action.

---

## Modal Pattern

### Shell (bottom-sheet on mobile, centered dialog on desktop)

```svelte
<div class="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(46,26,14,0.55)]
            backdrop-blur-sm md:items-center"
     role="presentation"
     onclick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
  <section class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden
                  rounded-t-3xl bg-[var(--white)] md:rounded-3xl"
           role="dialog" aria-modal="true">
    <!-- Header -->
    <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
      <h2 class="display-font min-w-0 flex-1 truncate text-2xl font-bold text-[var(--espresso)]">Title</h2>
      <button class="btn-outline px-4 py-2" onclick={closeModal}>Close</button>
    </div>
    <!-- Scrollable body -->
    <div class="min-h-0 flex-1 overflow-y-auto p-5 space-y-3"> ... </div>
    <!-- Footer -->
    <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
      <!-- footer content — see patterns below -->
    </div>
  </section>
</div>
```

### Modal footer — create form

```svelte
<div class="flex items-center justify-end gap-3 border-t border-[var(--border)] p-5">
  <button class="btn-outline" onclick={closeModal}>Cancel</button>
  <button class="btn-primary" onclick={submit}>Add X</button>
</div>
```

### Modal footer — edit form (with destructive delete)

Delete sits on the **left**; safe actions on the **right**. This spatial split prevents accidental deletion.

```svelte
<div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
  <button
    class="flex items-center gap-2 rounded-full border border-red-200 bg-red-50
           px-4 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-100"
    onclick={openDeleteConfirm}
  >
    <Trash2 class="h-4 w-4" />
    Delete
  </button>
  <div class="flex flex-1 items-center justify-end gap-3">
    <button class="btn-outline" onclick={closeModal}>Cancel</button>
    <button class="btn-primary" disabled={saving} onclick={save}>
      {saving ? 'Saving…' : 'Save changes'}
    </button>
  </div>
</div>
```

---

## Confirm Delete Modal

A small centered dialog (not a sheet). Always appears on top of everything (`z-50`, same layer — the edit modal closes first before this opens).

```svelte
{#if deleteConfirmItem}
  <div class="fixed inset-0 z-50 flex items-center justify-center
              bg-[rgba(46,26,14,0.6)] p-4 backdrop-blur-sm">
    <section class="w-full max-w-sm overflow-hidden rounded-3xl bg-[var(--white)] shadow-2xl"
             role="dialog" aria-modal="true">
      <div class="flex flex-col items-center px-6 pb-5 pt-7 text-center">
        <div class="mb-4 grid h-14 w-14 place-items-center rounded-full bg-red-100">
          <Trash2 class="h-6 w-6 text-red-600" />
        </div>
        <h2 class="display-font text-xl font-bold text-[var(--espresso)]">Delete X</h2>
        <p class="mt-2 text-sm text-[var(--text-muted)]">
          Are you sure you want to delete
          <strong class="text-[var(--espresso)]">{deleteConfirmItem.name}</strong>?
          This cannot be undone.
        </p>
      </div>
      <div class="flex gap-3 border-t border-[var(--border)] p-4">
        <button class="btn-outline flex-1" onclick={closeDeleteConfirm}>Cancel</button>
        <button
          class="flex-1 rounded-full bg-red-600 px-4 py-2.5 font-bold text-white
                 transition hover:bg-red-700 disabled:opacity-50"
          disabled={deleting}
          onclick={confirmDelete}
        >{deleting ? 'Deleting…' : 'Delete'}</button>
      </div>
    </section>
  </div>
{/if}
```

**State pattern:**
```typescript
let deleteConfirmItem = $state<T | null>(null);
let deleting = $state(false);

function openDeleteConfirm() {
  const item = editingItem; // capture before closeEditModal nulls editingItem
  if (!item) return;
  closeEditModal();
  deleteConfirmItem = item;
}

function closeDeleteConfirm() { deleteConfirmItem = null; }

async function confirmDelete() {
  if (!deleteConfirmItem) return;
  deleting = true;
  try { await removeItem(deleteConfirmItem); deleteConfirmItem = null; }
  finally { deleting = false; }
}
```

---

## Form Fields with Labels

Every field in create/edit modals gets a label. Use `<label class="block">` so tapping the label focuses the input on mobile.

```svelte
<label class="block">
  <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
    Field Name
    <!-- optional hint in normal weight -->
    <span class="normal-case font-normal">(optional)</span>
  </span>
  <input class="field" placeholder="…" bind:value={fieldValue} />
</label>
```

For selects, textareas, and number inputs the same wrapper applies.

---

## Currency Input (Rupiah, dot-separated)

Prices are integers (Rupiah). Inputs use `type="text" inputmode="numeric"` with live dot-formatting via `id-ID` locale. Never use `type="number"` for price fields.

```typescript
function parsePrice(s: string): number {
  const n = parseInt(s.replace(/\D/g, '') || '0', 10);
  return isNaN(n) ? 0 : n;
}

function formatPriceDisplay(n: number): string {
  return n > 0 ? n.toLocaleString('id-ID') : '';
}

function onPriceInput(e: Event & { currentTarget: HTMLInputElement }): string {
  const digits = e.currentTarget.value.replace(/\D/g, '');
  const n = digits ? parseInt(digits, 10) : 0;
  const formatted = n > 0 ? n.toLocaleString('id-ID') : '';
  e.currentTarget.value = formatted; // immediate DOM update for cursor
  return formatted;
}
```

```svelte
<label class="block">
  <span class="mb-0.5 block text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">Price (Rp)</span>
  <input
    class="field"
    type="text"
    inputmode="numeric"
    placeholder="0"
    value={priceDisplay}
    oninput={(e) => { priceDisplay = onPriceInput(e); }}
  />
</label>
```

- Store as `priceDisplay: string` state; derive or call `parsePrice(priceDisplay)` when submitting.
- Open-modal init: `priceDisplay = formatPriceDisplay(existingPrice)`.
- Close-modal reset: `priceDisplay = ''`.

---

## Availability Toggle (inline)

Used inside clickable rows to toggle availability without opening the edit modal.

```svelte
<button
  class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold transition
         {item.is_available === false
           ? 'bg-red-100 text-red-700 hover:bg-red-200'
           : 'bg-green-100 text-green-700 hover:bg-green-200'}
         {toggling ? 'cursor-wait opacity-60' : ''}"
  disabled={toggling}
  onclick={(e) => { e.stopPropagation(); toggleAvailable(item); }}
>
  <span class="relative h-3 w-5 rounded-full bg-current/30">
    <span class="absolute top-0.5 h-2 w-2 rounded-full bg-current transition-all
                 {item.is_available === false ? 'left-0.5' : 'left-3'}"></span>
  </span>
  {toggling ? '...' : item.is_available === false ? 'Off' : 'On'}
</button>
```

---

## Compact Modifier Editor Rows (Options & Addons)

Choice rows in option/addon editors must **never stack vertically** on mobile. Use `flex` with fixed-width wrappers — not `grid-cols` without a breakpoint prefix.

### Choice row (options)
```svelte
<div class="flex items-center gap-1.5">
  <input class="field min-w-0 flex-1 py-2 text-sm" placeholder="e.g. Less Sugar" bind:value={choice.name} />
  <button
    class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--border)]
           text-[var(--text-muted)] transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-500"
    onclick={() => removeChoice(groupIndex, choiceIndex)}
  ><X class="h-3.5 w-3.5" /></button>
</div>
```

### Choice row (addons — with price)
```svelte
<div class="flex items-center gap-1.5">
  <input class="field min-w-0 flex-1 py-2 text-sm" placeholder="e.g. Extra Shot" bind:value={choice.name} />
  <div class="w-[6.5rem] shrink-0">
    <input class="field py-2 text-right text-sm" type="number" min="0" placeholder="0" bind:value={choice.extra_price} />
  </div>
  <button class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--border)]
                 text-[var(--text-muted)] transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-500"
    onclick={() => removeChoice(groupIndex, choiceIndex)}
  ><X class="h-3.5 w-3.5" /></button>
</div>
```

### Group header row (with labeled fields above)
```svelte
<div class="mb-2 flex items-end gap-1.5">
  <div class="min-w-0 flex-1">
    <span class="mb-0.5 block text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">Name</span>
    <input class="field min-w-0 w-full py-2 text-sm" bind:value={group.name} />
  </div>
  <div class="w-14 shrink-0">
    <span class="mb-0.5 block text-center text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">Min</span>
    <input class="field py-2 text-center text-sm" type="number" min="0" placeholder="0" bind:value={group.min_select} />
  </div>
  <div class="w-14 shrink-0">
    <span class="mb-0.5 block text-center text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">Max</span>
    <input class="field py-2 text-center text-sm" type="number" min="0" placeholder="∞" bind:value={group.max_select} />
  </div>
  <!-- Group delete — aligned to bottom of inputs -->
  <button class="mb-0.5 grid h-[2.375rem] w-8 shrink-0 place-items-center rounded-lg
                 border border-red-200 bg-red-50 text-red-400 transition-colors
                 hover:bg-red-100 hover:text-red-600"
    onclick={() => removeGroup(groupIndex)}
  ><Trash2 class="h-3.5 w-3.5" /></button>
</div>
```

**Key rules:**
- Remove-choice button: neutral border, turns red on hover (`hover:border-red-200 hover:bg-red-50 hover:text-red-500`)
- Remove-group button: pre-styled soft red (`border-red-200 bg-red-50`) — signals higher destructiveness
- `+ Add choice` is a text link (`text-xs font-bold text-[var(--warm-brown)]`), not a full button
- `+ Add group` is a `btn-outline` button

---

## Pagination

```svelte
{#if totalPages > 1}
  <div class="mt-4 flex items-center justify-between gap-3 text-sm">
    <span class="text-[var(--text-muted)]">Page {page} of {totalPages}</span>
    <div class="flex gap-2">
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === 1 || loading} onclick={() => goToPage(page - 1)}>Previous</button>
      <button class="btn-outline px-3 py-2 text-sm" disabled={page === totalPages || loading} onclick={() => goToPage(page + 1)}>Next</button>
    </div>
  </div>
{/if}
```

---

## Small / Inline Remove Buttons

| Use case | Style |
|----------|-------|
| Remove a choice from a list | `h-8 w-8` icon button, neutral border → red on hover |
| Remove a whole group | `h-8 w-8` icon button, soft red background always |
| Delete a record (in edit modal footer) | Outlined red pill with Trash2 icon + "Delete" text |
| Confirm delete (in confirm modal) | Solid red filled pill, full width |

---

## Column Label Convention (mini labels above inputs)

Used inside editor cards and group headers where space is tight:

```svelte
<span class="mb-0.5 block text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">
  Label
</span>
```

For centered labels (Min/Max columns): add `text-center`.

---

## Search Bar

Standard search input with debouncing (350ms recommended). Placed in the page header above the table.

```svelte
<input
  type="text"
  placeholder="Search items…"
  class="field w-full max-w-xs"
  bind:value={searchQuery}
  oninput={(e) => {
    searchQuery = e.currentTarget.value;
    debounceSearch();
  }}
/>
```

**Rules:**
- Debounce API calls to avoid excessive network requests
- Clear search on filter/page changes if behavior needs it
- Always search by name (case-insensitive backend filtering via `ilike`)

---

## Filter Modal & Active Chips

Filter modals are bottom-sheet on mobile, centered on desktop. Below the page header, display active filter chips so users see which filters are applied.

### Filter modal (same shell as edit modal)

```svelte
<div class="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(46,26,14,0.55)] backdrop-blur-sm md:items-center">
  <section class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-[var(--white)] md:rounded-3xl">
    <!-- Header -->
    <div class="flex items-center gap-4 border-b border-[var(--border)] p-5">
      <h2 class="display-font text-2xl font-bold text-[var(--espresso)]">Filter</h2>
      <button class="btn-outline px-4 py-2" onclick={closeFilter}>Close</button>
    </div>
    <!-- Body: filter fields -->
    <div class="min-h-0 flex-1 overflow-y-auto p-5 space-y-3">
      <!-- e.g., date range, select dropdowns, toggles -->
    </div>
    <!-- Footer: Apply & Reset -->
    <div class="flex items-center gap-3 border-t border-[var(--border)] p-5">
      <button class="btn-outline flex-1" onclick={resetFilters}>Reset</button>
      <button class="btn-primary flex-1" onclick={applyFilters}>Apply</button>
    </div>
  </section>
</div>
```

### Active filter chips

Display below the search bar (or page header). Each chip has an 'x' to remove it individually.

```svelte
{#if hasActiveFilters}
  <div class="mb-4 flex flex-wrap gap-2">
    {#each activeFilterChips as chip (chip.key)}
      <div class="inline-flex items-center gap-2 rounded-full bg-[var(--light-brown)] px-3 py-1.5 text-xs font-bold text-[var(--espresso)]">
        <span>{chip.label}</span>
        <button class="text-[var(--text-muted)] hover:text-[var(--espresso)]" onclick={() => removeFilter(chip.key)}>
          <X class="h-3.5 w-3.5" />
        </button>
      </div>
    {/each}
  </div>
{/if}
```

**Rules:**
- Chips appear only if filters are active (non-empty)
- Clicking the 'x' removes one filter and refetches
- Clicking "Reset" in the modal clears all filters

---

## Segments & Filter Chips

Use the shared helpers in `$lib/utils/ui` (`SEG_GROUP`, `CHIP_ROW`, `seg()`, `chip()`), never a local copy.

- **Segment** (periods, tabs, view toggle): grey `#EDECE7` group with 4px padding; items are `--om-tap` high, radius 8. The active item has the brand tint background and an inset 2px brand outline.
- **Chip** (status, channel, category, reason): pill, `--om-tap` high on filter rows (40px inside modals), 1px `--om-border` border and white background; the active chip has the brand tint background and a brand border. Filter chips show no counts.
- Chip rows scroll horizontally on mobile and wrap from `md` up.
