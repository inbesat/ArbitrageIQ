/**
 * Budget Lab: two transparent plans for one budget (task T16; `plans/PRD.md` §4.4).
 *
 * Four controls, all sent as strings to `POST /api/v1/budget/simulate`; the response
 * carries the base and conservative scenarios plus the honesty statement, which is
 * rendered verbatim (`plans/BUSINESS_RULES.md` §11.3).
 *
 * The controls are inputs, not money this app computes: their text goes to the backend
 * exactly as typed, and every figure that comes back is displayed as the string it
 * arrived as (`AGENTS.md` rule 7).
 *
 * T16 added the per-control range check (`RULES` below) and the §7 disclaimer, which is
 * rendered here beside the assumed controls from the single source in
 * `components/Disclaimer.tsx`.
 *
 * The layout now follows the operator's Budget Lab mockup: a hero, three headline
 * banners, a grid of parameter tiles, the two plans and the stressed pair, then the
 * disclosure. What is NOT ported is the mockup's browser-side arithmetic and its
 * invented engine: no percentage is divided out here, no delta or "premium" is
 * computed, and the banner that reports the higher of the two plans is a pick between
 * two decimal strings (`largerDecimal` below), not a subtraction.
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { apiFetch, useApi } from '../api/client';
import type { ApiState } from '../api/client';
import type { Product, Simulation } from '../api/types';
import { Disclaimer } from '../components/Disclaimer';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Loading } from '../components/Loading';
import { MoneyCell } from '../components/MoneyCell';
import { PlanCard } from '../components/PlanCard';
import { Reveal } from '../components/Reveal';

// Module-level so `useApi` does not re-run on every render.
const NO_PRODUCTS = (products: Product[]) => products.length === 0;

/**
 * The control names the API expects, each with its label, its hint, whether it is assumed,
 * and the range it accepts.
 *
 * `min` and `max` are PLAIN TEXT restating the range `RULES` enforces, written here so the
 * tile can show them without the browser deriving anything (`AGENTS.md` rule 7).
 */
const CONTROLS = [
  {
    key: 'budget',
    label: 'Working budget',
    hint: 'The rupees you are willing to tie up in stock.',
    assumed: true,
    min: '0.00',
    max: 'no stated maximum',
  },
  {
    key: 'sell_through',
    label: 'Sell-through rate',
    hint: 'Fraction of the units bought that you expect to sell, between 0 and 1.',
    assumed: true,
    min: '0',
    max: '1',
  },
  {
    key: 'salvage',
    label: 'Salvage recovery',
    hint: 'Fraction of landed cost recovered on an unsold unit, between 0 and 1.',
    assumed: true,
    min: '0',
    max: '1',
  },
  {
    key: 'max_share_per_sku',
    label: 'Concentration cap',
    hint: 'Largest share of the budget any one SKU may take, in (0, 1]. Constrains Plan B only.',
    assumed: false,
    min: 'above 0',
    max: '1',
  },
] as const;

type ControlKey = (typeof CONTROLS)[number]['key'];
type Controls = Record<ControlKey, string>;

/**
 * Range checks for the four controls.
 *
 * These are LEXICAL tests on the exact text the API will be sent, not numeric ones: the
 * frontend never converts a money or ratio string into a number (`AGENTS.md` rule 7,
 * `plans/TECH_STACK.md` §3.1), so each bound is written as the shape the text must have.
 *
 * sell-through and salvage are fractions in [0, 1]; the concentration cap is in (0, 1];
 * the budget is a plain non-negative amount.
 */
const WITHIN_ZERO_ONE = /^(?:0(?:\.\d+)?|\.\d+|1(?:\.0+)?)$/;
const ABOVE_ZERO_UP_TO_ONE = /^(?:0?\.\d*[1-9]\d*|1(?:\.0+)?)$/;
const AMOUNT = /^\d+(?:\.\d+)?$/;

