import { useEffect, useState, type ReactNode } from 'react';

import { Link } from 'react-router-dom';

import { Reveal } from '../components/Reveal';
import { Stagger, StaggerItem } from '../components/Stagger';
import { Logo } from '../components/Logo';
import { apiFetch, useApi, type ApiState } from '../api/client';
import type { Product, SkuProfit, SkuSimulation } from '../api/types';
import { MoneyCell } from '../components/MoneyCell';

/**
 * Landing: the public page at `/`. `App.tsx` maps it there; the five working views sit
 * under `/app/*`.
 *
 * An alternating full-bleed band page — ivory, ink, one butter band, hairline rules,
 * near-square corners, no shadows, no emoji and no illustration — describing what
 * ArbitrageIQ actually does. The copy follows `plans/PRD.md` §1–§4 and
 * `plans/BUSINESS_RULES.md` §1, §11.3, §11.4 and §12: contribution is realised from
 * imported rows, the two allocation plans are transparent rules of thumb, and a uniform
 * downside shock cannot demonstrate the main benefit of diversification.
 *
 * Fonts: the whole page inherits `font-landing`, which names Space Grotesk first and falls
 * back to the system stack (see `src/index.css`). Nothing is bundled: no font package, no
 * CDN link, no `index.html` change.
 *
 * No money is parsed or computed here (`AGENTS.md` rule 7, ADR-024). The SKU panel
 * displays backend-calculated figures; other amounts are illustrative copy.
 */

const CONTAINER = 'mx-auto w-full max-w-[1180px] px-5 md:px-8';

/** Focus rings are re-anchored per band; the global ring is teal on the app canvas. */
const FOCUS_LIGHT = 'focus-visible:ring-offset-ivory';
const FOCUS_DARK = 'focus-visible:ring-ivory focus-visible:ring-offset-ink';

const BUTTON =
  'inline-flex min-h-[44px] shrink-0 items-center justify-center gap-2 rounded-landing px-5 text-[14.5px] font-semibold transition-colors duration-fast ease-standard';
/** The one CTA, on a light band. */
const PRIMARY = `${BUTTON} bg-ink text-ivory hover:bg-ink/85 ${FOCUS_LIGHT}`;
const SECONDARY = `${BUTTON} border border-ink/25 text-ink hover:bg-ink/[0.06] ${FOCUS_LIGHT}`;

/** The header nav is the five sections the spec names; §7 is reached by scrolling. */
const SECTIONS = [
  { id: 'problem', label: 'The problem' },
  { id: 'how', label: 'How it works' },
  { id: 'simulator', label: 'SKU explorer' },
  { id: 'computes', label: 'What it computes' },
  { id: 'budget-lab', label: 'Budget Lab' },
  { id: 'faq', label: 'FAQ' },
] as const;

const CHIPS = [
  'Runs on your machine',
  'Your own CSV files',
  'No marketplace connection',
  'Illustrative demo assumptions',
  'Contribution, not accounting profit',
] as const;

/** What the shelf price hides (`plans/PRD.md` §1, `BUSINESS_RULES.md` §1). */
const LEAKAGES = [
  {
    title: 'Marketplace fees',
    body: 'A share of the price the customer paid, plus a fixed closing and shipping charge per unit. A returned order was still processed, so those fixed charges are paid on it all the same.',
  },
  {
    title: 'GST on fees',
    body: 'A tax on the marketplace\u2019s services, not on your goods. It is still a cost unless you can claim it back as input credit.',
  },
  {
    title: 'Returns',
    body: 'The revenue leaves with the unit. What was spent getting that unit out, and getting it back, stays.',
  },
  {
    title: 'Ad spend',
    body: 'Advertising sits on top of the fees and is paid whether or not the unit sells through. It rarely appears in the column that shows what a product sold for.',
  },
] as const;

/** The import-to-allocate journey (`plans/PRD.md` §3, §4.2). */
const STEPS = [
  {
    title: 'Import your CSVs',
    body: 'Two CSV files with documented columns — a catalogue and a transaction export — or the built-in synthetic sample. Files are read as text, capped at 5 MB and 20,000 data rows each, and a dry run validates without saving anything.',
  },
  {
    title: 'Set your assumptions',
    body: 'Referral, closing, shipping and fulfilment fees, the GST rate on those fees, refunds and sell-through are one editable, dated set shown next to every derived figure. Change a value and the figures move with it.',
  },
  {
    title: 'Read the profit',
    body: 'Open any SKU to see the lines behind its headline contribution figure, and that those lines sum back to it. Contribution is net revenue less product cost, fees, GST on fees, advertising and other charges, in that order.',
  },
  {
    title: 'Spend a budget',
    body: 'Enter a budget and compare two rules of thumb for splitting it across the catalogue, alongside a conservative scenario that lowers price and sell-through.',
  },
] as const;

