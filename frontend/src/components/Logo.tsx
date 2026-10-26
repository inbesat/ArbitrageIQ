/**
 * The brand, in one place. Three placements previously each spelled the name for themselves
 * — the landing header, the landing footer and the app shell sidebar — so the identity is
 * now a single component rather than three loose text nodes.
 *
 * The mark is a signature `A`: a bold hand-written letter whose crossbar runs straight
 * through both legs, and a separate shallow swash that leaves the baseline and carries out
 * to the right, where it ends in the accent and the pen lifts. It is the initial of
 * ArbitrageIQ and, read the other way, the contribution line the product measures. Every
 * shape is a filled outline rather than a `stroke-width`, because a pen's weight swells and
 * tapers and a stroke cannot. No corners: each part is one smooth curve. The pen taper is
 * deliberately held back so the letter does not thin to a hairline at 24 px, where the
 * wordmark is hidden on narrow screens and the letter is the only thing naming the brand.
 *
 * Inline SVG, no icon package (`plans/TECH_STACK.md` §3), and colour is inherited through
 * `currentColor`, so the same drawing reads on the ivory landing header, the ink footer and
 * the navy sidebar. A token class, never a hex — the rule written into
 * `tailwind.config.js`.
 */

/** The letter: left leg, apex, right leg, swelling at the apex and tapering to each foot. */
const LETTER =
  'M2.14 20.33 C2.24 20.01 8.27 0.95 8.6 0.95 C8.93 0.95 15.01 20 15.11 20.31 C13.19 20.57 8.93 4.65 8.6 4.65 C8.27 4.65 3.96 20.55 3.86 20.87 Z';

/** The crossbar: straight and evenly weighted, its tapered ends buried inside the legs. */
const CROSSBAR =
  'M5.17 14.4 C5.5 14.38 8.53 13.99 8.86 13.97 C9.19 13.95 12.24 14.02 12.57 14 C12.3 15.12 9.27 15.51 8.94 15.53 C8.61 15.55 5.56 15.48 5.23 15.5 Z';

/** The swash: one shallow sweep just under the baseline, carried out to the right. */
const SWASH =
  'M4.67 22.16 C4.99 22.22 8.49 22.54 8.82 22.55 C9.15 22.56 15.08 21.99 15.41 21.92 C15.73 21.85 27.02 19.11 27.34 19.01 C27.14 19.49 16.12 23.61 15.79 23.68 C15.47 23.75 9.11 24.06 8.78 24.05 C8.45 24.04 4.86 22.91 4.53 22.84 Z';

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
      <svg viewBox="1.89 0.7 26.16 23.6" className="h-full w-auto shrink-0" {...a11y}>
        <g fill="currentColor">
          <path d={LETTER} />
          <path d={SWASH} />
          <path d={CROSSBAR} />
        </g>
        <rect x="25.6" y="18" width="2.2" height="2.2" rx=".5" className={accentClassName} />
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