const RULES: Record<ControlKey, { pattern: RegExp; message: string }> = {
  budget: {
    pattern: AMOUNT,
    message: 'The budget must be an amount, for example 50000.00.',
  },
  sell_through: {
    pattern: WITHIN_ZERO_ONE,
    message: 'Sell-through must be between 0 and 1, for example 0.80.',
  },
  salvage: {
    pattern: WITHIN_ZERO_ONE,
    message: 'Salvage must be between 0 and 1, for example 0.50.',
  },
  max_share_per_sku: {
    pattern: ABOVE_ZERO_UP_TO_ONE,
    message: 'The concentration cap must be above 0 and no more than 1, for example 0.40.',
  },
};

const DEFAULTS: Controls = {
  budget: '50000.00',
  sell_through: '0.80',
  salvage: '0.50',
  max_share_per_sku: '0.40',
};

/** How long the controls settle before a request goes out, so typing is not a request each. */
const SETTLE_MS = 250;

const CONSERVATIVE_CAPTION = 'price × 0.95 · sell-through × 0.75 · fees recomputed';

/**
 * Which of two decimal strings is the larger: `'a'` or `'b'`, `'a'` on a tie.
 *
 * This is a pick between two strings, not arithmetic on money: each value is re-shaped
 * into the same digits and the two are compared as text, so neither ever becomes a number
 * (`AGENTS.md` rule 7). Sign is settled first — every positive beats every negative — and
 * the zero padding makes values of different digit counts comparable.
 *
 * shortcut: assumes the backend's `-?\d+\.\d{2}` form and magnitudes below 10^16; upgrade
 * to a real decimal comparison if the wire format widens.
 */
function largerDecimal(a: string, b: string): 'a' | 'b' {
  const negative = a.startsWith('-');
  if (negative !== b.startsWith('-')) {
    return negative ? 'b' : 'a';
  }
  const magnitude = (value: string): string => {
    const [whole = '', fraction = ''] = (negative ? value.slice(1) : value).split('.');
    return `${whole.padStart(16, '0')}.${fraction.padEnd(4, '0')}`;
  };
  const higher = magnitude(a) >= magnitude(b) ? 'a' : 'b';
  // Written as a sign-and-magnitude comparison so no rupee figure is ever negated in
  // arithmetic. Two losses still have a larger and a smaller one, and the pick flips.
  return negative ? (higher === 'a' ? 'b' : 'a') : higher;
}

/** One headline figure. The badge is a static word; nothing in it is derived. */
function KpiBanner({
  label,
  badge,
  children,
}: {
  label: string;
  badge: string;
  children: ReactNode;
}) {
  return (
    <div className="card p-4 sm:p-5">
      <p className="font-mono text-micro font-semibold uppercase tracking-widest text-muted">
        {label}
      </p>
      <div className="mt-1.5 flex flex-wrap items-baseline gap-2">
        <p className="text-figure-sm font-semibold">{children}</p>
        <span className="rounded border border-teal/30 bg-teal-wash px-1.5 py-0.5 font-mono text-micro font-semibold uppercase tracking-wide text-teal-dark">
          {badge}
        </span>
      </div>
    </div>
  );
}

/**
 * The three headline banners.
 *
 * Nothing here subtracts, divides or derives a percentage: one figure is the echoed
 * budget, one is the echoed cap, and the middle one is the higher of the two plans'
 * expected contribution with the plan it came from named beside it — no delta, no
 * premium, no yield.
 */
function KpiBanners({ data }: { data: Simulation }) {
  const higher = largerDecimal(
    data.base.plan_a.expected_contribution,
    data.base.plan_b.expected_contribution,
  );

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <KpiBanner label="Working budget" badge="Deployed">
        <MoneyCell value={data.budget} />
      </KpiBanner>
      <KpiBanner
        label="Highest expected contribution"
        badge={higher === 'a' ? 'Plan A' : 'Plan B'}
      >
        <MoneyCell
          value={
            higher === 'a'
              ? data.base.plan_a.expected_contribution
              : data.base.plan_b.expected_contribution
          }
        />
      </KpiBanner>
      <KpiBanner label="Concentration cap" badge="Plan B only">
        <span className="tnum">{data.max_share_per_sku}</span>
      </KpiBanner>
    </div>
  );
}

