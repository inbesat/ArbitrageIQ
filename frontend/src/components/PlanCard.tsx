/**
 * One Budget Lab plan (task T16; `plans/PRD.md` §4.4).
 *
 * A plan is a transparent heuristic, never a mathematical answer, so the card shows the
 * rule it followed, what it spends, what it leaves and what the assumptions imply it
 * earns — with the word "expected" on the figure that rests on an assumption
 * (`plans/BUSINESS_RULES.md` §11.1).
 *
 * Two consequences of that honesty rule live here. The card carries its own methodology
 * affordance, so every figure in it has one next to it (AT-10.6). And the breakdown lists
 * only the lines that actually received capital: the API answers with a zero-quantity line
 * for every candidate it did not buy, so a `qty` of zero is not an allocation and the
 * "buys nothing" message would otherwise never be reachable.
 *
 * The layout follows the operator's Budget Lab mockup: an accent band, a plan chip, a 2-up
 * metric grid, a contribution banner, then the funded lines. The mockup's invented panels —
 * a risk-profile table, target-sell/salvage/ROI micro-rows and a status pill naming a
 * concentration verdict — are deliberately absent, because no endpoint returns those
 * values and a label the backend did not compute is not something this app may show.
 *
 * The proportion bar is sized from the capital strings by integer division: digits are
 * scaled to whole paise with `BigInt` and turned into a percentage string, so no money
 * value ever passes through a float or a numeric conversion (`plans/TECH_STACK.md` §3.1).
 * The bar carries no transition: it stands in for an amount, and an amount that eases
 * from one width to another reads as a value changing.
 */
import { Link } from 'react-router-dom';

import type { Plan } from '../api/types';
import { MoneyCell } from './MoneyCell';

/**
 * `part` as a whole-percent string of `whole`, e.g. `'3000.00'` of `'10000.00'` -> `'30%'`.
 *
 * Digits only: sign dropped, fraction padded or trimmed to two places, then integer
 * division on `BigInt`. A bar does not need more resolution than one percent, and working
 * in digits keeps the guarantee that no rupee value is ever a float.
 */
function sharePercent(part: string, whole: string): string {
  const scale = (value: string): bigint => {
    const digits = value.startsWith('-') ? value.slice(1) : value;
    const [whole_, fraction = ''] = digits.split('.');
    return BigInt((whole_ || '0') + fraction.padEnd(2, '0').slice(0, 2));
  };
  const total = scale(whole);
  if (total === 0n) {
    return '0%';
  }
  return `${(scale(part) * 100n) / total}%`;
}

export function PlanCard({
  plan,
  tag,
  budget,
  names,
}: {
  plan: Plan;
  /** The plan's chip: `Plan A` for the ROI-first rule, `Plan B` for the capped one. */
  tag: string;
  /** The echoed working budget, only used as the denominator of the allocated bar. */
  budget: string;
  /** sku -> display name, from the catalogue. A SKU missing here shows its own code. */
  names: Map<string, string>;
}) {
  // `B3` in `plans/BUSINESS_RULES.md` §11.4: a bought line has `qty` of at least the MOQ,
  // so `qty > 0` is exactly "this SKU received capital".
  const funded = plan.lines.filter((line) => line.qty > 0);

  return (
    <article className="card relative flex h-full flex-col overflow-hidden p-5 pt-6 sm:p-6 sm:pt-7">
      {/* The mockup's 1 px accent band, from the two existing tokens rather than its hexes. */}
      <span
        aria-hidden="true"
        className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${
          tag === 'Plan A' ? 'from-teal to-gain' : 'from-navy-soft to-teal'
        }`}
      />

      <div className="min-w-0 border-b border-rule pb-3.5">
        <span className="rounded border border-teal/30 bg-teal-wash px-1.5 py-0.5 font-mono text-micro font-semibold uppercase tracking-widest text-teal-dark">
          {tag}
        </span>
        <h3 className="mt-1.5 text-title font-semibold text-navy">{plan.label}</h3>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded border border-rule bg-canvas p-3">
          <dt className="font-mono text-micro uppercase tracking-wider text-muted">
            Capital allocated
          </dt>
          <dd className="mt-0.5 text-title font-semibold">
            <MoneyCell value={plan.capital_used} />
          </dd>
          <div aria-hidden="true" className="mt-2 h-1 w-full overflow-hidden rounded-full bg-rule">
            <div
              className="h-full rounded-full bg-teal"
              style={{ width: sharePercent(plan.capital_used, budget) }}
            />
          </div>
        </div>
        <div className="rounded border border-rule bg-canvas p-3">
          <dt className="font-mono text-micro uppercase tracking-wider text-muted">Budget unused</dt>
          <dd className="mt-0.5 text-title font-semibold">
            <MoneyCell value={plan.budget_remaining} />
          </dd>
        </div>
      </dl>

      <div className="mt-3 rounded border border-teal/25 bg-teal-wash px-4 py-4">
        <p className="eyebrow text-teal-dark">Expected contribution</p>
        <p className="mt-1 text-figure-sm font-semibold">
          <MoneyCell value={plan.expected_contribution} />
        </p>
        <p className="mt-1.5 text-micro text-teal-dark">
          Expected, not realised: it rests on the sell-through and salvage values in the controls.
        </p>
      </div>

      <p className="eyebrow mt-5">Allocation breakdown</p>

      {funded.length === 0 ? (
        <p className="mt-2 rounded border border-rule bg-canvas px-3.5 py-3 text-caption text-muted">
          This plan buys nothing. Either no SKU has positive per-unit economics under these
          assumptions, or the smallest order the rule could place costs more than the whole
          budget. Raise the budget, or revisit the sell-through and salvage values above.
        </p>
      ) : (
        <ul className="mt-2.5 space-y-3">
          {funded.map((line) => (
            <li key={line.sku}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-caption">
                <span className="flex min-w-0 flex-wrap items-baseline gap-2">
                  <span className="rounded border border-rule bg-canvas px-1.5 py-0.5 font-mono text-micro font-semibold uppercase tracking-wide text-navy">
                    {line.sku}
                  </span>
                  <span className="min-w-0 font-medium text-navy">
                    {names.get(line.sku) ?? line.sku}
                  </span>
                </span>
                <span className="tnum shrink-0 font-mono text-muted">{line.qty} units</span>
              </div>
              <div
                aria-hidden="true"
                className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-rule"
              >
                <div
                  className="h-full rounded-full bg-teal"
                  style={{ width: sharePercent(line.capital, plan.capital_used) }}
                />
              </div>
              <div className="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 text-micro">
                <span className="text-muted">
                  Expected contribution <MoneyCell value={line.expected_contribution} />
                </span>
                {line.assumed ? (
                  <span className="font-semibold uppercase tracking-wide text-warn">
                    assumed sell-through
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* `mt-auto` pins the footnote to the bottom of the shorter card, so the two plans
          in a row end on the same line. */}
      <div className="mt-auto pt-4">
        <p className="border-t border-rule pt-3 text-caption text-muted">
          Capital utilised{' '}
          <span className="font-medium text-navy">
            <MoneyCell value={plan.capital_used} />
          </span>{' '}
          across {funded.length} {funded.length === 1 ? 'SKU' : 'SKUs'}.
        </p>
        {/* The card's own methodology affordance: the same wording `Overview` uses next to
            each of its figures (AT-10.6). */}
        <Link
          to="/app/methodology"
          className="mt-1 inline-flex min-h-[44px] items-center text-micro font-medium text-teal underline-offset-2 hover:underline"
        >
          How this is computed
        </Link>
      </div>
    </article>
  );
}
