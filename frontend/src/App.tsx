import type { ReactNode } from 'react';

import { motion, useReducedMotion, useScroll, useTransform } from 'motion/react';
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { useApi } from './api/client';
import type { Assumptions, Health, Product } from './api/types';
import { AssumptionPanel } from './components/AssumptionPanel';
import { DemoBadge } from './components/DemoBadge';
import { EmptyState } from './components/EmptyState';
import { ErrorState } from './components/ErrorState';
import { Loading } from './components/Loading';
import { Logo } from './components/Logo';
import { Reveal } from './components/Reveal';
import { ScrollProgress } from './components/ScrollProgress';
import { useSmoothScroll } from './lib/smooth-scroll';
import { BudgetLab } from './views/BudgetLab';
import { Import } from './views/Import';
import { Landing } from './views/Landing';
import { Methodology } from './views/Methodology';
import { Overview } from './views/Overview';
import { Profitability } from './views/Profitability';

/**
 * The application shell: five routes, a responsive navigation frame, and the app-wide
 * readouts (backend status, demo-data marker, assumptions).
 *
 * T13 built the shell; T14 added the real Overview and Import view bodies; T16 added the
 * remaining three views. `ViewBody` below still renders each view's own informative empty
 * state, which is what `plans/ACCEPTANCE_TESTS.md` AT-10.1 asks of a fresh start. No money
 * is calculated or parsed anywhere in this file (`AGENTS.md` rule 7).
 *
 * The five views now live under `/app/*`; `/` is the public landing page, which has no
 * sidebar. `AppShell` is everything that used to be `App`.
 */

// Stable predicates: `useApi` re-runs whenever its `isEmpty` reference changes, so these
// must be module-level rather than inline arrows.
const NEVER_EMPTY = () => false;
const NO_PRODUCTS = (products: Product[]) => products.length === 0;

interface ViewSpec {
  path: string;
  /** The route path relative to `/app`, used as the nested `<Route path>`. */
  segment: string;
  /** Short label for the sidebar. */
  label: string;
  /** Small caps line above the heading, giving the view its place in the flow. */
  eyebrow: string;
  heading: string;
  intro: string;
  emptyTitle: string;
  emptyMessage: string;
  action?: { path: string; label: string };
}

const VIEWS: readonly ViewSpec[] = [
  {
    path: '/app/overview',
    segment: 'overview',
    label: 'Overview',
    eyebrow: 'Step 1 · The portfolio',
    heading: 'Overview',
    intro: 'The portfolio in one read: contribution, net revenue and capital at cost.',
    emptyTitle: 'No data yet',
    emptyMessage:
      'Import product and transaction CSVs and this view shows the portfolio contribution, net revenue and the capital tied up in stock, plus how many SKUs are profitable. Nothing is forecast — every figure comes from the rows you imported.',
    action: { path: '/app/import', label: 'Go to Import' },
  },
  {
    path: '/app/import',
    segment: 'import',
    label: 'Import',
    eyebrow: 'Step 2 · Your data',
    heading: 'Import',
    intro: 'Load the catalogue and the transactions the figures are computed from.',
    emptyTitle: 'Nothing imported yet',
    emptyMessage:
      'Choose a CSV with the documented columns, or load the built-in synthetic sample to explore the tool. Files are read as text and are capped at 5 MB and 20,000 data rows; a dry run validates without saving.',
  },
  {
    path: '/app/profitability',
    segment: 'profitability',
    label: 'Profitability',
    eyebrow: 'Step 3 · Realised',
    heading: 'Profitability',
    intro: 'Contribution per SKU, with a drill-down to every contributing line.',
    emptyTitle: 'No transactions yet',
    emptyMessage:
      'Once transactions are imported this view lists each SKU with its contribution, and a drill-down shows the individual lines that add up to the headline figure.',
  },
  {
    path: '/app/budget-lab',
    segment: 'budget-lab',
    label: 'Budget Lab',
    eyebrow: 'Step 4 · Expected',
    heading: 'Budget Lab',
    intro:
      'Two transparent allocation plans compared on expected profit, with a downside scenario.',
    emptyTitle: 'No catalogue yet',
    emptyMessage:
      'Once a catalogue is imported this view splits a budget between two greedy rules of thumb — one that ranks purely by risk-adjusted return, one that caps how much any single SKU may take — and shows how each fares under a conservative price and sell-through assumption. Both are transparent heuristics, not a mathematical answer.',
    action: { path: '/app/import', label: 'Go to Import' },
  },
  {
    path: '/app/methodology',
    segment: 'methodology',
    label: 'Methodology',
    eyebrow: 'Reference',
    heading: 'Methodology',
    intro: 'How every figure is computed, and what the numbers cannot tell you.',
    emptyTitle: 'Methodology not written yet',
    emptyMessage:
      'This view will set out the profit terms in the order they are applied — net revenue, product cost, fees, GST on fees and contribution — together with the disclaimer and the limitation of the downside scenario.',
  },
];

