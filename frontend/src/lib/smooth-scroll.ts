import { useEffect } from 'react';

import Lenis from 'lenis';

/**
 * Inertial wheel scrolling — the one "premium" behaviour plain CSS cannot reproduce.
 *
 * `scroll-behavior: smooth` animates programmatic and anchor scrolls only; it never
 * touches wheel input, which is why a stock browser feels notchy. Lenis interpolates
 * wheel deltas into a damped scroll instead.
 *
 * `anchors` closes a gap that mounting Lenis otherwise opens. The stylesheet rules Lenis
 * needs include `.lenis.lenis-smooth { scroll-behavior: auto !important }`, which switches
 * off the smooth anchor jumps `index.css` asks for — so the landing header's `#problem`,
 * `#how` … links teleport unless Lenis is told to take them over. Lenis reads the target's
 * own `scroll-margin-top` and the container's `scroll-padding-top` before adding its offset
 * (verified in the installed `lenis` source, `scrollTo`), and every band here carries
 * `scroll-mt-24`, so the 68 px fixed header stays clear with no offset of our own.
 *
 * `stopInertiaOnNavigate` resets the scroll on a same-origin link that changes the path —
 * "Open the workspace" leaves the landing for `/app` — so the page does not arrive still
 * carrying the velocity of the click that left it.
 *
 * Mounted once from the shell. The listener is not installed at all when the visitor
 * asks for reduced motion, so the accessibility promise in `frontend/src/index.css`
 * still holds.
 */
export function useSmoothScroll() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const lenis = new Lenis({
      lerp: 0.09,
      wheelMultiplier: 1.05,
      anchors: true,
      stopInertiaOnNavigate: true,
    });
    let handle = 0;

    const frame = (time: number) => {
      lenis.raf(time);
      handle = requestAnimationFrame(frame);
    };
    handle = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(handle);
      lenis.destroy();
    };
  }, []);
}
