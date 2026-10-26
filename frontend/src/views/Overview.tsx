/**
 * Overview: the portfolio in one read (task T14; `plans/PRD.md` §4.1).
 *
 * One decision, not a dashboard — no chart, no trend, no forecast. Every figure
 * arrives from `/profit/reconcile` as a decimal string and is rendered by
 * `MoneyCell`; nothing here is parsed or calculated (`AGENTS.md` rule 7).
 */
import { Link } from 'react-router-dom';

import { useApi } from '../api/client';
import type { Money, Reconcile } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Loading } from '../components/Loading';
import { MoneyCell } from '../components/MoneyCell';
import { Reveal } from '../components/Reveal';

/**
 * `/profit/reconcile` carries two portfolio totals beyond its base shape: the net
 * revenue and the capital tied up at cost, added for this view. Declared locally so
 * the shared `Reconcile` type stays exactly what the rest of the app reads.
 */
type ReconcilePayload = Reconcile & {
  portfolio_net_revenue: Money;
  portfolio_capital_at_cost: Money;
};

// Module-level so `useApi` does not re-run on every render.
const NO_SKUS = (data: ReconcilePayload) => Object.keys(data.per_sku).length === 0;

function Figure({ label, value }: { label: string; value: Money }) {
  return (
    <div className="card flex h-full flex-col px-5 py-4">
      <p className="eyebrow">{label}</p>
      <p className="tnum mt-2 text-figure font-semibold text-navy">
        <MoneyCell value={value} />
      </p>
      {/* `mt-auto` lines the three affordances up along the bottom of the row, however
          differently the labels above wrap. */}
      <Link
        to="/app/methodology"
        className="mt-auto inline-flex min-h-[44px] items-center pt-1 text-micro font-medium text-teal underline-offset-2 hover:underline"
      >
        How this is computed
      </Link>
    </div>
  );
}

export function Overview() {
  const { state, reload } = useApi<ReconcilePayload>('/profit/reconcile', NO_SKUS);

  const header = (
    <Reveal className="space-y-2.5 border-b border-rule pb-6">
      <p className="eyebrow">Step 1 · The portfolio</p>
      <h1 className="text-display text-navy sm:text-display-lg">Overview</h1>
      <p className="max-w-[68ch] text-body text-muted">
        The portfolio in one read: contribution, net revenue and capital at cost.
      </p>
    </Reveal>
  );

  if (state.status === 'loading') {
    return (
      <section className="space-y-7">
        {header}
        <Loading label="Reconciling the portfolio…" rows={3} variant="cards" />
      </section>
    );
  }

  if (state.status === 'error') {
    return (
      <section className="space-y-7">
        {header}
        <ErrorState title="The portfolio could not be read" detail={state.detail} onRetry={reload} />
      </section>
    );
  }

  if (state.status === 'empty') {
    return (
      <section className="space-y-7">
        {header}
        <Reveal delay={0.07}>
          <EmptyState
            title="No data yet"
            message="Import product and transaction CSVs and this view shows the portfolio contribution, net revenue and the capital tied up in stock, plus how many SKUs are profitable. Nothing is forecast — every figure comes from the rows you imported."
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

  const data = state.data;
  const entries = Object.entries(data.per_sku);
  // A sign test on the string the backend sent: never a numeric conversion, never a parse.
  const lossMaking = entries.filter(([, contribution]) => contribution.startsWith('-')).length;
  const profitable = entries.length - lossMaking;

  return (
    <section className="enter space-y-7">
      {header}

      <div className="grid gap-4 sm:grid-cols-3">
        <Reveal className="h-full">
          <Figure label="Portfolio contribution" value={data.portfolio_total} />
        </Reveal>
        <Reveal className="h-full" delay={0.05}>
          <Figure label="Net revenue" value={data.portfolio_net_revenue} />
        </Reveal>
        <Reveal className="h-full" delay={0.1}>
          <Figure label="Capital at cost" value={data.portfolio_capital_at_cost} />
        </Reveal>
      </div>

      <Reveal delay={0.07} className="space-y-4">
        <div className="card px-5 py-4">
          <h2 className="eyebrow">Where it stands</h2>
          <p className="mt-2 text-lead text-navy">
            {profitable} of {entries.length} {entries.length === 1 ? 'SKU' : 'SKUs'} contribute a
            positive amount
            {lossMaking > 0 ? (
              <>
                ; {lossMaking} {lossMaking === 1 ? 'SKU loses' : 'SKUs lose'} money on every unit
                sold.
              </>
            ) : (
              '.'
            )}
          </p>
          <p className="mt-2 text-caption text-muted">
            Every figure is realised from the rows you imported — nothing here is forecast.
            Contribution excludes overheads and income tax, so it is not the money in your bank
            account.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link
            to="/app/profitability"
            className="lift inline-flex min-h-[44px] items-center rounded border border-rule bg-surface px-4 text-sm font-semibold text-navy shadow-card transition-colors duration-fast ease-standard hover:border-teal hover:text-teal"
          >
            See it per SKU
          </Link>
          <Link
            to="/app/budget-lab"
            className="lift inline-flex min-h-[44px] items-center rounded border border-rule bg-surface px-4 text-sm font-semibold text-navy shadow-card transition-colors duration-fast ease-standard hover:border-teal hover:text-teal"
          >
            Spend a budget
          </Link>
        </div>
      </Reveal>
    </section>
  );
}
