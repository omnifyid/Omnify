<script lang="ts">
  import type { ReceiptLine } from '$lib/utils/receipt';

  let { lines, paper = '58' }: { lines: ReceiptLine[]; paper?: '58' | '80' } = $props();
</script>

<svelte:head>
  {@html `<style>@media print{@page{size:${paper}mm auto;margin:4mm 2mm}}</style>`}
</svelte:head>

<div class="receipt" style="width: {paper === '80' ? 340 : 280}px; max-width: 100%">
  {#each lines as line}
    {#if line.t === 'logo'}
      <img src={line.url} alt="logo" class="logo" />
    {:else if line.t === 'rule'}
      <div class="rule"></div>
    {:else if line.t === 'text'}
      <div class="text" class:center={line.align === 'center'} class:bold={line.bold} class:big={line.big} class:muted={line.muted} class:indent={line.indent}>{line.text}</div>
    {:else}
      <div class="row" class:bold={line.bold} class:big={line.big} class:muted={line.muted} class:discount={line.accent === 'discount'}>
        <span class="left">{line.left}</span><span class="right">{line.right}</span>
      </div>
    {/if}
  {/each}
</div>

<style>
  .receipt {
    margin: 0 auto;
    padding: 4px 2px;
    font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
    font-size: 12px;
    line-height: 1.45;
    color: #10140f;
    text-align: left;
  }
  .logo { display: block; margin: 0 auto 6px; max-height: 48px; width: auto; object-fit: contain; }
  .rule { border-top: 1px dashed #a9ada4; margin: 6px 0; }
  .text { white-space: pre-wrap; overflow-wrap: anywhere; }
  .center { text-align: center; }
  .indent { padding-left: 14px; }
  .bold { font-weight: 700; }
  .big { font-size: 15px; }
  .muted { color: #4a4e47; }
  .row { display: flex; justify-content: space-between; gap: 8px; }
  .row .left { min-width: 0; overflow-wrap: anywhere; }
  .row .right { flex-shrink: 0; text-align: right; }
  .row.discount { color: #8e1a14; }
</style>
