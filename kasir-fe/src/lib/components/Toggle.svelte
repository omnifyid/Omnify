<script lang="ts">
  let {
    checked = $bindable(false),
    disabled = false,
    label = '',
    compact = false,
    onchange
  }: { checked?: boolean; disabled?: boolean; label?: string; compact?: boolean; onchange?: (value: boolean) => void } = $props();

  function flip(e: MouseEvent) {
    e.stopPropagation();
    if (disabled) return;
    checked = !checked;
    onchange?.(checked);
  }
</script>

<button
  type="button"
  role="switch"
  aria-checked={checked}
  aria-label={label || undefined}
  {disabled}
  onclick={flip}
  class="flex shrink-0 items-center justify-center"
  style={compact ? undefined : "min-width: var(--om-tap); min-height: var(--om-tap)"}
>
  <span
    class="flex h-6 w-[42px] rounded-xl p-[3px] transition-colors {checked ? 'justify-end bg-[var(--om-brand-bright)]' : 'justify-start bg-[var(--om-border-strong)]'}"
  >
    <span class="h-[18px] w-[18px] rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,.2)]"></span>
  </span>
</button>