export function BudgetLab() {
  const products = useApi<Product[]>('/products', NO_PRODUCTS);
  const [controls, setControls] = useState<Controls>(DEFAULTS);
  // The last value that passed its check, per control. An out-of-range entry is reverted to
  // this on blur, so a bad value is never left in the box and never sent to the API
  // (`plans/ACCEPTANCE_TESTS.md` AT-10.10).
  const [kept, setKept] = useState<Controls>(DEFAULTS);
  const [rejection, setRejection] = useState<{ key: ControlKey; message: string } | null>(null);
  const [simulation, setSimulation] = useState<ApiState<Simulation>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  const noCatalogue = products.state.status === 'empty';
  const complete = CONTROLS.every((control) => controls[control.key].trim() !== '');
  const inRange = CONTROLS.every((control) => RULES[control.key].pattern.test(controls[control.key]));

  const changeControl = (key: ControlKey, text: string) => {
    setControls((current) => ({ ...current, [key]: text }));
    setRejection(
      text.trim() === '' || RULES[key].pattern.test(text)
        ? null
        : { key, message: RULES[key].message },
    );
  };

  const settleControl = (key: ControlKey) => {
    const text = controls[key];
    if (text.trim() === '') {
      return;
    }
    if (RULES[key].pattern.test(text)) {
      setKept((current) => ({ ...current, [key]: text }));
      return;
    }
    // Reject it, say why, and put the previous value back.
    setControls((current) => ({ ...current, [key]: kept[key] }));
    setRejection({
      key,
      message: `${RULES[key].message} The previous value, ${kept[key]}, was kept.`,
    });
  };

  useEffect(() => {
    if (!complete || !inRange || noCatalogue) {
      return;
    }

    let live = true;
    // Settle first, then request; the previous result stays on screen while one is in
    // flight, so a keystroke never blanks the panel.
    const handle = window.setTimeout(() => {
      void apiFetch<Simulation>('/budget/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(controls),
      }).then((next) => {
        if (live) {
          setSimulation(next);
        }
      });
    }, SETTLE_MS);

    return () => {
      live = false;
      window.clearTimeout(handle);
    };
  }, [controls, complete, inRange, noCatalogue, attempt]);

  const names = new Map(
    (products.state.status === 'ready' ? products.state.data : []).map((product) => [
      product.sku,
      product.name,
    ]),
  );

  const header = (
    <Reveal className="space-y-3 border-b border-rule pb-8">
      <p className="eyebrow text-teal">Budget Lab / Portfolio capital allocation</p>
      <h1 className="text-display text-navy sm:text-display-lg">Put your budget to work. See the trade-offs.</h1>
      <p className="max-w-[68ch] text-body text-muted">
        Compare two transparent buying rules using your catalogue, then examine the same plans under a conservative price and sell-through scenario.
      </p>
    </Reveal>
  );

  if (noCatalogue) {
    return (
      <section className="enter space-y-7">
        {header}
        <Reveal delay={0.07}>
          <EmptyState
            title="No catalogue yet"
            message="Once a catalogue is imported this view splits a budget between two greedy rules of thumb — one that ranks purely by risk-adjusted return, one that caps how much any single SKU may take — and shows how each fares under a conservative price and sell-through assumption. Both are transparent heuristics, not a mathematical answer."
            action={
              <Link
                to="/app/import"
                className="lift inline-flex min-h-[44px] items-center rounded bg-teal px-4 text-sm font-semibold text-white shadow-card transition-colors duration-fast ease-standard hover:bg-teal-dark hover:shadow-glow"
              >
                Go to Import
              </Link>
            }
          />
        </Reveal>
      </section>
    );
  }

  return (
    <section className="enter space-y-7">
      {header}

      {simulation.status === 'ready' && (
        <Reveal>
          <KpiBanners data={simulation.data} />
        </Reveal>
      )}

      <Reveal className="card border-t-4 border-t-teal p-5 sm:p-8">
        <p className="eyebrow text-teal">01 / Configure</p>
        <h2 className="mt-2 text-title font-semibold text-navy">Simulation parameters &amp; constraints</h2>
        <p className="mt-2 text-caption text-muted">Adjust the assumptions; the local backend recomputes both rules.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CONTROLS.map((control) => (
            <div
              key={control.key}
              className="rounded border border-rule bg-canvas p-3.5 transition-colors duration-fast ease-standard hover:border-teal/50"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label
                  htmlFor={`${control.key}-input`}
                  className="font-mono text-micro font-semibold uppercase tracking-widest text-navy"
                >
                  {control.label}
                </label>
                {control.assumed ? (
                  <span className="rounded border border-warn/40 bg-warn-wash px-1.5 py-0.5 font-mono text-micro font-semibold uppercase tracking-wide text-warn">
                    assumed
                  </span>
                ) : (
                  <span className="rounded border border-rule bg-surface px-1.5 py-0.5 font-mono text-micro font-semibold uppercase tracking-wide text-muted">
                    Plan B only
                  </span>
                )}
              </div>
              <input
                id={`${control.key}-input`}
                value={controls[control.key]}
                inputMode="decimal"
                autoComplete="off"
                aria-invalid={rejection?.key === control.key}
                aria-describedby={
                  rejection?.key === control.key
                    ? `${control.key}-hint ${control.key}-rejection`
                    : `${control.key}-hint`
                }
                onChange={(event) => changeControl(control.key, event.target.value)}
                onBlur={() => settleControl(control.key)}
                className={`tnum mt-2 min-h-[44px] w-full rounded border bg-surface px-2.5 font-mono text-body font-semibold text-navy transition-colors duration-fast ease-standard hover:border-muted/50 focus:border-teal ${
                  rejection?.key === control.key ? 'border-loss' : 'border-rule'
                }`}
              />
              <p id={`${control.key}-hint`} className="mt-1.5 text-micro text-muted">
                {control.hint}
              </p>
              {/* The mockup's MIN/MAX row, as plain text: it restates `RULES`, it is not
                  read from the box and it is never derived from a value. */}
              <p className="mt-1 flex flex-wrap items-center justify-between gap-x-2 font-mono text-micro uppercase tracking-wide text-muted">
                <span>Min {control.min}</span>
                <span>Max {control.max}</span>
              </p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-caption text-muted">
          Changing a control re-runs the simulation. The budget, sell-through and salvage values
          start from the tool's own illustrative demo assumptions; the cap is a rule of thumb, not
          a limit a marketplace imposes. A value outside its stated range is refused, the reason is
          given here, and the field keeps its previous value.
        </p>
        {!complete && (
          <p role="status" className="mt-2 text-caption font-medium text-warn">
            Every control needs a value before the simulation can run.
          </p>
        )}
        {rejection !== null && (
          <p
            id={`${rejection.key}-rejection`}
            role="status"
            className="mt-2 text-caption font-medium text-loss"
          >
            {rejection.message} Nothing was sent to the API.
          </p>
        )}
        <div className="mt-4">
          <Disclaimer />
        </div>
      </Reveal>

      {simulation.status === 'loading' && (
        <Reveal>
          <Loading label="Running both plans…" rows={4} variant="fields" />
        </Reveal>
      )}

      {simulation.status === 'error' && (
        <Reveal>
          <ErrorState
            title="The simulation did not run"
            detail={simulation.detail}
            onRetry={() => setAttempt((value) => value + 1)}
          />
        </Reveal>
      )}

      {simulation.status === 'ready' && (
        <>
          <Reveal className="card px-5 py-4">
            <h2 className="eyebrow">What was simulated</h2>
            <dl className="mt-2 flex flex-wrap gap-x-8 gap-y-1.5 text-caption">
              <div className="flex items-baseline gap-2">
                <dt className="font-mono text-muted">Budget</dt>
                <dd>
                  <MoneyCell value={simulation.data.budget} />
                </dd>
              </div>
              <div className="flex items-baseline gap-2">
                <dt className="font-mono text-muted">Sell-through</dt>
                <dd className="tnum font-medium text-navy">{simulation.data.sell_through}</dd>
              </div>
              <div className="flex items-baseline gap-2">
                <dt className="font-mono text-muted">Salvage</dt>
                <dd className="tnum font-medium text-navy">{simulation.data.salvage}</dd>
              </div>
              <div className="flex items-baseline gap-2">
                <dt className="font-mono text-muted">Concentration cap</dt>
                <dd className="tnum font-medium text-navy">{simulation.data.max_share_per_sku}</dd>
              </div>
            </dl>
            <p className="mt-2 text-caption text-muted">
              These are the values the backend ran, echoed back with the plans. Both plans are
              rules of thumb over the catalogue in front of you; neither is a mathematical answer,
              and a product scoring highly may still be limited by its minimum order quantity or
              its supplier's supply limit. Expected contribution excludes overheads and income tax.
            </p>
            <Link
              to="/app/methodology"
              className="mt-1 inline-flex min-h-[44px] items-center text-caption font-medium text-teal underline-offset-2 hover:underline"
            >
              Assumptions and method
            </Link>
          </Reveal>

          {/* Both scenarios are labelled the same way and carry the same pair of cards, so
              the base run and the stressed run can be read against each other. The labels
              are real `h2`s: the plan cards inside are `h3`s. */}
           <Reveal delay={0.04} className="space-y-4">
             <div className="border-b border-rule pb-3">
               <p className="eyebrow text-teal">02 / Compare</p>
               <h2 className="mt-1 text-title font-semibold text-navy">Base scenario comparison</h2>
               <p className="mt-1 text-caption text-muted">Same catalogue and score; Plan B also limits how much one SKU can receive.</p>
             </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <PlanCard
                plan={simulation.data.base.plan_a}
                tag="Plan A"
                budget={simulation.data.budget}
                names={names}
              />
              <PlanCard
                plan={simulation.data.base.plan_b}
                tag="Plan B"
                budget={simulation.data.budget}
                names={names}
              />
            </div>
          </Reveal>

            <Reveal delay={0.07} className="rounded-card bg-navy p-5 text-white sm:p-8">
              <p className="eyebrow text-teal-200">03 / Stress test</p>
              <h2 className="mt-1 text-title font-semibold text-white">Conservative stress scenario</h2>
            <p className="mt-3 inline-flex items-center gap-2 rounded-full border border-warn/40 bg-warn-wash px-2.5 py-1 font-mono text-micro font-semibold uppercase tracking-wide text-warn">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-warn" />
              Uniform shock · not product-specific
            </p>
            <p className="tnum mt-2 text-caption text-white/75">{CONSERVATIVE_CAPTION}</p>
            <p className="mt-2 max-w-[68ch] text-caption text-white/75">
              Every SKU is stressed by the same amount, so this scenario says what happens when
              prices and sell-through fall together — not which plan survives a failure that hits
              one product.
            </p>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <PlanCard
                plan={simulation.data.conservative.plan_a}
                tag="Plan A"
                budget={simulation.data.budget}
                names={names}
              />
              <PlanCard
                plan={simulation.data.conservative.plan_b}
                tag="Plan B"
                budget={simulation.data.budget}
                names={names}
              />
            </div>
          </Reveal>

          <Reveal
            delay={0.1}
            className="rounded-card border border-warn/40 bg-warn-wash px-5 py-5 shadow-card sm:px-6"
          >
            <h2 className="font-mono text-micro font-semibold uppercase tracking-widest text-warn">
              Methodological Disclosure &amp; Mathematical Limitation
            </h2>
            <p className="mt-2 max-w-[68ch] text-body text-navy">{simulation.data.disclosure}</p>
            <Link
              to="/app/methodology"
              className="mt-1 inline-flex min-h-[44px] items-center text-caption font-medium text-teal underline-offset-2 hover:underline"
            >
              Read the methodology
            </Link>
          </Reveal>
        </>
      )}
    </section>
  );
}