/** The six figures the tool actually reports (`plans/PRD.md` §4.3, `BUSINESS_RULES.md` §1). */
const COMPUTES = [
  {
    title: 'Gross revenue',
    body: 'What the customer paid, GST included. The figure a marketplace reports first, and the one that is easiest to mistake for money you earned.',
  },
  {
    title: 'Net revenue',
    body: 'Gross revenue with GST removed — it was collected on the government\u2019s behalf — and the refunds on returned units taken off.',
  },
  {
    title: 'Fees',
    body: 'Referral, closing, shipping and fulfilment, each on its own line rather than as one lump deduction.',
  },
  {
    title: 'Fee GST',
    body: 'The tax charged on those marketplace fees. A cost of selling unless it comes back as input credit.',
  },
  {
    title: 'Product cost',
    body: 'What the stock cost you landed: supplier price plus inbound freight and packaging, per unit.',
  },
  {
    title: 'Contribution',
    body: 'Net revenue less product cost, fees, fee GST, advertising and other charges. The headline figure for a SKU, and the one this page and the app both stop at.',
  },
] as const;

/** The two heuristics (`plans/BUSINESS_RULES.md` §11.4). */
const PLANS = [
  {
    name: 'Plan A — ROI-first',
    body: 'Ranks every SKU by its risk-adjusted contribution per rupee of stock, then buys down the list until the budget runs out. No cap on how much any single SKU may take.',
  },
  {
    name: 'Plan B — Diversified cap',
    body: 'The same ranking and the same score, with one extra rule: no single SKU may take more than the concentration cap — 40% of the budget by default.',
  },
] as const;

/** What the tool must never be taken for (`plans/BUSINESS_RULES.md` §12, §11.1). */
const NOTS = [
  {
    title: 'Not a forecast',
    body: 'No page estimates future demand, and no model is trained on anything. The expected figures in the Budget Lab rest on the sell-through and salvage values in its own controls, which are assumptions you can see and change.',
  },
  {
    title: 'Not connected to any marketplace',
    body: 'No seller account, no credentials, and no change to an order, a price or a listing. Nothing you see here was read from a live seller account.',
  },
  {
    title: 'Not tax advice',
    body: 'The GST treatment is a simplification for comparing one SKU with another, not a filing position. Overheads — rent, salaries, software, your own time — and income tax sit outside contribution and are never modelled.',
  },
  {
    title: 'No live scraping',
    body: 'No marketplace page or API is read, by this tool or on its behalf. The only way data enters is a file you choose from your own machine, and the fee and GST values that ship with it are illustrative demo assumptions.',
  },
  {
    title: 'No automated repricing',
    body: 'Nothing here writes a price anywhere. A break-even figure is a floor to compare a price against, never an instruction to charge it, and no listing is ever edited.',
  },
  {
    title: 'The sample data is synthetic',
    body: 'The built-in sample is illustrative and generated for demonstration. Imported data must be your own or owner-authorised, and a sell-through value you type is an assumption, not a measurement of how anything sells.',
  },
] as const;

const FAQ = [
  {
    q: 'Where does the data come from?',
    a: 'From you. ArbitrageIQ imports two CSV files — a product catalogue and a transaction export — from the machine it runs on. There is also a built-in synthetic sample so you can look around before importing anything of your own.',
  },
  {
    q: 'What does it need from me?',
    a: 'A catalogue CSV and a transaction CSV with the documented columns, or nothing at all if you want to open the sample. Files are capped at 5 MB and 20,000 data rows each, and a dry run reports what would happen without writing a row. Rows that fail validation are set aside and reported with the row number, the field and a plain-English reason, never silently dropped.',
  },
  {
    q: 'Can I trust the numbers?',
    a: 'You can check them. Every SKU opens into the lines behind its headline figure and shows that those lines sum back to it, and the arithmetic is pinned by a test with a hand-derived expected value. The assumption set that produced a figure travels with it.',
  },
  {
    q: 'Can it place orders?',
    a: 'No. There is no order, price, listing or repricing operation anywhere in this project. The tool reads files and shows figures; it writes nothing back to a marketplace.',
  },
  {
    q: 'Is it connected to Amazon?',
    a: 'No. There is no seller account, no API key and no scraping anywhere in this project. The referral, closing, shipping and GST values are illustrative demo assumptions that ship with the tool and that you can edit.',
  },
  {
    q: 'What are the file limits?',
    a: 'Each CSV is read as text and capped at 5 MB and 20,000 data rows. A file over either limit is refused with a message naming the limit, rather than being partially imported.',
  },
  {
    q: 'Is my data uploaded?',
    a: 'No. The tool runs locally: a Python backend and a SQLite file on your own machine, with the browser talking only to that local API. Use synthetic or owner-authorised data, and keep your own exports out of the repository.',
  },
] as const;

/**
 * Full-bleed section band. Each tone is a static class string so Tailwind's scanner
 * sees every token it needs to emit.
 */
function Band({
  id,
  tone = 'light',
  children,
}: {
  id?: string;
  tone?: 'light' | 'dark' | 'butter' | 'stone';
  children: ReactNode;
}) {
  const tones = {
    light: 'border-hair bg-ivory py-24 text-ink md:py-36',
    dark: 'border-hairDark bg-ink py-24 text-ivory md:py-32',
    butter: 'border-hair bg-butter py-24 text-ink md:py-32',
    stone: 'border-hair bg-simulator py-24 text-ink md:py-32',
  } as const;

  return (
    <section id={id} className={`scroll-mt-24 border-t ${tones[tone]}`}>
      <div className={CONTAINER}>{children}</div>
    </section>
  );
}

