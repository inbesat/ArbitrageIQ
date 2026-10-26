import { createElement, type ReactNode } from 'react';

import { motion, useReducedMotion, type Variants } from 'motion/react';

const EASE: [number, number, number, number] = [0.2, 0, 0, 1];

/**
 * Staggered group entrance, for lists that are genuinely read in order: the four deductions
 * in "The problem", the four steps, the six terms and the FAQ rows.
 *
 * `Stagger` is the group and owns the timing; `StaggerItem` is one member and owns its own
 * entrance. Motion propagates the group's variant down to each item, so the items arrive one
 * after another rather than all at once — the pattern the Motion docs call orchestration.
 *
 * Each takes an `as`, so a list stays a list: an `<ol>` renders an `ol` and each member an
 * `li` in both the animated and the reduced-motion state, and the markup never changes shape
 * because of a motion preference. Under reduced motion both render plain elements and nothing
 * is subscribed at all.
 *
 * `amount: 0.15` waits until a sixth of the group is on screen, which is what makes the
 * order readable. It is safe for these four groups because the tallest of them — the six
 * terms stacked one per row at 375 px — is about 1140 px against a viewport of at least
 * 667 px, so the threshold is always reachable. A group taller than roughly six viewports
 * would never reach it and would stay at `opacity: 0`; that is why this is a group helper
 * and not a default on `Reveal` (`plans/PROGRESS.md` §8, DEV-35).
 */
type Tag = 'div' | 'ol' | 'ul' | 'dl' | 'li' | 'details';

/** The six generated components share one prop shape. The union of their type parameters is
 *  not callable as a JSX element, so it is narrowed once here; the tag is what decides the
 *  DOM node. */
const MOTION_TAGS = {
  div: motion.div,
  ol: motion.ol,
  ul: motion.ul,
  dl: motion.dl,
  li: motion.li,
  details: motion.details,
} as const;

const GROUP: Variants = {
  hidden: {},
  // 70 ms between members: long enough to read as a sequence, short enough that the last of
  // seven FAQ rows still lands inside the first second.
  shown: { transition: { staggerChildren: 0.07 } },
};

const ITEM: Variants = {
  hidden: { opacity: 0, y: 14, filter: 'blur(6px)' },
  shown: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.5, ease: EASE } },
};

interface GroupProps {
  as?: Tag;
  className?: string;
  children: ReactNode;
}

interface ItemProps {
  as?: Tag;
  className?: string;
  children: ReactNode;
}

export function Stagger({ as = 'div', className, children }: GroupProps) {
  if (useReducedMotion()) {
    return createElement(as, { className }, children);
  }

  const Element = MOTION_TAGS[as] as typeof motion.div;

  return (
    <Element
      className={className}
      variants={GROUP}
      initial="hidden"
      whileInView="shown"
      viewport={{ once: true, amount: 0.15 }}
    >
      {children}
    </Element>
  );
}

export function StaggerItem({ as = 'div', className, children }: ItemProps) {
  if (useReducedMotion()) {
    return createElement(as, { className }, children);
  }

  const Element = MOTION_TAGS[as] as typeof motion.div;

  return (
    <Element className={className} variants={ITEM}>
      {children}
    </Element>
  );
}
