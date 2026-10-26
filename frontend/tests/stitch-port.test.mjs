import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (relative) => readFileSync(new URL(relative, import.meta.url), 'utf8');

/** For files a pending slice is about to add: an absent file fails the assertion, not the run. */
const readIfPresent = (relative) => {
  try {
    return read(relative);
  } catch {
    return '';
  }
};

const landing = read('../src/views/Landing.tsx');
const budget = read('../src/views/BudgetLab.tsx');
const plan = read('../src/components/PlanCard.tsx');
const types = read('../src/api/types.ts');
const tailwind = read('../tailwind.config.js');

const SIMULATOR_FIELDS = [
  'price',
  'landed_unit_cost',
  'referral_rate',
  'closing_fee',
  'returns_rate',
  'ads_per_unit',
];

test('landing simulator sends typed terms to the API and reads real catalogue rows', () => {
  assert.match(landing, /Live SKU Contribution Simulator/);
  assert.match(landing, /useApi<Product\[]>\('\/products'/);
  assert.match(landing, /useApi<SkuProfit>\(`\/profit\/sku\/\$\{encodeURIComponent\(selected\)\}`/);
  assert.match(landing, /apiFetch<SkuSimulation>\('\/simulate\/sku'/);
  assert.match(landing, /method: 'POST'/);
  assert.match(landing, /totals\.contribution/);
  assert.match(landing, /simulation\.data\.basis/);
  assert.match(landing, /<HowItWorks \/>\s*<Simulator \/>\s*<Computes \/>/);
  assert.match(landing, /'TIFFIN-3', 'DIYA-SET-12', 'PHONE-STND'/);
  assert.match(landing, /<Band id="simulator" tone="stone">/);
  assert.match(landing, /aria-live="polite"[^>]*bg-ink/);
  for (const field of SIMULATOR_FIELDS) {
    assert.match(landing, new RegExp(`key: '${field}'`));
  }
  // Money stays a decimal string end to end: no numeric conversion anywhere.
  assert.doesNotMatch(landing, /parseFloat|parseInt|Number\(/);
  assert.match(types, /interface SkuSimulation/);
});

// The landing `#simulator` mockup is a generated screen whose arithmetic runs in the browser
// over `parseFloat`ed numbers, driven by six `<input type="range">` sliders. Only its layout
// and wording are ported: every figure still arrives as a decimal string from the API.
test('landing simulator adopts the mockup layout without porting its browser-side calculator', () => {
  // The band's warm neutral ground, as a token rather than a raw hex in the component.
  assert.match(tailwind, /simulator: '#F3F1EC'/);
  assert.match(landing, /bg-simulator/);

  // The header: the preset loader moved up out of the parameter card.
  assert.match(landing, /Load SKU Preset:/);
  assert.match(landing, /aria-label="Sample SKUs"/);

  // The two cards and the mockup's own labels.
  assert.match(landing, /lg:col-span-7/);
  assert.match(landing, /lg:col-span-5/);
  assert.match(landing, />Parameters</);
  assert.match(landing, /Deterministic model/);
  assert.match(landing, /Unit economics/);
  assert.match(landing, /Net contribution margin per unit/);
  assert.match(landing, /Statutory fee GST rate/);

  // The waterfall, relabelled to the mockup's wording, with the realised-revenue subtotal.
  assert.match(landing, /'Gross invoiced price'/);
  assert.match(landing, /'Less: expected return drag'/);
  assert.match(landing, /'= Net realised revenue'/);
  assert.match(landing, /'Less: landed procurement \(COGS\)'/);

  // The reality check, and the badge chosen by a string sign test.
  assert.match(landing, /What you actually keep:/);
  assert.match(landing, /You lose: /);
  assert.match(landing, /isLoss \? 'Loss-making' : 'Profitable'|'Loss-making'/);
  assert.match(landing, /'Profitable'/);
  assert.match(landing, /contribution\.startsWith\('-'\)/);
  // `MoneyCell` carries its own colour class and Tailwind emits `text-navy` after
  // `text-ivory`, so on the ink card the figure only stays legible with the important
  // modifier. Checked against the built CSS, where `.text-navy` follows `.text-ivory`.
  assert.match(landing, /className="!text-ivory"/);

  // The API's own rate is echoed, and it is never dressed up as a percentage: the wire value
  // is a fraction ("0.18"), and turning it into 18 would be arithmetic on a ratio.
  assert.match(landing, /assumptions\.gst_on_fees_rate/);
  assert.doesNotMatch(landing, /gst_on_fees_rate\}[^`"'\n]*%/);
  assert.doesNotMatch(landing, /→ ?Range|type="range"/);

  // No banned claim about the heuristic.
  assert.doesNotMatch(landing, /optimal|guaranteed|predicted sale/i);
});

test('Budget Lab preserves backend simulation and renders four backend-sourced plan cards', () => {
  assert.match(budget, /apiFetch<Simulation>\('\/budget\/simulate'/);
  assert.match(budget, /Base scenario comparison/);
  assert.match(budget, /Conservative stress scenario/);
  assert.match(budget, /simulation\.data\.disclosure/);
  assert.match(budget, /bg-navy[^"\n]*text-white/);
  assert.match(plan, /plan\.expected_contribution/);
  assert.doesNotMatch(budget + plan, /Integer Knapsack|Monte Carlo|64-bit Floating Point/);
});

// The Budget Lab mockup is a generated screen whose arithmetic runs in the browser and
// whose panels report a solver that does not exist here. Only its layout is ported.
const MOCKUP_ENGINE_CLAIMS = [
  'Integer Knapsack',
  'Monte Carlo',
  '64-bit Floating Point',
  'QUANT v2.4',
  'Deterministic Sandbox',
  'Solver Ready',
  'Latency 34ms',
  'Auto-Solve',
  'RESALE-OPT-4.1',
  'Concentration Premium',
  'Greedy Advantage',
  'High Fragility',
  'MAX PROFIT',
  'RESILIENT',
  'Risk Diversified',
  'Supplier Dependency',
  'Listing Suspend Risk',
  'Inventory Liquidity',
];

const MOCKUP_INVENTED_FIGURES = [
  '21,184.13',
  '15,266.62',
  '5,917.51',
  '49,896.00',
  '49,959.00',
  '1,788.92',
  '42.45%',
  '39.8%',
  '100 units',
  '126 units',
  '26 units',
];

test('Budget Lab adopts the mockup layout from API strings, not the mockup engine', () => {
  // The hero and the three headline banners, each fed by an echoed API field.
  assert.match(budget, /Budget Lab \/ Portfolio capital allocation/);
  assert.match(budget, /Working budget/);
  assert.match(budget, /Highest expected contribution/);
  assert.match(budget, /Concentration cap/);
  assert.match(budget, /simulation\.data\.budget/);
  assert.match(budget, /simulation\.data\.max_share_per_sku/);
  assert.match(budget, /base\.plan_a\.expected_contribution/);
  assert.match(budget, /base\.plan_b\.expected_contribution/);

  // The parameter grid keeps every control, its validation and its revert-on-blur.
  assert.match(budget, /Simulation parameters &amp; constraints/);
  assert.match(budget, /inputMode="decimal"/);
  assert.match(budget, /aria-invalid=/);
  assert.match(budget, /aria-describedby=/);

  // The plan card keeps the two headline figures and the funded-line breakdown.
  assert.match(plan, /Capital allocated/);
  assert.match(plan, /Budget unused/);
  assert.match(plan, /Expected contribution/);
  assert.match(plan, /Allocation breakdown/);
  assert.match(plan, /sharePercent/);

  // Money stays a decimal string end to end: no numeric conversion anywhere.
  assert.doesNotMatch(budget + plan, /parseFloat|parseInt|Number\(/);

  // No banned claim about the allocator.
  assert.doesNotMatch(budget + plan, /optimal|best|maximis|guaranteed|predicted sale/i);

  // None of the mockup's invented engine claims or figures reached the port.
  for (const ported of [...MOCKUP_ENGINE_CLAIMS, ...MOCKUP_INVENTED_FIGURES]) {
    assert.ok(!(budget + plan).includes(ported), `ported mockup string: ${ported}`);
  }
});

// --- typography and scroll motion (DEV-42) ----------------------------------------------
// The font stacks themselves are deliberately system-only, so this pass refines the scale,
// the tracking and the optical defaults rather than the typeface. See plans/PROGRESS.md §8.

const reveal = read('../src/components/Reveal.tsx');
const stagger = readIfPresent('../src/components/Stagger.tsx');
const progress = readIfPresent('../src/components/ScrollProgress.tsx');
const app = read('../src/App.tsx');
const smoothScroll = read('../src/lib/smooth-scroll.ts');
const indexCss = read('../src/index.css');
const packageJson = JSON.parse(read('../package.json'));

const TYPE_STEPS = [
  'micro',
  'caption',
  'body',
  'lead',
  'title',
  'figure-sm',
  'figure',
  'eyebrow',
  'display',
  'display-lg',
  'display-2xl',
  'display-xl',
];

test('every type step carries an intentional leading and tracking, and the base sets optical defaults', () => {
  // The scale is read as a block rather than line by line, so reordering or reformatting the
  // config does not break this: each named step must still declare both attributes.
  const scale = tailwind.slice(tailwind.indexOf('fontSize: {'), tailwind.indexOf('borderRadius: {'));
  assert.ok(scale.length > 0, 'fontSize block not found in tailwind.config.js');

  const steps = scale.match(/^\s+'?[a-z0-9-]+'?: \[/gm) ?? [];
  assert.ok(steps.length >= TYPE_STEPS.length, `only ${steps.length} type steps declared`);
  assert.equal(
    (scale.match(/lineHeight:/g) ?? []).length,
    steps.length,
    'a type step is missing its lineHeight',
  );
  assert.equal(
    (scale.match(/letterSpacing:/g) ?? []).length,
    steps.length,
    'a type step is missing its letterSpacing',
  );

  for (const name of TYPE_STEPS) {
    assert.ok(
      scale.includes(`${name}: [`) || scale.includes(`'${name}': [`),
      `type step renamed or dropped: ${name}`,
    );
  }

  // Optical defaults that only CSS can set: balanced headings, no orphaned last words.
  assert.match(indexCss, /text-wrap: balance/);
  assert.match(indexCss, /text-wrap: pretty/);
  assert.match(indexCss, /font-optical-sizing/);
  assert.match(indexCss, /font-variant-numeric: tabular-nums/);
  assert.match(indexCss, /font-feature-settings/);
});

test('scroll motion is staggered, scroll-linked, and off when motion is not wanted', () => {
  // `Reveal` keeps its existing call signature (`delay`, `y`) — it is used from fifteen places.
  assert.match(reveal, /export function Reveal/);
  assert.match(reveal, /useReducedMotion/);
  assert.match(reveal, /delay = 0/);
  assert.match(reveal, /y = \d+/);
  assert.match(reveal, /opacity: 0/);
  assert.match(reveal, /whileInView/);
  assert.match(reveal, /reduced/);

  // A group reveals its direct children in sequence, with the tag preserved in both states.
  assert.match(stagger, /export function Stagger/);
  assert.match(stagger, /export function StaggerItem/);
  assert.match(stagger, /staggerChildren/);
  assert.match(stagger, /useReducedMotion/);
  assert.match(stagger, /whileInView/);

  // The four genuinely list-like groups on the landing page use it, and nothing else does.
  assert.match(landing, /import \{ Stagger, StaggerItem \} from '\.\.\/components\/Stagger'/);
  const groups = landing.match(/<Stagger\b/g) ?? [];
  const items = landing.match(/<StaggerItem\b/g) ?? [];
  assert.equal(groups.length, 4, `expected 4 staggered groups, found ${groups.length}`);
  assert.equal(
    items.length,
    groups.length,
    'every group in the source maps its members through a StaggerItem',
  );
  assert.doesNotMatch(budget + read('../src/views/Methodology.tsx') + read('../src/views/Import.tsx'), /Stagger/);

  // A thin reading-progress rule, scaled from the page's own scroll fraction.
  assert.match(progress, /useScroll/);
  assert.match(progress, /useSpring/);
  assert.match(progress, /aria-hidden="true"/);
  assert.match(progress, /useReducedMotion\(\) \? null/);
  assert.match(progress, /scaleX/);
  assert.match(app, /<ScrollProgress \/>/);

  // The ambient bloom drifts with the page, one transform layer, and not under reduced motion.
  assert.match(app, /app-aurora/);
  assert.match(app, /useReducedMotion/);
  assert.match(app, /useTransform/);

  // Anchor links are handed to Lenis, which honours each section's `scroll-mt-24`.
  assert.match(smoothScroll, /anchors: true/);
  assert.match(smoothScroll, /stopInertiaOnNavigate: true/);
  assert.match(landing, /scroll-mt-24/);
  assert.match(indexCss, /prefers-reduced-motion: reduce/);
});

test('the premium pass added no dependency and no money parsing', () => {
  assert.deepEqual(Object.keys(packageJson.dependencies).sort(), [
    'lenis',
    'motion',
    'react',
    'react-dom',
    'react-router-dom',
  ]);
  assert.equal(packageJson.devDependencies?.tailwindcss !== undefined, true);

  // Motion is a transform/opacity concern only: nothing new converts or computes a figure.
  assert.doesNotMatch(landing, /parseFloat|parseInt|Number\(/);
  assert.doesNotMatch(budget + plan, /parseFloat|parseInt|Number\(/);
});

// --- the signature mark (DEV-43) --------------------------------------------------------
// Three brand placements previously each spelled the name for themselves. One component now
// carries the identity, and the favicon is drawn from the same path data.

const logo = readIfPresent('../src/components/Logo.tsx');
const favicon = readIfPresent('../public/favicon.svg');

test('one Logo component carries the brand, drawn in tokens with no raw hex', () => {
  assert.match(logo, /export function Logo/);
  // Colour is inherited from the surrounding text, so ivory, ink and navy all work from a
  // single drawing.
  assert.match(logo, /currentColor/);
  // A token name, never a hex, inside a component — the rule written into
  // `tailwind.config.js`.
  assert.doesNotMatch(logo, /#[0-9a-fA-F]{3,8}\b/);
  // A viewBox drawn tight on the ink itself, so the mark cannot inherit a dead margin.
  assert.match(logo, /viewBox="1\.89 0\.7 26\.16 23\.6"/);
  // Honest, small props: a size class, the lockup toggle and the accent's own colour.
  assert.match(logo, /showWordmark = true/);
  assert.match(logo, /accentClassName/);
});

test('the mark is announced only when it stands alone', () => {
  // One expression decides, so the two can never disagree: beside the wordmark the adjacent
  // text already names the brand and the svg must not repeat it; standing alone the svg is
  // the only name there is.
  assert.match(
    logo,
    /aria-hidden': 'true'[\s\S]{0,90}\}[\s\S]{0,20}:[\s\S]{0,60}role: 'img', 'aria-label': 'ArbitrageIQ'/,
  );
  // Sized by its caller, never stretched: the lockup sets a height and the mark follows.
  assert.match(logo, /h-full w-auto/);
  assert.match(logo, /shrink-0/);
});

test('the landing page and the app shell share the one identity', () => {
  assert.match(landing, /import \{ Logo \} from '\.\.\/components\/Logo'/);
  assert.equal((landing.match(/<Logo\b/g) ?? []).length, 2, 'the header and the footer');
  assert.doesNotMatch(landing, /function Wordmark/);
  assert.match(app, /import \{ Logo \} from '\.\/components\/Logo'/);
  assert.equal((app.match(/<Logo\b/g) ?? []).length, 1, 'the sidebar brand');
  assert.doesNotMatch(app, /function BrandMark/);
  // The landing states the ink-and-teal polarity; the two dark placements (ink footer, navy
  // sidebar) keep the mark legible by theming it themselves.
  assert.match(landing, /<Logo className="[^"]*text-ink/);
  assert.match(landing, /<Logo className="[^"]*text-ivory/);
  // Measured at 375 px: with the wordmark shown, the header lockup runs into the "Menu"
  // button. The mark stays and the name yields, exactly as it did before this component.
  assert.match(landing, /wordmarkClassName="hidden sm:inline"/);
});

test('the favicon is the same mark, and both copies move in step', () => {
  // Every page load used to 404 on `/favicon.ico`; there was no icon at all.
  assert.match(read('../index.html'), /<link rel="icon" href="\/favicon\.svg" type="image\/svg\+xml"/);
  assert.match(favicon, /<svg[^>]*viewBox="0 0 32 32"/);
  const paths = (source) => [...source.matchAll(/["'](M[^"'<>]+Z)["']/g)].map(([, d]) => d);
  assert.ok(paths(logo).length > 0, 'no signed path data in Logo.tsx');
  assert.deepEqual(
    paths(favicon).sort(),
    paths(logo).sort(),
    'Logo.tsx and public/favicon.svg must carry the same path data',
  );
});
