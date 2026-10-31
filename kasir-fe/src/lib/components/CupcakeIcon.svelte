<script lang="ts">
  // Placeholder for products without a photo.
  let { size = 24, color = '#CFCDC5' }: { size?: number; color?: string } = $props();
</script>

<svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" style="color: {color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M5.2 12.5h13.6l-1.5 7.6a1 1 0 0 1-1 .8H7.7a1 1 0 0 1-1-.8z" />
  <path d="M5.6 12.5a3.4 3.4 0 0 1 1.6-3 4.8 4.8 0 0 1 9.6 0 3.4 3.4 0 0 1 1.6 3" />
  <circle cx="12" cy="3.6" r="1" />
  <path d="M9.5 15v3M12 15v3M14.5 15v3" />
</svg>
