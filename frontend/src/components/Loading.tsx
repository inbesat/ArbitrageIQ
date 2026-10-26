/**
 * A content-shaped loading placeholder (`plans/PRD.md` §4.5: skeleton shapes, not elaborate
 * animation).
 *
 * Each variant is drawn at the size and in the layout of the thing it stands in for, so
 * arrival causes no visible shift (AT-10.15): `cards` is the three-up figure row, `fields`
 * is the four-up control row, `table` is a header plus rows inside the table's own box,
 * `inline` is a short readout in the top bar, `text` is a stack of paragraph lines.
 *
 * The blocks are `aria-hidden`, so a screen reader gets the label and nothing else, and the
 * region is marked `aria-busy`. The pulse is `motion-safe`, so a reader who asks for
 * reduced motion gets flat blocks — no animation, and nothing hidden behind one.
 */
type Variant = 'inline' | 'text' | 'cards' | 'fields' | 'table';

const BLOCK = 'bg-rule/70 motion-safe:animate-pulse';

const SHAPE: Record<Variant, { track: string; item: string }> = {
  inline: { track: 'flex items-center gap-4', item: 'h-5 w-40 rounded' },
  text: { track: 'space-y-2.5', item: 'h-3.5 rounded' },
  cards: { track: 'grid gap-4 sm:grid-cols-3', item: 'h-[124px] rounded-card border border-rule' },
  fields: {
    track: 'grid gap-4 sm:grid-cols-2 lg:grid-cols-4',
    item: 'h-[100px] rounded-card border border-rule',
  },
  table: { track: 'card overflow-hidden', item: 'h-12' },
};

/** Ragged line lengths, so a text skeleton reads as prose rather than as a set of bars. */
const LINE_WIDTH = ['w-full', 'w-[92%]', 'w-[76%]'];

export function Loading({
  label = 'Loading…',
  rows = 3,
  variant = 'text',
}: {
  label?: string;
  rows?: number;
  variant?: Variant;
}) {
  const { track, item } = SHAPE[variant];

  return (
    <div role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true" className={track}>
        {Array.from({ length: rows }, (_, index) => (
          <div
            key={index}
            className={`${BLOCK} ${item} ${
              variant === 'text' ? LINE_WIDTH[index % LINE_WIDTH.length] : ''
            }`}
          />
        ))}
      </div>
    </div>
  );
}