/**
 * One 16 px stroke icon per route, drawn in `currentColor` so the active and inactive
 * states colour it themselves. Inline SVG on purpose: `plans/TECH_STACK.md` §3 specifies
 * inline SVG and no icon package. Each is `aria-hidden`: the nav item's own text carries
 * the meaning.
 */
const NAV_ICONS: Record<string, ReactNode> = {
  '/app/overview': (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2.5" y="2.5" width="6" height="6" rx="1.5" />
      <rect x="11.5" y="2.5" width="6" height="6" rx="1.5" />
      <rect x="2.5" y="11.5" width="6" height="6" rx="1.5" />
      <rect x="11.5" y="11.5" width="6" height="6" rx="1.5" />
    </svg>
  ),
  '/app/import': (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 2.5v9" />
      <path d="M6.5 8 10 11.5 13.5 8" />
      <path d="M2.5 13.5v2.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-2.5" />
    </svg>
  ),
  '/app/profitability': (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 17v-3" />
      <path d="M10 17V9" />
      <path d="M16 17V3.5" />
    </svg>
  ),
  '/app/budget-lab': (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 3v13.5" />
      <path d="M5.5 16.5h9" />
      <path d="M3.5 7h13" />
      <path d="M3.5 7 5.5 11.5h-4L3.5 7Z" />
      <path d="M16.5 7 18.5 11.5h-4L16.5 7Z" />
    </svg>
  ),
  '/app/methodology': (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11.5 2.5H5.5A1.5 1.5 0 0 0 4 4v12a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 16 16V7l-4.5-4.5Z" />
      <path d="M11.5 2.5V7H16" />
      <path d="M7 11h6" />
      <path d="M7 14h4" />
    </svg>
  ),
};

/**
 * One route body. It renders the view's own empty state, which is the honest thing to
 * show before that view has a data layer.
 */
function ViewBody({ spec }: { spec: ViewSpec }) {
  return (
    <section key={spec.path} className="enter space-y-7">
      <Reveal className="space-y-2.5 border-b border-rule pb-6">
        <p className="eyebrow">{spec.eyebrow}</p>
        <h1 className="text-display text-navy sm:text-display-lg">{spec.heading}</h1>
        <p className="max-w-[68ch] text-body text-muted">{spec.intro}</p>
      </Reveal>

      <Reveal delay={0.07}>
        <EmptyState
          title={spec.emptyTitle}
          message={spec.emptyMessage}
          action={
            spec.action ? (
              <Link
                to={spec.action.path}
                className="lift inline-flex min-h-[44px] items-center rounded bg-teal px-4 text-sm font-semibold text-white shadow-card transition-colors duration-fast ease-standard hover:bg-teal-dark hover:shadow-glow"
              >
                {spec.action.label}
              </Link>
            ) : undefined
          }
        />
      </Reveal>
    </section>
  );
}

/** Liveness of the local API, read through the typed client. */
function BackendStatus() {
  const { state, reload } = useApi<Health>('/health', NEVER_EMPTY);

  if (state.status === 'loading') {
    return <Loading label="Checking the backend…" rows={1} variant="inline" />;
  }

  if (state.status === 'ready') {
    return (
      <p className="flex items-center gap-2 text-caption font-medium text-gain">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-gain" />
        Backend reachable · v{state.data.version}
      </p>
    );
  }

  if (state.status === 'empty') {
    return null;
  }

  return <ErrorState title="Backend not reachable" detail={state.detail} onRetry={reload} />;
}

/** The demo-data marker, shown only once the catalogue actually has rows (AT-10.2). */
function DemoDataMarker() {
  const { state } = useApi<Product[]>('/products', NO_PRODUCTS);
  return state.status === 'ready' ? <DemoBadge /> : null;
}

/** Routes with a real view body; anything unknown still renders the placeholder. */
function routeElement(view: ViewSpec) {
  if (view.segment === 'overview') {
    return <Overview />;
  }
  if (view.segment === 'import') {
    return <Import />;
  }
  if (view.segment === 'profitability') {
    return <Profitability />;
  }
  if (view.segment === 'budget-lab') {
    return <BudgetLab />;
  }
  if (view.segment === 'methodology') {
    return <Methodology />;
  }
  return <ViewBody spec={view} />;
}

/** Routing: the public landing page at `/`, the shell above it at `/app/*`, and anything
 *  unrecognised back to the landing page. */
