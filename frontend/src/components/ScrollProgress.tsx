import { motion, useReducedMotion, useScroll, useSpring } from 'motion/react';

/**
 * How far down the page the reader is, as a hairline across the top of the viewport.
 *
 * The bar is the page's own scroll fraction scaled on the x axis, so it costs one composite
 * per frame and never changes layout. `useSpring` is what removes the jitter of a raw scroll
 * value: without it the rule ticks with every wheel event rather than flowing.
 *
 * Not rendered at all when the visitor prefers reduced motion — a bar that snaps in steps is
 * movement without information — and `aria-hidden`, because the scroll position is already
 * announced by the browser.
 */
export function ScrollProgress() {
  return useReducedMotion() ? null : <ProgressBar />;
}

function ProgressBar() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 30, restDelta: 0.001 });

  return (
    <motion.div
      aria-hidden="true"
      style={{ scaleX }}
      className="fixed inset-x-0 top-0 z-[60] h-[2px] origin-left bg-ink"
    />
  );
}
