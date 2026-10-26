/**
 * The dense per-SKU table (task T16; `plans/PRD.md` §4.2).
 *
 * The catalogue supplies the name and the on-hand units; `/profit/reconcile` supplies
 * the contribution string. A SKU is listed when the API returned a contribution for it,
 * so every figure shown here is a value the backend computed (`AGENTS.md` rule 7).
 *
 * Money is never parsed. Ordering is done on the decimal strings themselves — sign
 * first, then the integer part by length, then digit by digit — so no numeric conversion
 * of any kind appears anywhere in this file (ADR-024).
 *
 * Every row is the same height and every figure is right-aligned on tabular numerals, so
 * the column of contributions can be read down. Nothing is truncated: a long name wraps
 * onto a second line and that row grows.
 */
import type { Money, Product } from '../api/types';
import { MoneyCell } from './MoneyCell';

/**
 * Compares two unsigned decimal strings (`"9.00"` vs `"10.00"`) without a numeric cast.
 * Longer integer part wins; equal lengths fall through to a lexicographic compare, which
 * is correct digit order for equally-wide integers.
 */
function compareUnsigned(a: string, b: string): number {
  const [aWhole, aFrac = ''] = a.split('.');
  const [bWhole, bFrac = ''] = b.split('.');
  // Strip leading zeros so "09" and "9" have the same width.
  const aLead = aWhole.replace(/^0+(?=\d)/, '');
  const bLead = bWhole.replace(/^0+(?=\d)/, '');
  if (aLead.length !== bLead.length) {
    return aLead.length < bLead.length ? -1 : 1;
  }
  if (aLead !== bLead) {
    return aLead < bLead ? -1 : 1;
  }
  const width = Math.max(aFrac.length, bFrac.length);
  const aTail = aFrac.padEnd(width, '0');
  const bTail = bFrac.padEnd(width, '0');
  if (aTail === bTail) {
    return 0;
  }
  return aTail < bTail ? -1 : 1;
}

/** Descending contribution order; a negative figure sorts below every positive one. */
export function compareMoneyDesc(a: string, b: string): number {
  if (a === b) {
    return 0;
  }
  // `n/a` is not a magnitude, so it sits below everything rather than comparing as text.
  if (a === 'n/a' || b === 'n/a') {
    return a === 'n/a' ? 1 : -1;
  }
  const aNegative = a.startsWith('-');
  const bNegative = b.startsWith('-');
  if (aNegative !== bNegative) {
    return aNegative ? 1 : -1;
  }
  // Descending, so a positive pair reverses the magnitude comparison; a negative pair does
  // not, because a larger magnitude is a smaller number.
  const magnitude = compareUnsigned(aNegative ? a.slice(1) : a, bNegative ? b.slice(1) : b);
  return aNegative ? magnitude : -magnitude;
}

interface Row {
  sku: string;
  name: string;
  /** On-hand units from the catalogue; null when the catalogue does not hold the SKU. */
  units: number | null;
  contribution: Money;
}

/** A downward arrow, so a negative row carries a shape as well as a colour (AT-10.12). */
function DownArrow() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 12 12"
      className="h-3 w-3 shrink-0 text-loss"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 2v8" />
      <path d="M2.75 7 6 10.25 9.25 7" />
    </svg>
  );
}

export function SkuTable({
  products,
  contributions,
  selected,
  onSelect,
  drilldownId,
}: {
  products: Product[];
  contributions: Record<string, Money>;
  /** The SKU whose drill-down is open, or null. */
  selected: string | null;
  onSelect: (sku: string) => void;
  /** id of the panel a row's button expands, for `aria-controls`. */
  drilldownId: string;
}) {
  const catalogue = new Map(products.map((product) => [product.sku, product]));

  const rows: Row[] = Object.entries(contributions)
    .map(([sku, contribution]) => {
      const product = catalogue.get(sku);
      return {
        sku,
        name: product?.name ?? '—',
        units: product ? product.current_stock : null,
        contribution,
      };
    })
    .sort((a, b) => compareMoneyDesc(a.contribution, b.contribution));

  if (rows.length === 0) {
    return null;
  }

  return (
    // `data-lenis-prevent` keeps the inertial scroller off this box, so its own scroll
    // (which is what the sticky header below rides on) stays native.
    <div className="table-scroll mt-4" data-lenis-prevent>
      <table className="w-full min-w-[38rem] border-collapse text-left text-body">
        <caption className="px-4 pb-3 text-left text-caption text-muted">
          Contribution per SKU, highest first. A negative row is marked with an arrow and the
          word loss, so it does not depend on colour.
        </caption>
        <thead className="table-head">
          <tr>
            <th scope="col" className="eyebrow px-4 py-2.5">
              SKU
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5">
              Name
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5 text-right">
              Units
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5 text-right">
              Contribution
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5 text-right">
              Lines
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const open = selected === row.sku;
            return (
              <tr
                key={row.sku}
                className={`border-b border-rule/70 transition-colors duration-fast ease-standard last:border-b-0 ${
                  open ? 'bg-teal-wash' : 'hover:bg-canvas'
                }`}
              >
                <td className="h-12 whitespace-nowrap px-4 font-semibold text-navy">{row.sku}</td>
                <td className="h-12 min-w-[12rem] px-4 text-navy">{row.name}</td>
                <td className="tnum h-12 px-4 text-right text-muted">
                  {row.units === null ? '—' : row.units}
                </td>
                <td className="h-12 px-4 text-right">
                  <span className="inline-flex items-center gap-1.5">
                    {row.contribution.startsWith('-') ? <DownArrow /> : null}
                    <MoneyCell value={row.contribution} />
                  </span>
                </td>
                <td className="h-12 px-4 text-right">
                  <button
                    type="button"
                    aria-expanded={open}
                    aria-controls={drilldownId}
                    onClick={() => onSelect(row.sku)}
                    className="inline-flex min-h-[44px] items-center justify-end rounded px-1.5 text-caption font-semibold text-teal transition-colors duration-fast ease-standard hover:text-teal-dark"
                  >
                    {open ? 'Hide lines' : 'View lines'}
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 12 12"
                      className={`ml-1.5 h-3 w-3 shrink-0 transition-transform duration-fast ease-standard ${
                        open ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="m2.75 4.5 3.25 3.25L9.25 4.5" />
                    </svg>
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
