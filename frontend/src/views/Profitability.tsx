/**
 * Profitability: what each SKU actually made (task T16; `plans/PRD.md` §4.2).
 *
 * Realised figures only, from `/profit/reconcile`, joined to the catalogue for the
 * display name and the on-hand units. Selecting a row opens `SkuDrilldown`, which reads
 * `/profit/sku/{sku}` and shows the lines that add up to the same headline figure
 * (`plans/ACCEPTANCE_TESTS.md` AT-10.5).
 *
 * This view sorts and joins strings; it never parses a money value (`AGENTS.md` rule 7).
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useApi } from '../api/client';
import type { Money, Product, Reconcile } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Loading } from '../components/Loading';
import { Reveal } from '../components/Reveal';
import { SkuDrilldown } from '../components/SkuDrilldown';
import { SkuTable } from '../components/SkuTable';

/**
 * `/profit/reconcile` carries two portfolio totals beyond the base shape. Declared
 * locally so the shared `Reconcile` type stays exactly what the rest of the app reads.
 */
type ReconcilePayload = Reconcile & {
  portfolio_net_revenue: Money;
  portfolio_capital_at_cost: Money;
};

const DRILLDOWN_ID = 'sku-line-breakdown';

// Module-level so `useApi` does not re-run on every render.
const NO_SKUS = (data: ReconcilePayload) => Object.keys(data.per_sku).length === 0;
const NO_PRODUCTS = (products: Product[]) => products.length === 0;

const SECONDARY_LINK =
  'lift inline-flex min-h-[44px] items-center rounded border border-rule bg-surface px-4 text-sm ' +
  'font-semibold text-navy shadow-card transition-colors duration-fast ease-standard hover:border-teal hover:text-teal';

export function Profitability() {
  const reconcile = useApi<ReconcilePayload>('/profit/reconcile', NO_SKUS);
  // The catalogue is only needed for the name and the units; a failure here shows the SKU
  // code instead of blanking the view, because the money is in the other response.
  const products = useApi<Product[]>('/products', NO_PRODUCTS);
  const [selected, setSelected] = useState<string | null>(null);

  const header = (
    <Reveal className="space-y-2.5 border-b border-rule pb-6">
      <p className="eyebrow">Step 3 · Realised</p>
      <h1 className="text-display text-navy sm:text-display-lg">Profitability</h1>
      <p className="max-w-[68ch] text-body text-muted">
        Contribution per SKU, with a drill-down to every contributing line.
      </p>
    </Reveal>
  );

  if (reconcile.state.status === 'loading') {
    return (
      <section className="space-y-7">
        {header}
        <Loading label="Adding up what each SKU made…" rows={6} variant="table" />
      </section>
    );
  }

  if (reconcile.state.status === 'error') {
    return (
      <section className="space-y-7">
        {header}
        <ErrorState
          title="Contribution per SKU could not be read"
          detail={reconcile.state.detail}
          onRetry={reconcile.reload}
        />
      </section>
    );
  }

  if (reconcile.state.status === 'empty') {
    return (
      <section className="space-y-7">
        {header}
        <Reveal delay={0.07}>
          <EmptyState
            title="No transactions yet"
            message="Once transactions are imported this view lists each SKU with its contribution, and a drill-down shows the individual lines that add up to the headline figure."
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

  const contributions = reconcile.state.data.per_sku;
  const catalogue = products.state.status === 'ready' ? products.state.data : [];
  const skuCount = Object.keys(contributions).length;

  return (
    <section className="enter space-y-7">
      {header}

      <Reveal className="card p-5 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="min-w-0">
            <h2 className="eyebrow">Every SKU with transactions</h2>
            <p className="mt-1 text-body text-muted">
              {skuCount} {skuCount === 1 ? 'SKU has' : 'SKUs have'} at least one line. Highest
              contribution first.
            </p>
          </div>
          <Link
            to="/app/methodology"
            className="inline-flex min-h-[44px] items-center text-caption font-medium text-teal underline-offset-2 hover:underline"
          >
            Assumptions
          </Link>
        </div>

        <SkuTable
          products={catalogue}
          contributions={contributions}
          selected={selected}
          onSelect={(sku) => setSelected((current) => (current === sku ? null : sku))}
          drilldownId={DRILLDOWN_ID}
        />

        <p className="mt-3 text-caption text-muted">
          Contribution excludes overheads and income tax: it is what the SKU leaves behind after
          GST, refunds, product cost, fees, ads and other charges, not the money in your bank
          account.
        </p>
      </Reveal>

      {selected !== null && contributions[selected] !== undefined && (
        // A mount fade, not a viewport `Reveal`: the reader asked for this panel, so it must
        // not sit at `opacity: 0` waiting to be scrolled into view — the panel opens below
        // the row that was clicked, so it usually is not in view when it mounts. `key`
        // re-plays the fade when a different SKU is picked.
        <div key={selected} className="enter">
          <SkuDrilldown
            sku={selected}
            headline={contributions[selected]}
            panelId={DRILLDOWN_ID}
            onClose={() => setSelected(null)}
          />
        </div>
      )}

      <Reveal delay={0.07} className="flex flex-wrap gap-3">
        <Link to="/app/overview" className={SECONDARY_LINK}>
          Back to the portfolio
        </Link>
        <Link to="/app/budget-lab" className={SECONDARY_LINK}>
          Spend a budget
        </Link>
      </Reveal>
    </section>
  );
}
