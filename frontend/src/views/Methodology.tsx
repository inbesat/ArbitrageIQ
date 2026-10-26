/**
 * Methodology: how the numbers are made, and what they cannot tell you (task T16;
 * `plans/PRD.md` §4.5).
 *
 * Static reference prose — no request, no figure of its own. Two strings are specification
 * text rather than this file's writing: the §7 disclaimer comes from
 * `components/Disclaimer.tsx`, and the paragraph inside the downside-scenario block is the
 * honesty statement from `plans/BUSINESS_RULES.md` §11.3, reproduced character for
 * character. The same §11.3 string travels with every simulation response and is rendered
 * verbatim by Budget Lab.
 *
 * Nothing here claims a forecast, a tax position or a connection to a marketplace
 * (`plans/BUSINESS_RULES.md` §12).
 */
import { Disclaimer } from '../components/Disclaimer';
import { Reveal } from '../components/Reveal';

/** `plans/BUSINESS_RULES.md` §11.3, verbatim. Do not reword. */
const UNIFORM_SHOCK =
  'A uniform downside shock cannot demonstrate the main benefit of diversification. Because every SKU is stressed equally, a diversified plan can score worse in the conservative scenario than a concentrated one, even though it is genuinely more resilient to a product-specific failure such as a supplier default, a stock-out, or a listing suspension. The scenario is a stress test of price and sell-through, not proof of diversification.';

/**
 * The five things people call "profit" (`plans/BUSINESS_RULES.md` §1), which is the list
 * this page exists to keep apart — not the calculation order, which is a different thing
 * and lives on Profitability.
 */
const TERMS = [
  {
    term: 'Sales value',
    status: 'Context only',
    meaning:
      'What your customers paid, GST included. The GST inside that number is collected on the government\u2019s behalf rather than earned, so it is never treated as revenue here. Sales value is shown so a figure on a marketplace statement can be recognised, and for nothing else.',
  },
  {
    term: 'Net revenue',
    status: 'Computed',
    meaning:
      'Sales value with the GST taken out, less the refunds paid on returned units. This is the only revenue figure that reaches contribution, and the one every margin percentage is measured against.',
  },
  {
    term: 'Marketplace payout',
    status: 'Context only',
    meaning:
      'What a marketplace actually transfers, after its fees, the GST on those fees and any withholding. It is shown so an actual settlement can be compared with the modelled fees. When a row carries its own settlement total, that figure replaces the model for that row and the two are never added together.',
  },
  {
    term: 'Contribution profit',
    status: 'This tool\u2019s headline figure',
    meaning:
      'Net revenue minus product cost, minus marketplace fees, minus the GST on those fees unless it is recoverable as input credit, minus advertising, minus any other charge on the line. It stops before every overhead, so it is the figure to compare one SKU with another, and never the money in your bank.',
  },
  {
    term: 'Accounting profit',
    status: 'Never computed',
    meaning:
      'Contribution less rent, salaries, depreciation, software, your own time and income tax. Nothing in this tool calculates it, and no figure it shows may be read as if it had.',
  },
] as const;

/** What the tool deliberately does not do (`plans/BUSINESS_RULES.md` §12, `PRD.md` §6). */
const LIMITS = [
  {
    heading: 'Not an optimisation',
    body: 'The two allocation plans are rules of thumb, not an optimisation. Each applies one visible rule to the catalogue in front of it and stops: no objective is solved, no plan is shown to be superior to another, and no result here is a promise about what will happen. A product that scores highly may still be capped by its minimum order quantity or by how much its supplier can supply, and the figure behind that score rests on the weakest input in the tool, the assumed sell-through.',
  },
  {
    heading: 'Not a forecast',
    body: 'No page here estimates future demand. The expected figures in Budget Lab rest on the sell-through and salvage values in its own controls, which are assumptions you can see and change.',
  },
  {
    heading: 'Not tax advice',
    body: 'The GST treatment here is a simplification for comparing one SKU with another, not a filing position. Tax collected at source and tax deducted at source are cash-flow items and are never counted as costs. Income tax on profit is not modelled at all.',
  },
  {
    heading: 'Not a marketplace integration',
    body: 'There is no seller account, no credentials, no scraping, and no order, price or listing change. Nothing leaves the machine this tool runs on except requests to its own local API.',
  },
  {
    heading: 'Not accounting profit',
    body: 'Contribution stops before overheads, your own time and income tax. It must never be read as money in the bank.',
  },
] as const;

