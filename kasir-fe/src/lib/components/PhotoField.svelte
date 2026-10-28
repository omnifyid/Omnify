<script lang="ts">
  import { language } from '$lib/i18n/language.svelte';

  let {
    file = $bindable(null),
    currentUrl = null,
    uploading = false,
    onremove
  }: { file?: File | null; currentUrl?: string | null; uploading?: boolean; onremove?: () => void } = $props();

  const MAX_BYTES = 5 * 1024 * 1024;
  const TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/avif'];

  let error = $state('');
  let input: HTMLInputElement | undefined = $state();
  let previewUrl = $state<string | null>(null);

  $effect(() => {
    if (!file) { previewUrl = null; return; }
    const url = URL.createObjectURL(file);
    previewUrl = url;
    return () => URL.revokeObjectURL(url);
  });

  let shown = $derived(previewUrl ?? currentUrl);

  function pick(e: Event & { currentTarget: HTMLInputElement }) {
    const f = e.currentTarget.files?.[0] ?? null;
    e.currentTarget.value = '';
    if (!f) return;
    if (!TYPES.includes(f.type)) { error = language.t('photoTypeError'); return; }
    if (f.size > MAX_BYTES) { error = language.t('photoSizeError'); return; }
    error = '';
    file = f;
  }

  function remove() {
    error = '';
    if (file) file = null;
    else onremove?.();
  }
</script>

<div class="flex flex-col gap-2">
  <span class="text-[16px] font-semibold">{language.t('productPhoto')}</span>
  <div class="flex flex-wrap items-center gap-3.5">
    <button
      type="button"
      class="relative flex h-28 w-28 shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-[14px] border border-dashed border-[#A9ADA4] bg-[var(--om-fill-muted)]"
      aria-label={shown ? language.t('replaceImage') : language.t('selectPhoto')}
      onclick={() => input?.click()}
    >
      {#if shown}
        <img src={shown} alt={language.t('productPhoto')} class="h-full w-full object-cover" />
      {:else}
        <span class="flex flex-col items-center gap-1 text-[var(--om-text-secondary)]">
          <span class="ms !text-[32px]">add_photo_alternate</span>
          <span class="text-[12px] font-medium">{language.t('selectPhoto')}</span>
        </span>
      {/if}
      {#if uploading}
        <span class="absolute inset-0 grid place-items-center bg-[rgba(16,20,15,.72)] text-[var(--om-on-dark)]"><span class="ms animate-spin">progress_activity</span></span>
      {/if}
    </button>

    <div class="flex min-w-[180px] flex-1 flex-col gap-2">
      <span class="text-[12px] leading-[1.45] text-[var(--om-text-secondary)]">{language.t('photoHint')}</span>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-[10px] border border-[var(--om-ink)] bg-white px-3.5 font-semibold"
          style="min-height: var(--om-tap)"
          disabled={uploading}
          onclick={() => input?.click()}
        >
          <span class="ms !text-[20px]">upload</span>{shown ? language.t('replaceImage') : language.t('selectPhoto')}
        </button>
        {#if file || (currentUrl && onremove)}
          <button type="button" class="rounded-[10px] px-3 font-semibold text-[var(--om-danger)]" style="min-height: var(--om-tap)" disabled={uploading} onclick={remove}>
            {language.t('removeImage')}
          </button>
        {/if}
      </div>
      {#if error}<span role="alert" class="text-[12px] font-semibold text-[var(--om-danger)]">{error}</span>{/if}
    </div>
  </div>
  <input bind:this={input} type="file" accept={TYPES.join(',')} class="sr-only" tabindex="-1" onchange={pick} />
</div>
