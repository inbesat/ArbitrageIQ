/** @type {import('tailwindcss').Config} */
// Tailwind CSS v3 configuration (the version pinned in plans/TECH_STACK.md §3).
// Source: https://v3.tailwindcss.com/docs/configuration
//
// T13 design tokens. They implement the direction in plans/TECH_STACK.md §3 and §6 —
// navy / near-white neutrals, teal-green for primary and positive, amber for warnings,
// loss red for negative — which describes the palette but names no hex value. The hexes
// below are therefore a T13 styling choice, logged in plans/PROGRESS.md §8.
//
// Use a token name, never a raw hex, inside a component.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#142338', soft: '#1E3350', deep: '#0B1523' },
        canvas: '#F7F9FB',
        surface: '#FFFFFF',
        rule: '#E2E8F0',
        teal: { DEFAULT: '#0F766E', dark: '#115E59', wash: '#E7F2F1' },
        gain: { DEFAULT: '#166534', wash: '#EAF4EC' },
        warn: { DEFAULT: '#A16207', wash: '#FBF3E3' },
        loss: { DEFAULT: '#B42318', wash: '#FBECEA' },
        muted: '#64748B',
        // Landing-page band palette (the public page at `/`). The five app views keep the
        // navy/teal/canvas tokens above; these are additive.
        ivory: '#FAF9F6',
        ink: '#111827',
        butter: '#F5E6C8',
        hair: '#E5E3DD',
        hairDark: '#2A2F3A',
        // The warm neutral ground the landing `#simulator` band sits on. It is a separate
        // name rather than an override of stone-100 (#f5f5f4) so the tone stays a token.
        simulator: '#F3F1EC',
      },
      fontFamily: {
        // Resolved from the CSS variables in src/index.css, so the stack is declared once.
        sans: ['var(--font-sans)'],
        display: ['var(--font-display)'],
        // The public landing page only. Names Space Grotesk first, bundles nothing.
        landing: ['var(--font-landing)'],
      },
      // A restrained type scale. Body copy uses Tailwind's defaults; only the display
      // sizes and the small caps label are worth naming.
      //
      // Every step names its own `lineHeight` and `letterSpacing`, because the two belong to
      // the size rather than to the call site: a heading set at 34 px wants negative tracking
      // and a tight leading, a small caps label at 11 px wants positive tracking and room to
      // breathe. Tracking runs from +0.1em on the smallest label to -0.038em on the hero, and
      // no step relies on Tailwind's inherited default. See plans/PROGRESS.md §8.
      fontSize: {
        // The label above a heading. Smallest type on the page, so it takes the most air.
        eyebrow: ['11px', { lineHeight: '1.2', letterSpacing: '0.1em' }],
        display: ['30px', { lineHeight: '1.12', letterSpacing: '-0.021em' }],
        'display-lg': ['34px', { lineHeight: '1.08', letterSpacing: '-0.023em' }],
        // The interior scale. Seven steps, so a size is picked rather than nudged; the
        // steps before it were half-pixel neighbours (13/13.5/14, 19/20/22) and read as
        // an accident. Ranks: micro < caption < body < lead < title < figure-sm < figure.
        // The public landing page keeps its own scale and does not read these.
        micro: ['11.5px', { lineHeight: '1.45', letterSpacing: '0.012em' }],
        caption: ['12.5px', { lineHeight: '1.55', letterSpacing: '0.006em' }],
        body: ['13.5px', { lineHeight: '1.6', letterSpacing: '-0.002em' }],
        lead: ['14.5px', { lineHeight: '1.6', letterSpacing: '-0.004em' }],
        title: ['18px', { lineHeight: '1.28', letterSpacing: '-0.016em' }],
        'figure-sm': ['21px', { lineHeight: '1.1', letterSpacing: '-0.018em' }],
        figure: ['26px', { lineHeight: '1.05', letterSpacing: '-0.022em' }],
        // Landing headings. Clamped so a 375 px viewport shrinks the type instead of
        // overflowing. The hero gets the tightest tracking on the page: at 4.75rem a
        // default tracking reads as a gap between letters rather than a word.
        'display-2xl': ['clamp(1.9rem, 4vw, 3rem)', { lineHeight: '1.05', letterSpacing: '-0.031em' }],
        'display-xl': ['clamp(2.6rem, 6.6vw, 4.75rem)', { lineHeight: '1', letterSpacing: '-0.038em' }],
      },
      // A restrained radius hierarchy: controls sit at 6px, containers at 10px, and the
      // public landing page's bands and cards stay near-square at 4px.
      borderRadius: { DEFAULT: '6px', card: '10px', landing: '4px' },
      // Two-layer shadows read as depth rather than as a grey edge.
      boxShadow: {
        card: '0 1px 2px rgba(20, 35, 56, 0.05), 0 1px 3px rgba(20, 35, 56, 0.06)',
        raised: '0 2px 4px rgba(20, 35, 56, 0.06), 0 8px 20px -12px rgba(20, 35, 56, 0.20)',
        // Hover elevation for interactive cards, and a teal halo for the primary action.
        lift: '0 2px 4px rgba(20, 35, 56, 0.06), 0 14px 34px -14px rgba(20, 35, 56, 0.28)',
        glow: '0 0 0 1px rgba(15, 118, 110, 0.16), 0 10px 30px -14px rgba(15, 118, 110, 0.55)',
      },
      transitionDuration: { fast: '140ms', base: '180ms' },
      transitionTimingFunction: { standard: 'cubic-bezier(0.2, 0, 0, 1)' },
      // A slow drift for the ambient background. Long enough to read as "alive"
      // rather than as a moving element competing with the content.
      keyframes: {
        drift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)' },
          '50%': { transform: 'translate3d(0, -2.5%, 0) scale(1.06)' },
        },
      },
      animation: { drift: 'drift 26s cubic-bezier(0.45, 0, 0.55, 1) infinite' },
    },
  },
  plugins: [],
};