export function Methodology() {
  return (
    <section className="enter space-y-7">
      <Reveal className="space-y-2.5 border-b border-rule pb-6">
        <p className="eyebrow">Reference</p>
        <h1 className="text-display text-navy sm:text-display-lg">Methodology</h1>
        <p className="max-w-[68ch] text-body text-muted">
          How every figure is computed, and what the numbers cannot tell you.
        </p>
      </Reveal>

      <div className="max-w-[68ch] space-y-9">
        <Reveal className="space-y-3">
          <p className="text-lead text-navy">
            This tool exists to keep five things apart that are easy to run together: what a
            customer paid, what you keep once GST and refunds are taken out, what the marketplace
            charges, what the stock cost, and what is left over.
          </p>
          <p className="text-body text-muted">
            Every rupee figure on the other pages is computed by the API from the rows you imported
            and rendered here exactly as the API sent it. The browser does not recalculate, round
            or reformat a single amount.
          </p>
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">The five profit terms</h2>
          <p className="text-body text-muted">
            These are the five numbers that all get called &ldquo;profit&rdquo;. Only two of them
            are computed here, and only one of those two is the headline.
          </p>
          <dl className="space-y-3.5">
            {TERMS.map((entry) => (
              <div key={entry.term} className="border-l-2 border-teal/30 pl-4">
                <dt className="text-body font-semibold text-navy">
                  {entry.term}
                  <span className="ml-2 align-middle text-micro font-semibold uppercase tracking-wide text-muted">
                    {entry.status}
                  </span>
                </dt>
                <dd className="mt-1 text-body text-muted">{entry.meaning}</dd>
              </div>
            ))}
          </dl>
          <p className="text-body text-navy">
            Every rupee figure derived from contribution excludes overheads and income tax. A
            contribution figure is what a sale earned after the costs that move with it, and it is
            not a bank balance.
          </p>
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">The disclaimer</h2>
          <Disclaimer />
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">A returned unit</h2>
          <p className="text-body text-navy">
            A returned unit is written off. The refund paid for it is deducted from net revenue at
            its own ex-GST refund value, and nothing of the cost behind that unit comes back: the
            fraction of landed cost recovered on a return is fixed at zero in this build.
          </p>
          <p className="text-body text-muted">
            The fees on a returned order are not reversed either. Referral, closing, shipping and
            fulfilment are charged on the units shipped, and a returned unit was shipped. The GST
            on those fees follows the same rule, and a settlement total supplied on the row is used
            as supplied rather than adjusted for the return.
          </p>
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">
            Tax collected and deducted at source
          </h2>
          <p className="text-body text-navy">
            TCS and TDS are cash-flow items, not costs. Tax collected at source and tax deducted at
            source change when money reaches you, not how much a sale earned, so neither is ever
            subtracted from a contribution figure. Both are listed with the assumptions so the
            amount withheld can be reconciled against a payout.
          </p>
          <p className="text-body text-muted">
            The cost of a sale and the cash timing of it are therefore different questions. Six
            layers exist around a single order — marketplace fees, the GST on those fees, the GST
            inside the price, TCS, TDS and income tax — and only the first three can ever reach
            contribution. Income tax on profit is not modelled at all.
          </p>
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">
            The downside scenario
          </h2>
          <p className="text-body text-navy">
            Budget Lab runs each plan twice. The base run uses the price and sell-through you set.
            The conservative run stresses every SKU, and only SKUs, by the same amount: price ×
            0.95, sell-through × 0.75, with fees recomputed at the lower price. Both results sit
            next to each other so the difference can be read rather than described.
          </p>
          {/* The same honesty statement travels with every simulation response and is shown
              on Budget Lab as a warn-tinted panel. One treatment for that content in both
              places, rather than a side-tab here and a panel there. */}
          <blockquote className="rounded-card border border-warn/40 bg-warn-wash px-4 py-3.5 text-body text-navy">
            {UNIFORM_SHOCK}
          </blockquote>
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">Assumptions</h2>
          <p>
            <span className="inline-flex rounded border border-warn/40 bg-warn-wash px-2 py-0.5 text-micro font-semibold uppercase tracking-wide text-warn">
              Illustrative demo assumption
            </span>
          </p>
          <p className="text-body text-navy">
            Every fee, rate and default is a dated record stored with the tool rather than a
            constant written into the code, and each record carries the day it took effect. The
            active set, with that effective date, is listed under Readouts at the foot of this
            page. The values that ship with this build are illustrative demo assumptions: close
            enough to reason with, and not the real rates of any marketplace, any GST slab or any
            demand figure.
          </p>
          <p className="text-body text-muted">
            The demo-data marker appears whenever the bundled synthetic sample is loaded. Read
            every figure computed from those values as a worked example, not as a statement about
            your prices.
          </p>
        </Reveal>

        <Reveal className="space-y-3">
          <h2 className="text-title font-semibold text-navy">
            What this tool is not
          </h2>
          <dl className="space-y-3.5">
            {LIMITS.map((limit) => (
              <div key={limit.heading} className="border-l-2 border-rule pl-4">
                <dt className="text-body font-semibold text-navy">{limit.heading}</dt>
                <dd className="mt-1 text-body text-muted">{limit.body}</dd>
              </div>
            ))}
          </dl>
          <p className="text-body text-muted">
            Explicitly not modelled: overheads such as rent, salaries, software, depreciation and
            your own time; income tax; and anything that would need a live marketplace connection.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
