/**
 * The per-SKU drill-down (task T16; `plans/PRD.md` §4.2, `plans/ACCEPTANCE_TESTS.md` AT-10.5).
 *
 * Reads `GET /api/v1/profit/sku/{sku}` and shows every contributing line, the twelve
 * figures on each line, and the total the backend computed for the SKU. That total is the
 * same string the table above displays as the headline, so the two are visibly equal.
 *
 * The active assumption set and the assumptions link sit next to the figures, because
 * every displayed rupee needs a methodology affordance (AT-10.6). No money value is
 * parsed, re-rounded or recomputed here (`AGENTS.md` rule 7).
 */
import { Link } from 'react-router-dom';

import { useApi } from '../api/client';
import type { BreakdownLine, Money, SkuProfit } from '../api/types';
import { ErrorState } from './ErrorState';
import { Loading } from './Loading';
import { MoneyCell } from './MoneyCell';

/** No lines is a real state for a catalogue SKU that never sold. */
const NO_LINES = (data: SkuProfit) => data.lines.length === 0;

/** The money-typed keys of a line, so reading one back is a string with no cast. */
type MoneyKey =
  | 'price_paid'
  | 'ex_gst_unit_price'
  | 'gross_revenue'
  | 'refunds'
  | 'net_revenue'
  | 'referral_fee'
  | 'fees_ex_gst'
  | 'fee_gst'
  | 'product_cost'
  | 'ads'
  | 'contribution'
  | 'profit_per_unit';

/** The twelve money fields of one line, in the order `plans/BUSINESS_RULES.md` §4 applies them. */
const LINE_FIELDS = [
  ['price_paid', 'Price paid per unit'],
  ['ex_gst_unit_price', 'Ex-GST unit price'],
  ['gross_revenue', 'Gross revenue'],
  ['refunds', 'Refunds'],
  ['net_revenue', 'Net revenue'],
  ['referral_fee', 'Referral fee'],
  ['fees_ex_gst', 'Fees, ex-GST'],
  ['fee_gst', 'GST on fees'],
  ['product_cost', 'Product cost'],
  ['ads', 'Ads'],
  ['contribution', 'Contribution'],
  ['profit_per_unit', 'Contribution per unit'],
] as const satisfies ReadonlyArray<readonly [MoneyKey, string]>;

function LineBreakdown({ line, index }: { line: BreakdownLine; index: number }) {
  return (
    <li className="rounded border border-rule bg-canvas px-4 py-3.5">
      <p className="text-caption font-semibold text-navy">
        Line {index + 1}
        <span className="ml-2 font-normal text-muted">
          {line.transaction_id ?? 'no transaction id'} · {line.net_units} units
        </span>
      </p>
      <p className="mt-0.5 text-micro text-muted">Fees from {line.fee_source}.</p>
      <dl className="mt-2.5 grid gap-x-6 gap-y-1 text-caption sm:grid-cols-2">
        {LINE_FIELDS.map(([key, label]) => (
          <div key={key} className="flex items-baseline justify-between gap-3">
            <dt className="text-muted">{label}</dt>
            <dd>
              <MoneyCell value={line[key]} />
            </dd>
          </div>
        ))}
      </dl>
    </li>
  );
}

export function SkuDrilldown({
  sku,
  headline,
  panelId,
  onClose,
}: {
  sku: string;
  /** The contribution the table shows for this SKU, straight from `/profit/reconcile`. */
  headline: Money;
  panelId: string;
  onClose: () => void;
}) {
  const { state, reload } = useApi<SkuProfit>(`/profit/sku/${encodeURIComponent(sku)}`, NO_LINES);

  return (
    <section
      id={panelId}
      aria-label={`Line breakdown for ${sku}`}
      className="card p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Line breakdown</p>
          <h2 className="mt-1 text-title font-semibold text-navy">{sku}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/app/methodology"
            className="inline-flex min-h-[44px] items-center text-caption font-medium text-teal underline-offset-2 hover:underline"
          >
            Assumptions
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-[44px] items-center rounded border border-rule bg-surface px-3 text-caption font-semibold text-navy transition-colors duration-fast ease-standard hover:border-teal hover:text-teal"
          >
            Close
          </button>
        </div>
      </div>

      {state.status === 'loading' && (
        <div className="mt-4">
          <Loading label="Adding up the lines…" rows={3} />
        </div>
      )}

      {state.status === 'error' && (
        <div className="mt-4">
          <ErrorState title="That SKU could not be read" detail={state.detail} onRetry={reload} />
        </div>
      )}

      {state.status === 'empty' && (
        <p className="mt-4 rounded border border-rule bg-canvas px-4 py-3 text-body text-muted">
          No transaction lines were recorded for this SKU, so there is no breakdown to show.
        </p>
      )}

      {state.status === 'ready' && (
        <>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded border border-teal/25 bg-teal-wash px-4 py-3">
              <dt className="eyebrow text-teal-dark">Total of the lines</dt>
              <dd className="mt-1 text-figure-sm font-semibold">
                <MoneyCell value={state.data.totals.contribution} />
              </dd>
            </div>
            <div className="rounded border border-rule bg-canvas px-4 py-3">
              <dt className="eyebrow">Headline in the table</dt>
              <dd className="mt-1 text-figure-sm font-semibold">
                <MoneyCell value={headline} />
              </dd>
            </div>
          </dl>

          <p className="mt-3 text-caption text-muted">
            {state.data.totals.contribution === headline
              ? `Both figures come from the same computation: the total of ${state.data.totals.line_count} ${
                  state.data.totals.line_count === 1 ? 'line' : 'lines'
                } is the contribution shown for this SKU in the table above.`
              : 'The two figures are shown side by side because they are not the same value. Reload the view to reconcile them.'}
          </p>

          <h3 className="eyebrow mt-5">Every line, with the figures the API returns</h3>
          <ul className="mt-2.5 space-y-3">
            {state.data.lines.map((line, index) => (
              <LineBreakdown
                key={line.transaction_id ?? `${sku}-${index}`}
                line={line}
                index={index}
              />
            ))}
          </ul>
          <p className="mt-3 text-caption text-muted">
            Contribution excludes overheads and income tax. The assumption set in force is the one
            the backend recorded for these lines.
          </p>
        </>
      )}
    </section>
  );
}