export default function App() {
  // Mounted once for the whole app, so the landing page scrolls the same way the views do.
  useSmoothScroll();

  return (
    <>
      {/* Above the routes rather than inside them: one bar for the whole document, on the
          landing and in the app alike. */}
      <ScrollProgress />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app/*" element={<AppShell />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

/**
 * The ambient bloom, drifting against the page as it scrolls.
 *
 * A wrapper is what moves, not the bloom itself: `.app-aurora` carries the slow `drift`
 * keyframe, and a CSS animation outranks an inline transform, so translating the element the
 * animation is on would do nothing. The wrapper is fixed to the viewport and translated a
 * little further than the content travels, which is enough to read as depth. Transform only,
 * and the plain, unmoving bloom under reduced motion.
 */
function AmbientBloom() {
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 1400], [0, -72]);

  if (useReducedMotion()) {
    return <div aria-hidden="true" className="app-aurora" />;
  }

  return (
    <motion.div aria-hidden="true" style={{ y }} className="app-aurora-frame">
      <div className="app-aurora" />
    </motion.div>
  );
}

/** The application shell: the sidebar frame and the app-wide readouts. */
function AppShell() {
  const { state: assumptions } = useApi<Assumptions>('/assumptions', NEVER_EMPTY);
  const { pathname } = useLocation();

  // The top bar names the step the reader is in; the view repeats it above its heading.
  const current = VIEWS.find((view) => view.path === pathname);

  return (
    <div className="relative min-h-screen bg-canvas">
      <AmbientBloom />

      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:rounded focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>

      <div className="relative z-[1] mx-auto flex w-full max-w-[1400px] flex-col lg:flex-row">
        <aside className="border-b border-navy-soft bg-navy bg-gradient-to-b from-navy-soft/95 to-navy-deep px-5 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:shrink-0 lg:overflow-y-auto lg:border-b-0 lg:border-r lg:px-6 lg:py-9">
          <div className="min-w-0">
            <Logo className="h-7 text-white" accentClassName="text-teal-wash" />
            <p className="mt-1.5 text-eyebrow font-semibold uppercase text-white/55">
              Decision support
            </p>
          </div>

          {/* One 44 px row per section. The active one is marked three ways at once: a
              light rail on the leading edge, a lifted background and white text — so the
              state never rests on hue alone. The focus ring is white, because teal on
              navy does not reach 3:1. */}
          <nav aria-label="Sections" className="mt-6 flex flex-wrap gap-1 lg:mt-9 lg:flex-col">
            {VIEWS.map((view) => (
              <NavLink
                key={view.path}
                to={view.path}
                className={({ isActive }) =>
                  `flex min-h-[44px] items-center gap-2.5 rounded-r border-l-2 pl-2.5 pr-3 text-sm font-medium transition-colors duration-fast ease-standard focus-visible:ring-white focus-visible:ring-offset-navy ${
                    isActive
                      ? 'border-teal-wash bg-white/[0.07] text-white'
                      : 'border-transparent text-white/60 hover:border-white/20 hover:bg-white/[0.04] hover:text-white'
                  }`
                }
              >
                {NAV_ICONS[view.path]}
                {view.label}
              </NavLink>
            ))}
          </nav>

          <p className="mt-8 hidden border-t border-navy-soft pt-4 text-micro text-white/40 lg:block">
            Local-only. Synthetic or owner-authorised data, and no connection to any
            marketplace.
          </p>
        </aside>

        <main id="content" className="min-w-0 flex-1 scroll-mt-24 px-5 py-7 lg:px-10 lg:py-12">
          {/* Full-bleed and slightly translucent from `lg` up, so the readouts stay
              readable while a long table scrolls under them. At phone width it stays in
              the flow: a sticky bar that wraps to three lines would eat the viewport. */}
          <div className="mb-7 flex flex-wrap items-center justify-between gap-x-5 gap-y-3 border-b border-rule pb-4 lg:sticky lg:top-0 lg:z-20 lg:-mx-10 lg:mb-9 lg:bg-canvas/85 lg:px-10 lg:py-3.5 lg:backdrop-blur">
            <p className="eyebrow">{current?.eyebrow ?? 'ArbitrageIQ'}</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <DemoDataMarker />
              <BackendStatus />
            </div>
          </div>

          <Routes>
            {/* `/app` and anything unmatched inside the shell land on the first view. */}
            <Route index element={<Navigate to="/app/overview" replace />} />
            {VIEWS.map((view) => (
              <Route key={view.path} path={view.segment} element={routeElement(view)} />
            ))}
            <Route path="*" element={<Navigate to="/app/overview" replace />} />
          </Routes>

          <footer className="card mt-12 px-5 py-5">
            <h2 className="eyebrow">Readouts</h2>
            <div className="mt-3 space-y-4">
              <AssumptionPanel
                assumptions={assumptions.status === 'ready' ? assumptions.data : null}
              />
              <p className="border-t border-rule pt-4 text-micro text-muted">
                Local tool. Synthetic or owner-authorised data only, and no connection to any
                marketplace.
              </p>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
