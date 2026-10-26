/**
 * The brand, in one place. Three placements previously each spelled the name for themselves
 * — the landing header, the landing footer and the app shell sidebar — so the identity is
 * now a single component rather than three loose text nodes.
 *
 * The mark is a signature `A`: a heavy hand-written letter whose crossbar runs straight
 * through both legs, and a swash that leaves the letter's own left foot and carries out to
 * the right, where it ends in the accent and the pen lifts. It is the initial of ArbitrageIQ
 * and, read the other way, the contribution line the product measures. Every shape is a
 * filled outline rather than a `stroke-width`, because a pen's weight swells and tapers and
 * a stroke cannot. No corners: each part is one smooth curve. The letter is deliberately the
 * heaviest thing in the mark and the swash a step below it, because at 24 px — where the
 * wordmark is hidden on narrow screens — the letter is the only thing naming the brand and a
 * flourish that outweighs it reads as an underline with a letter on top.
 *
 * Inline SVG, no icon package (`plans/TECH_STACK.md` §3), and colour is inherited through
 * `currentColor`, so the same drawing reads on the ivory landing header, the ink footer and
 * the navy sidebar. A token class, never a hex — the rule written into
 * `tailwind.config.js`.
 */

/** The letter: left leg, apex, right leg, swelling at the apex and tapering to each foot. */
const LETTER =
  'M2.1 20.46 C2.2 20.14 8.47 0.45 8.8 0.45 C9.13 0.45 15.5 20.11 15.59 20.43 C13.11 20.85 9.13 4.75 8.8 4.75 C8.47 4.75 4.4 20.82 4.3 21.14 Z';

/**
 * The crossbar: a straight, evenly weighted bar. Both of its ends finish *inside* the legs,
 * so the visible stroke simply meets each inner edge — no overshoot, no taper out into the
 * counter, and nothing that reads as a leaf.
 */
const CROSSBAR =
  'M6.15 14.03 C6.48 14.01 7.21 13.86 7.54 13.83 C7.87 13.81 8.41 13.77 8.74 13.75 C9.08 13.73 9.61 13.69 9.95 13.67 C10.28 13.65 11.32 13.69 11.66 13.67 C11.41 15.19 10.39 15.35 10.05 15.37 C9.72 15.39 9.19 15.43 8.86 15.45 C8.52 15.47 7.99 15.5 7.66 15.53 C7.33 15.55 6.59 15.5 6.25 15.53 Z';

/**
 * The swash: the pen's exit. It begins on the letter's own left foot, so the two shapes
 * overlap and the mark stays one unbroken stroke, then thins away as it carries right.
 */
const SWASH =
  'M4.38 20.34 C4.68 20.49 7.36 22.21 7.69 22.26 C8.02 22.3 14.08 22.23 14.4 22.16 C14.73 22.09 24.59 18.84 24.91 18.74 C24.78 19.37 14.92 22.97 14.6 23.04 C14.27 23.11 7.84 23.59 7.51 23.54 C7.18 23.5 3.92 22.01 3.62 21.86 Z';

export interface LogoProps {
  /**
   * Sizes the whole lockup. Pass a height class (`h-6`, `h-7`); the mark takes its height
   * from it and the wordmark's size is fixed, so the two never drift apart.
   */
  className?: string;
  /** The wordmark beside the mark. Off when the mark has to stand on its own. */
  showWordmark?: boolean;
  /** The wordmark's own classes, so a narrow band can drop the name and keep the mark. */
  wordmarkClassName?: string;
  /** The accent element's colour only, so it can be re-tinted on a dark band. */
  accentClassName?: string;
}

export function Logo({
  className,
  showWordmark = true,
  wordmarkClassName,
  accentClassName = 'text-teal',
}: LogoProps) {
  // One decision, in one place, so the two can never disagree: beside the wordmark the text
  // already names the brand, so the svg is decorative; standing alone the svg is the only
  // name there is.
  const a11y = showWordmark
    ? ({ 'aria-hidden': 'true' } as const)
    : ({ role: 'img', 'aria-label': 'ArbitrageIQ' } as const);

  return (
    <span className={`inline-flex shrink-0 items-center gap-2 ${className ?? 'h-7'}`}>
      <svg viewBox="1.85 0.2 25 23.59" className="h-full w-auto shrink-0" {...a11y}>
        <g fill="currentColor">
          <path d={LETTER} />
          <path d={SWASH} />
          <path d={CROSSBAR} />
        </g>
        <rect x="24.4" y="17.9" width="2.2" height="2.2" rx=".5" className={accentClassName} />
      </svg>

      {showWordmark && (
        <span
          className={`font-display text-[17px] font-bold leading-none tracking-tight ${wordmarkClassName ?? ''}`}
        >
          Arbitrage<span className={accentClassName}>IQ</span>
        </span>
      )}
    </span>
  );
}
