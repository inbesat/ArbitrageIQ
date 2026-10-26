import type { Assumptions } from '../api/types';
import { MoneyCell } from './MoneyCell';

/**
 * The visible assumptions affordance.
 *
 * `plans/ACCEPTANCE_TESTS.md` AT-10.6 requires a methodology/assumptions affordance
 * adjacent to every displayed money figure. This panel renders the active set exactly as
 * the API returned it — the rates stay decimal strings, and the five genuinely monetary
 * values go through `MoneyCell`. Nothing here is calculated or rounded.
 *
 * Editing the set is T15's job (`plans/PHASES_DETAILED.md` §T15); T13 only displays it.
 *
 * One `<details>` for both states, so the disclosure keeps its open/closed state when the
 * assumption set arrives. The chevron is explicit: a flex `summary` drops the native
 * marker, and without it the row reads as static text.
 */

/** The §2 keys whose value is an amount of money rather than a ratio. */
const MONEY_ROWS = [
  ['zero_referral_below', 'Zero-referral below'],
  ['closing_fee', 'Closing fee per order'],
  ['shipping_fee', 'Shipping fee per order'],
  ['fulfilment_fee', 'Fulfilment fee per order'],
  ['default_budget', 'Default budget'],
] as const satisfies ReadonlyArray<readonly [keyof Assumptions, string]>;

/** The §2 keys whose value is a dimensionless ratio. */
const RATIO_ROWS = [
  ['referral_rate', 'Referral rate'],
  ['product_gst_rate', 'GST on the product'],
  ['gst_on_fees_rate', 'GST on the fees'],
  ['tcs_rate', 'TCS rate (cash flow, not a cost)'],
  ['tds_rate', 'TDS rate (cash flow, not a cost)'],
  ['default_sell_through', 'Assumed sell-through'],
  ['default_salvage', 'Assumed salvage'],
  ['default_max_share_per_sku', 'Default per-SKU cap'],
] as const satisfies ReadonlyArray<readonly [keyof Assumptions, string]>;

function Chevron() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 12 12"
      className="h-3.5 w-3.5 shrink-0 text-muted transition-transform duration-fast ease-standard group-open:rotate-180"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m2.75 4.5 3.25 3.25L9.25 4.5" />
    </svg>
  );
}

export function AssumptionPanel({ assumptions }: { assumptions: Assumptions | null }) {
  return (
    <details className="group rounded border border-rule bg-canvas px-4 py-3 text-body">
      <summary className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 font-medium text-navy">
        <span>
          {assumptions === null
            ? 'Assumptions'
            : 'Assumptions — illustrative demo values'}
        </span>
        <Chevron />
      </summary>

      {assumptions === null ? (
        <p className="mt-2 text-muted">
          No assumption set is loaded yet. The active values appear here once the backend
          is reachable.
        </p>
      ) : (
        <>
          {assumptions.note ? <p className="mt-2 text-caption text-muted">{assumptions.note}</p> : null}

          <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-1 sm:grid-cols-2">
            {MONEY_ROWS.map(([key, label]) => (
              <div key={key} className="flex items-baseline justify-between gap-4">
                <dt className="text-muted">{label}</dt>
                <dd>
                  <MoneyCell value={assumptions[key]} />
                </dd>
              </div>
            ))}

            {RATIO_ROWS.map(([key, label]) => (
              <div key={key} className="flex items-baseline justify-between gap-4">
                <dt className="text-muted">{label}</dt>
                <dd className="tnum font-medium text-navy">{assumptions[key]}</dd>
              </div>
            ))}

            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Fee GST recoverable</dt>
              <dd className="font-medium text-navy">
                {assumptions.fee_gst_recoverable ? 'Yes' : 'No'}
              </dd>
            </div>
          </dl>

          <p className="mt-3 text-caption text-muted">In force from {assumptions.effective_from}.</p>
        </>
      )}
    </details>
  );
}
