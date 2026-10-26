import type { ReactNode } from 'react';

import { motion, useReducedMotion } from 'motion/react';

const EASE: [number, number, number, number] = [0.2, 0, 0, 1];

interface RevealProps {
  children: ReactNode;
  className?: string;
  /** Seconds to wait after the element enters the viewport. */
  delay?: number;
  /** Distance in px the element travels up into place. */
  y?: number;
  /** px of blur the element resolves out of. Set 0 for large surfaces, where a blur is work. */
  blur?: number;
}

/**
 * Fade, rise and focus on first sight, driven by Motion's viewport trigger.
 *
 * The small blur is what makes the entrance read as settling into place rather than sliding
 * in from below; it resolves over the same 550 ms as the transform, so the two arrive
 * together. Only `opacity`, `transform` and `filter` animate — the layout never moves.
 *
 * Renders a plain element when the visitor prefers reduced motion, so the content is never
 * hidden behind an animation that will not play.
 */
export function Reveal({ children, className, delay = 0, y = 16, blur = 4 }: RevealProps) {
  const reduced = useReducedMotion();

  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y, filter: `blur(${blur}px)` }}
      whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once: true, margin: '-64px' }}
      transition={{ duration: 0.55, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
