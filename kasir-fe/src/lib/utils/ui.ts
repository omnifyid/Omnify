// Segment / chip look from new-ui: the active one gets the brand tint and a brand outline.
export const SEG_GROUP = 'flex max-w-full overflow-x-auto rounded-[11px] bg-[#EDECE7] p-1';
export const CHIP_ROW = 'flex flex-nowrap gap-1.5 overflow-x-auto md:flex-wrap md:overflow-visible';

export const seg = (on: boolean) =>
  `shrink-0 rounded-[8px] px-3 font-semibold transition-colors ${on ? 'bg-[var(--om-brand-tint)] text-[var(--om-ink)] shadow-[inset_0_0_0_2px_var(--om-brand)]' : 'text-[var(--om-text-secondary)] hover:bg-[var(--om-fill-hover)]'}`;

export const chip = (on: boolean) =>
  `flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 font-medium transition-colors ${on ? 'border-[var(--om-brand)] bg-[var(--om-brand-tint)] text-[var(--om-ink)]' : 'border-[var(--om-border)] bg-white text-[var(--om-ink-2)]'}`;