/** Small caps label. Spelled out rather than reusing `.eyebrow`, whose slate grey is not in
 *  the landing palette and is too dark against the ink bands. */
function Eyebrow({ children, tone = 'light' }: { children: ReactNode; tone?: 'light' | 'dark' }) {
  return (
    <p
      className={`text-eyebrow font-semibold uppercase ${
        tone === 'dark' ? 'text-ivory/65' : 'text-ink/55'
      }`}
    >
      {children}
    </p>
  );
}

function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-hair bg-ivory/95 backdrop-blur">
      <div className={`${CONTAINER} flex min-h-[68px] items-center justify-between gap-3`}>
        <a
          href="#top"
          className={`flex min-h-[44px] min-w-[44px] items-center gap-2.5 rounded-landing ${FOCUS_LIGHT}`}
        >
          <Logo className="h-6 text-ink" wordmarkClassName="hidden sm:inline" />
        </a>

        {/* One nav, two presentations: a dropdown under the header on small viewports, an
            inline row from `lg`. `aria-controls` points at this id in both cases. */}
        <nav
          id="landing-nav"
          aria-label="Page sections"
          className={`${
            open ? 'flex' : 'hidden'
          } absolute inset-x-0 top-full max-h-[70vh] flex-col overflow-y-auto border-t border-hair bg-ivory px-5 py-2 lg:static lg:flex lg:max-h-none lg:flex-row lg:items-center lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0`}
        >
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              onClick={() => setOpen(false)}
              className={`inline-flex min-h-[44px] items-center rounded-landing px-3 text-[13.5px] font-medium text-ink/70 transition-colors duration-fast ease-standard hover:text-ink ${FOCUS_LIGHT}`}
            >
              {section.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-expanded={open}
            aria-controls="landing-nav"
            onClick={() => setOpen((wasOpen) => !wasOpen)}
            className={`inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-landing px-3 text-[13.5px] font-semibold text-ink transition-colors duration-fast ease-standard hover:bg-ink/[0.06] lg:hidden ${FOCUS_LIGHT}`}
          >
            {open ? 'Close' : 'Menu'}
          </button>

          <Link to="/app" className={PRIMARY}>
            Open the workspace
          </Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section
      id="top"
      className="scroll-mt-24 border-t border-hair bg-ivory pb-20 pt-[112px] text-ink md:pb-32"
    >
      <div className={CONTAINER}>
        <Reveal className="max-w-[54rem]">
          <Eyebrow>Decision support for resellers</Eyebrow>
          <h1 className="mt-5 font-landing text-display-xl text-ink">
            Know which SKU actually makes money.
          </h1>
          <p className="mt-6 max-w-[62ch] text-[17px] leading-relaxed text-ink/75">
            Import your own product and transaction CSVs and ArbitrageIQ works out what each
            SKU really contributes after marketplace fees, GST on those fees, shipping,
            returns and ad spend — then compares two transparent rules of thumb for spending
            an inventory budget.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link to="/app" className={PRIMARY}>
              Open the workspace
            </Link>
            <a href="#how" className={SECONDARY}>
              See how it works
            </a>
          </div>
        </Reveal>

        <Reveal delay={0.12}>
          <ul className="mt-14 flex flex-wrap gap-2 border-t border-hair pt-8">
            {CHIPS.map((chip) => (
              <li
                key={chip}
                className="inline-flex min-w-0 items-center rounded-landing border border-hair px-3.5 py-2 text-[13px] font-medium text-ink/75"
              >
                {chip}
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}

/** The mockup's mono micro-label. Anything that names a control rather than speaks to the
 *  reader carries one, rather than a new type size. */
const MICRO = 'font-mono text-eyebrow font-semibold uppercase';

/** The two-digit ordinal that opens a numbered item. Width-tracking, and the same string in
 *  all three places one appears — "The problem", "How it works" and "What this is not". */
const ORDINAL = 'font-landing text-[13px] font-bold tracking-[0.14em]';

const NO_PRODUCTS = (products: Product[]) => products.length === 0;
const NO_LINES = (profit: SkuProfit) => profit.lines.length === 0;

/**
 * The six terms the visitor can edit. Both rules are lexical tests on the exact text that
 * will be sent, the way Budget Lab checks its own controls: nothing here parses or computes
 * money (`AGENTS.md` rule 7, ADR-024). A blank `optional` term is left out of the request, and
 * the backend then uses the active assumption, which the result card echoes back.
 */
const AMOUNT = /^\d+(?:\.\d+)?$/;
const WITHIN_ZERO_ONE = /^(?:0(?:\.\d+)?|\.\d+|1(?:\.0+)?)$/;

const TERMS = [
  { key: 'price', label: 'Selling price, GST included', rule: AMOUNT, optional: false, adorn: '₹',
    hint: 'Per unit, in rupees. Starts from the catalogue target price as the backend stored it.' },
  { key: 'landed_unit_cost', label: 'Landed unit cost', rule: AMOUNT, optional: false, adorn: '₹',
    hint: 'Per unit, in rupees. Starts from the catalogue supplier cost — add inbound freight and packaging here if you want them counted.' },
  { key: 'referral_rate', label: 'Referral rate', rule: WITHIN_ZERO_ONE, optional: true, adorn: 'fraction',
    hint: 'A fraction of the price, for example 0.08. Leave blank to use the tool assumption.' },
  { key: 'closing_fee', label: 'Closing fee', rule: AMOUNT, optional: true, adorn: '₹',
    hint: 'Per unit, in rupees. Leave blank to use the tool assumption.' },
  { key: 'returns_rate', label: 'Returned share of the batch', rule: WITHIN_ZERO_ONE, optional: true, adorn: 'fraction',
    hint: 'A fraction of the batch, for example 0.10. Returned units are written off. Leave blank for none.' },
  { key: 'ads_per_unit', label: 'Ad spend per unit', rule: AMOUNT, optional: true, adorn: '₹',
    hint: 'In rupees, spread across the whole batch. Leave blank for none.' },
] as const;

type Term = (typeof TERMS)[number];
type TermKey = Term['key'];
type Terms = Record<TermKey, string>;

/** Seed only from columns the backend sent, copied as text — never added up here. */
function seedTerms(product: Product): Terms {
  return {
    price: product.target_price,
    landed_unit_cost: product.supplier_unit_cost,
    referral_rate: '',
    closing_fee: '',
    returns_rate: '',
    ads_per_unit: '',
  };
}

/** A ratio from the backend, already a string. `MoneyCell` would add a currency symbol. */
function PctCell({ value }: { value: string }) {
  const isLoss = value.startsWith('-');
  return (
    <span className={`tnum ${isLoss ? 'text-loss' : 'text-ivory'}`}>
      {value === 'n/a' ? 'n/a' : `${isLoss ? '−' : ''}${value.slice(isLoss ? 1 : 0)}%`}
    </span>
  );
}

const SETTLE_MS = 250;

function SkuSimulator({
  products,
  selected,
  onSelect,
}: {
  products: Product[];
  selected: string;
  onSelect: (sku: string) => void;
}) {
  const [terms, setTerms] = useState<Terms>(() => seedTerms(products[0]));
  const [kept, setKept] = useState<Terms>(() => seedTerms(products[0]));
  const [rejection, setRejection] = useState<{ key: TermKey; message: string } | null>(null);
  const [simulation, setSimulation] = useState<ApiState<SkuSimulation>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  const imported = useApi<SkuProfit>(`/profit/sku/${encodeURIComponent(selected)}`, NO_LINES);
  const product = products.find((item) => item.sku === selected);

  // Choosing a SKU restarts the what-if at that product's own catalogue terms.
  useEffect(() => {
    const next = products.find((item) => item.sku === selected);
    if (!next) return;
    const seeded = seedTerms(next);
    setTerms(seeded);
    setKept(seeded);
    setRejection(null);
  }, [selected, products]);

  const usable = TERMS.every((term) => {
    const text = terms[term.key].trim();
    return text === '' ? term.optional : term.rule.test(text);
  });

  const changeTerm = (term: Term, text: string) => {
    setTerms((current) => ({ ...current, [term.key]: text }));
    setRejection(
      (text.trim() === '' && term.optional) || term.rule.test(text)
        ? null
        : { key: term.key, message: `${term.label} is not a value this tool can use.` },
    );
  };

  const settleTerm = (term: Term) => {
    const text = terms[term.key].trim();
    if (text === '' && term.optional) {
      setRejection(null);
      return;
    }
    if (term.rule.test(text)) {
      setKept((current) => ({ ...current, [term.key]: text }));
      return;
    }
    setTerms((current) => ({ ...current, [term.key]: kept[term.key] }));
    setRejection({ key: term.key, message: `${term.label} is not a value this tool can use.` });
  };

  useEffect(() => {
    if (!usable) return;
    let live = true;
    const handle = window.setTimeout(() => {
      const body: Record<string, string> = {
        sku: selected,
        price: terms.price.trim(),
        landed_unit_cost: terms.landed_unit_cost.trim(),
      };
      for (const term of TERMS) {
        if (term.optional && terms[term.key].trim() !== '') body[term.key] = terms[term.key].trim();
      }
      void apiFetch<SkuSimulation>('/simulate/sku', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then((next) => {
        if (live) setSimulation(next);
      });
    }, SETTLE_MS);
    return () => {
      live = false;
      window.clearTimeout(handle);
    };
  }, [terms, selected, usable, attempt]);

  const line = simulation.status === 'ready' ? simulation.data.line : null;
  /** The badge tone is a string sign test on the backend's own figure, never a numeric
   *  comparison — no figure on this page is ever a number (`AGENTS.md` rule 7). */
  const isLoss = line !== null && line.contribution.startsWith('-');

  return (
    <div className="mt-10 grid gap-5 lg:grid-cols-12">
      {/* Left: the terms, each on its own label row. Styling only — every control keeps its
          validation, its revert-on-blur and its request wiring. */}
      <div className="min-w-0 rounded-landing border border-hair bg-white p-6 md:p-8 lg:col-span-7">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className={`${MICRO} text-ink/55`}>Parameters</p>
          <span className={`${MICRO} rounded-landing border border-hair px-2 py-1 text-ink/60`}>
            Deterministic model
          </span>
        </div>
        <p className="mt-3 text-[19px] font-bold text-ink">{product ? product.name : selected}</p>
        {product && <p className="mt-1 text-[13.5px] text-ink/60">{product.category}</p>}

        <label htmlFor="landing-sku" className="mt-5 block text-[13.5px] font-semibold text-ink">Select a SKU</label>
        <select id="landing-sku" value={selected} onChange={(event) => onSelect(event.target.value)}
          className={`mt-1.5 min-h-[44px] w-full rounded-landing border border-hair bg-ivory px-3 text-ink ${FOCUS_LIGHT}`}>
          {products.map((item) => <option value={item.sku} key={item.sku}>{item.name} · {item.sku}</option>)}
        </select>

        <div className="mt-6 border-t border-hair">
          {TERMS.map((term) => (
            <div key={term.key} className="flex min-h-[44px] flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-hair py-2.5 last:border-b-0">
              <label htmlFor={term.key} className="min-w-0 text-[14px] font-semibold text-ink">
                {term.label}
                {term.optional && <span className="ml-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink/45">optional</span>}
              </label>
              {/* A currency symbol leads the figure; a unit word trails it. */}
              <span className={`flex min-h-[44px] shrink-0 items-center rounded-landing border bg-ivory pr-3 transition-colors ${rejection?.key === term.key ? 'border-loss' : 'border-hair hover:border-ink/40 focus-within:border-ink'}`}>
                {term.adorn === '₹' && <span className="pl-3 text-[13.5px] text-ink/50">₹</span>}
                <input id={term.key} value={terms[term.key]} inputMode="decimal" autoComplete="off"
                  aria-invalid={rejection?.key === term.key}
                  aria-describedby={rejection?.key === term.key ? `${term.key}-hint ${term.key}-rejection` : `${term.key}-hint`}
                  onChange={(event) => changeTerm(term, event.target.value)}
                  onBlur={() => settleTerm(term)}
                  className={`tnum h-[44px] w-[8rem] bg-transparent px-2.5 text-right font-semibold text-ink outline-none ${FOCUS_LIGHT}`} />
                {term.adorn === 'fraction' && <span className="text-[12px] text-ink/50">fraction</span>}
              </span>
              <span id={`${term.key}-hint`} className="w-full text-[12.5px] leading-relaxed text-ink/60">{term.hint}</span>
            </div>
          ))}
        </div>
        {rejection && <p id={`${rejection.key}-rejection`} role="status" className="mt-3 text-[14px] font-medium text-loss">
          {rejection.message} The previous value was kept and nothing was sent to the API.
        </p>}

        {simulation.status === 'ready' && <div className="mt-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-ink/10 pt-4">
          <span className="text-[13.5px] font-semibold text-ink/70">Statutory fee GST rate</span>
          {/* The rate is echoed from the API as the fraction it is: "0.18" of the fee. It is
              never rendered as a percentage — that would mean multiplying a ratio here. */}
          <span className="tnum font-mono text-[13px] text-ink/70">
            Fixed {simulation.data.assumptions.gst_on_fees_rate} of the fee
          </span>
        </div>}

        <Link to="/app/profitability" className={`${SECONDARY} mt-7`}>Open all SKU results</Link>
      </div>

      {/* Right: the itemised result. Every figure below is a decimal string from the API.
          `!text-ivory` is deliberate: `MoneyCell` sets its own colour, and Tailwind emits
          `text-navy` after `text-ivory`, so the plain class would lose the cascade and paint
          navy on ink. The loss cue on this card is the word and the sign, not the hue. */}
      <div aria-live="polite" className="min-w-0 rounded-landing bg-ink p-6 text-ivory md:p-8 lg:col-span-5">
        {simulation.status === 'loading' && <p role="status">Running the what-if…</p>}
        {simulation.status === 'error' && <div role="alert"><p>{simulation.detail}</p><button type="button" onClick={() => setAttempt((value) => value + 1)} className={`${BUTTON} ${FOCUS_DARK} mt-4 border border-ivory/50 text-ivory hover:bg-ivory/10`}>Try again</button></div>}
        {simulation.status === 'ready' && line && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className={`${MICRO} text-ivory/60`}>Unit economics</p>
              <span className={`rounded-full border px-2.5 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide ${isLoss ? 'border-loss/50 bg-loss-wash text-loss' : 'border-gain/50 bg-gain-wash text-gain'}`}>
                {isLoss ? 'Loss-making' : 'Profitable'}
              </span>
            </div>

            <div className="mt-5 rounded-landing bg-ink/60 p-5">
              <p className={`${MICRO} text-ivory/60`}>Net contribution margin per unit</p>
              <p className="mt-2 text-[clamp(1.9rem,5.5vw,3rem)] font-bold tracking-tight text-ivory">
                <MoneyCell value={line.profit_per_unit} className="!text-ivory" />
              </p>
              <p className="mt-1 text-[13px] text-ivory/70">
                Margin on net revenue <PctCell value={line.margin_pct} />
              </p>
            </div>

            <p className="mt-4 text-[13.5px] leading-relaxed text-ivory/75">
              Shelf price: <MoneyCell value={line.price_paid} className="!text-ivory" /> ·{' '}
              {isLoss ? 'You lose: ' : 'What you actually keep: '}
              <MoneyCell value={isLoss ? line.profit_per_unit.slice(1) : line.profit_per_unit} className="!text-ivory" />
            </p>

            <dl className="mt-6 space-y-1 border-t border-ivory/25 pt-5 text-[14px]">
              {([
                ['Gross invoiced price', line.gross_revenue],
                ['Less: expected return drag', line.refunds],
                ['= Net realised revenue', line.net_revenue],
                ['Less: platform fees', line.fees_ex_gst],
                [`Less: GST on marketplace fees (rate ${simulation.data.assumptions.gst_on_fees_rate})`, line.fee_gst],
                ['Less: landed procurement (COGS)', line.product_cost],
                ['Less: ad spend', line.ads],
                ['Less: other charges', line.other_charges],
                ['Contribution', line.contribution],
              ] as const).map(([label, value]) =>
                <div key={label} className={`flex flex-wrap items-baseline justify-between gap-2 border-b border-ivory/20 py-1.5 ${label.startsWith('=') ? 'bg-ivory/[0.06] font-semibold' : ''}`}>
                  <dt className="text-ivory/75">{label}</dt>
                  <dd className="font-semibold"><MoneyCell value={value} className="!text-ivory" /></dd>
                </div>,
              )}
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ivory/20 py-1.5">
                <dt className="text-ivory/75">Return on cost</dt>
                <dd className="font-semibold"><PctCell value={line.roi_pct} /></dd>
              </div>
            </dl>
            <p className="mt-3 text-[13px] text-ivory/70">
              {simulation.data.units} units at your terms · {simulation.data.returned_units} written off · {line.net_units} shipped
            </p>
            <p className="mt-5 text-[13px] leading-relaxed text-ivory/75">{simulation.data.basis}</p>
            <p className="mt-3 text-[13px] leading-relaxed text-ivory/75">
              Rates the tool used: referral {simulation.data.assumptions.referral_rate}, closing fee {simulation.data.assumptions.closing_fee} per unit.
            </p>
            {imported.state.status === 'ready' && <p className="mt-5 border-t border-ivory/25 pt-5 text-[14px] leading-relaxed text-ivory/75">
              For comparison, the rows already imported for {selected} contribute <MoneyCell value={imported.state.data.totals.contribution} className="!text-ivory" /> across {imported.state.data.totals.line_count} transaction lines.
            </p>}
            <Link to="/app/methodology" className={`mt-4 inline-flex min-h-[44px] items-center text-[14px] font-semibold text-ivory underline underline-offset-4 ${FOCUS_DARK}`}>How contribution is calculated</Link>
          </>
        )}
      </div>
    </div>
  );
}

function Simulator() {
  const catalogue = useApi<Product[]>('/products', NO_PRODUCTS);
  const products = catalogue.state.status === 'ready' ? catalogue.state.data : [];
  // The SKU is chosen up in the header, so the choice is held here. `null` means "follow the
  // catalogue's first row", which is only known once the request lands.
  const [picked, setPicked] = useState<string | null>(null);
  const selected = picked !== null ? picked : products.length > 0 ? products[0].sku : '';
  const samples = products.filter(({ sku }) => ['TIFFIN-3', 'DIYA-SET-12', 'PHONE-STND'].includes(sku));

  return (
    <Band id="simulator" tone="stone">
      <Reveal>
        <div className="grid gap-8 lg:grid-cols-12 lg:items-end">
          <div className="lg:col-span-7">
            <Eyebrow>Interactive calculator</Eyebrow>
            <h2 className="mt-4 font-landing text-display-2xl text-ink">Live SKU Contribution Simulator</h2>
            <p className="mt-5 max-w-[62ch] text-[16px] leading-relaxed text-ink/80">
              Stress-test single-unit economics. Referral fees, the loss a return leaves behind and
              the ad budget each eat into the shelf price, and every change re-runs the calculation
              on the local backend. Nothing is calculated in your browser.
            </p>
          </div>

          {samples.length > 0 && (
            <div className="lg:col-span-5 lg:justify-self-end">
              <p className={`${MICRO} text-ink/55`}>Load SKU Preset:</p>
              <div aria-label="Sample SKUs" className="mt-2 inline-flex flex-wrap gap-1 rounded-landing border border-hair bg-white p-1">
                {samples.map(({ sku }) => (
                  <button key={sku} type="button" aria-pressed={selected === sku}
                    onClick={() => setPicked(sku)}
                    className={`min-h-[44px] rounded-landing border px-4 text-[13.5px] font-semibold transition-colors ${FOCUS_LIGHT} ${selected === sku ? 'border-ink bg-ink text-ivory' : 'border-transparent text-ink/70 hover:border-hair hover:text-ink'}`}>
                    {sku}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </Reveal>
      {catalogue.state.status === 'loading' && <p className="mt-8" role="status">Loading the catalogue…</p>}
      {catalogue.state.status === 'error' && <div className="mt-8" role="alert"><p>{catalogue.state.detail}</p><button type="button" onClick={catalogue.reload} className={`${SECONDARY} mt-4`}>Try again</button></div>}
      {catalogue.state.status === 'empty' && <p className="mt-8 rounded-landing border border-ink/20 bg-white p-6">No catalogue yet. <Link to="/app/import" className="underline">Load the synthetic sample or import your own CSVs</Link> to explore a SKU.</p>}
      {catalogue.state.status === 'ready' && <SkuSimulator products={products} selected={selected} onSelect={setPicked} />}
    </Band>
  );
}

function Problem() {
  return (
    <Band id="problem" tone="dark">
      <Reveal className="max-w-[48rem]">
        <Eyebrow tone="dark">The problem</Eyebrow>
        <h2 className="mt-4 font-landing text-display-2xl text-ivory">The shelf price lies.</h2>
        <p className="mt-6 text-[16.5px] leading-relaxed text-ivory/75">
          Subtract what a product cost from what it sells for and the difference looks like
          profit. Between those two numbers sit four deductions that a spreadsheet column
          rarely captures, and they are paid on units that never earned anything.
        </p>
      </Reveal>

      {/* The 1 px grid gap shows the parent's hairline colour through, so the cells are
          divided by real rules at every breakpoint. The four deductions are a sequence —
          each one takes its cut from what the last one left — so they arrive in order. */}
      <Stagger
        as="ol"
        className="mt-12 grid gap-px overflow-hidden rounded-landing border border-hairDark bg-hairDark sm:grid-cols-2 lg:grid-cols-4"
      >
        {LEAKAGES.map((item, index) => (
          <StaggerItem as="li" key={item.title} className="min-w-0 bg-ink p-6">
            <span aria-hidden="true" className={`${ORDINAL} text-butter`}>
              {String(index + 1).padStart(2, '0')}
            </span>
            <h3 className="mt-4 text-[18px] font-bold text-ivory">{item.title}</h3>
            <p className="mt-2.5 text-[14.5px] leading-relaxed text-ivory/70">{item.body}</p>
          </StaggerItem>
        ))}
      </Stagger>

      <p className="mt-10 max-w-[52rem] text-[15.5px] font-medium leading-relaxed text-ivory/85">
        A product that looks comfortably profitable on a spreadsheet can lose money on every
        unit that ships. Making that visible — per SKU, with the assumptions in the open — is
        the whole point of this tool.
      </p>
    </Band>
  );
}

function HowItWorks() {
  return (
    <Band id="how">
      <Reveal className="max-w-[48rem]">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="mt-4 font-landing text-display-2xl text-ink">Four steps, no setup.</h2>
      </Reveal>

      <Stagger as="ol" className="mt-12 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((step, index) => (
          <StaggerItem
            as="li"
            key={step.title}
            className="min-w-0 rounded-landing border border-hair bg-white p-6"
          >
            <span aria-hidden="true" className={`${ORDINAL} text-ink/45`}>
              {String(index + 1).padStart(2, '0')}
            </span>
            <h3 className="mt-4 text-[19px] font-bold text-ink">{step.title}</h3>
            <p className="mt-2.5 text-[14.5px] leading-relaxed text-ink/70">{step.body}</p>
          </StaggerItem>
        ))}
      </Stagger>
    </Band>
  );
}

function Computes() {
  return (
    <Band id="computes" tone="dark">
      <Reveal className="max-w-[48rem]">
        <Eyebrow tone="dark">What it computes</Eyebrow>
        <h2 className="mt-4 font-landing text-display-2xl text-ivory">
          Six figures, every one traceable.
        </h2>
        <p className="mt-6 text-[16px] leading-relaxed text-ivory/75">
          All of it realised from the rows you imported. Nothing on this page is projected or
          inferred, and contribution stops before overheads and income tax — it is not the
          money that reaches a bank account.
        </p>
      </Reveal>

      <Stagger as="dl" className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {COMPUTES.map((item) => (
          <StaggerItem
            key={item.title}
            className="min-w-0 rounded-landing border border-hairDark bg-white/[0.04] p-6"
          >
            <dt className="text-[18px] font-bold text-ivory">{item.title}</dt>
            <dd className="mt-2.5 text-[14.5px] leading-relaxed text-ivory/70">{item.body}</dd>
          </StaggerItem>
        ))}
      </Stagger>
    </Band>
  );
}

function BudgetLabSection() {
  return (
    <Band id="budget-lab" tone="butter">
      <Reveal className="max-w-[48rem]">
        <Eyebrow>Budget Lab</Eyebrow>
        <h2 className="mt-4 font-landing text-display-2xl text-ink">Two plans, both honest.</h2>
        <p className="mt-6 text-[16px] leading-relaxed text-ink/80">
          Enter a budget — ₹50,000 by default — and the lab splits it two ways. Both rest on a
          sell-through and a salvage value you can see and change, and neither is presented as
          the answer: they are two rules of thumb with the same score and one different rule.
        </p>
      </Reveal>

      <div className="mt-12 grid gap-6 lg:grid-cols-2">
        {PLANS.map((plan, index) => (
          <Reveal
            key={plan.name}
            delay={index * 0.08}
            className="min-w-0 rounded-landing border border-ink/15 bg-white/80 p-6"
          >
            <h3 className="text-[19px] font-bold text-ink">{plan.name}</h3>
            <p className="mt-2.5 text-[14.5px] leading-relaxed text-ink/75">{plan.body}</p>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.1}>
        <div className="mt-10 max-w-[52rem] rounded-landing border border-ink/20 bg-white/85 p-6">
          <h3 className="text-[15px] font-bold uppercase tracking-[0.09em] text-ink">
            The limitation, stated plainly
          </h3>
          <p className="mt-3 text-[15px] leading-relaxed text-ink/80">
            The conservative scenario is a uniform downside shock: price and sell-through fall
            for every SKU at once. Because every SKU is stressed equally, it cannot demonstrate
            the benefit of spreading a budget — a diversified plan can even score worse under it
            than a concentrated one, while still being more resilient in practice to a
            product-specific failure such as a supplier default, a stock-out or a listing
            suspension. Treat the scenario as a stress test of price and sell-through, not as
            proof of anything about diversification.
          </p>
        </div>
      </Reveal>
    </Band>
  );
}

function Not() {
  return (
    <Band id="not" tone="dark">
      <Reveal className="max-w-[48rem]">
        <Eyebrow tone="dark">What this is not</Eyebrow>
        <h2 className="mt-4 font-landing text-display-2xl text-ivory">
          Limits worth reading before you trust a number.
        </h2>
      </Reveal>

      <ul className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {NOTS.map((item, index) => (
          <li key={item.title} className="min-w-0 border-t border-hairDark pt-5">
            <span aria-hidden="true" className={`${ORDINAL} text-butter`}>
              {String(index + 1).padStart(2, '0')}
            </span>
            <h3 className="mt-3 text-[17px] font-bold text-ivory">{item.title}</h3>
            <p className="mt-2.5 text-[14.5px] leading-relaxed text-ivory/70">{item.body}</p>
          </li>
        ))}
      </ul>
    </Band>
  );
}

function Faq() {
  return (
    <Band id="faq">
      <Reveal className="max-w-[48rem]">
        <Eyebrow>FAQ</Eyebrow>
        <h2 className="mt-4 font-landing text-display-2xl text-ink">
          Asked and answered honestly.
        </h2>
      </Reveal>

      {/* Native <details>/<summary>: keyboard-operable and screen-reader-announced with no
          script of our own. Seven rows is long enough to read as a list, so they arrive in
          order; the group is the ruled block, and each row is one <details>. */}
      <Stagger className="mt-10 border-t border-hair">
        {FAQ.map((item) => (
          <StaggerItem as="details" key={item.q} className="group border-b border-hair">
            <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-4 py-4 text-[17px] font-semibold text-ink transition-colors duration-fast ease-standard hover:text-ink/70 focus-visible:ring-offset-ivory [&::-webkit-details-marker]:hidden">
              {item.q}
              <svg
                aria-hidden="true"
                viewBox="0 0 20 20"
                className="h-5 w-5 shrink-0 text-ink/55 transition-transform duration-base ease-standard group-open:rotate-180"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 7.5 10 12.5 15 7.5" />
              </svg>
            </summary>
            <p className="max-w-[68ch] pb-5 pr-9 text-[15px] leading-relaxed text-ink/75">
              {item.a}
            </p>
          </StaggerItem>
        ))}
      </Stagger>
    </Band>
  );
}

function Footer() {
  return (
    <footer className="border-t border-hairDark bg-ink pb-16 pt-20 text-ivory">
      <div className={CONTAINER}>
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr]">
          <div className="min-w-0">
            <Logo className="h-7 text-ivory" accentClassName="text-butter" />
            <p className="mt-3 max-w-[46ch] text-[14.5px] leading-relaxed text-ivory/70">
              Contribution profit per SKU from your own CSVs, and two transparent rules of
              thumb for spending an inventory budget.
            </p>
          </div>

          <nav aria-label="Landing sections" className="min-w-0">
            <p className="text-eyebrow font-semibold uppercase text-ivory/55">Sections</p>
            <ul className="mt-2">
              {SECTIONS.map((section) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className={`inline-flex min-h-[44px] min-w-[44px] items-center rounded-landing text-[14.5px] text-ivory/70 transition-colors duration-fast ease-standard hover:text-ivory ${FOCUS_DARK}`}
                  >
                    {section.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <p className="mt-14 border-t border-hairDark pt-8 text-[12.5px] leading-relaxed text-ivory/60">
          A local tool using illustrative demo assumptions and synthetic or owner-authorised
          data only. It files no returns and connects to nothing.
        </p>
      </div>
    </footer>
  );
}

export function Landing() {
  return (
    <div className="min-h-screen bg-ivory font-landing">
      <a
        href="#top"
        className={`sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-landing focus:bg-ivory focus:px-4 focus:py-3 focus:text-sm focus:font-medium focus:text-ink ${FOCUS_LIGHT}`}
      >
        Skip to content
      </a>

      <Header />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Simulator />
        <Computes />
        <BudgetLabSection />
        <Not />
        <Faq />
      </main>
      <Footer />
    </div>
  );
}
