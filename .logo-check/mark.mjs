// THROWAWAY: derives each candidate's outline from a centreline + width profile, because a
// tapered ribbon is not something to hand-guess. Deleted with .logo-check/ after the winner
// is pasted into src/components/Logo.tsx and public/favicon.svg.
import { writeFileSync } from 'node:fs';

const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
const mul = (a, k) => [a[0] * k, a[1] * k];
const norm = (a) => {
  const l = Math.hypot(a[0], a[1]);
  return [a[0] / l, a[1] / l];
};
const perp = (a) => [a[1], -a[0]];
const n = (v) => Number(v.toFixed(2));
const pt = (p) => `${n(p[0])} ${n(p[1])}`;

/** A closed outline around a knot chain, offset by the half-width at each knot. */
function ribbon(knots) {
  const tangents = knots.map((k, i) => {
    const prev = knots[i - 1]?.p ?? k.p;
    const next = knots[i + 1]?.p ?? k.p;
    const raw =
      i === 0 ? sub(next, k.p) : i === knots.length - 1 ? sub(k.p, prev) : mul(sub(next, prev), 0.5);
    return norm(raw);
  });
  const segs = knots.slice(0, -1).map((k, i) => ({
    c1: add(k.p, mul(tangents[i], 1 / 3)),
    c2: sub(knots[i + 1].p, mul(tangents[i + 1], 1 / 3)),
    n0: perp(tangents[i]),
    n1: perp(tangents[i + 1]),
    w0: k.w,
    w1: knots[i + 1].w,
  }));
  const off = (i, sign) => add(knots[i].p, mul(perp(tangents[i]), sign * knots[i].w));

  const d = [`M${pt(off(0, 1))}`];
  segs.forEach((s, i) =>
    d.push(`C${pt(add(s.c1, mul(s.n0, s.w0)))} ${pt(add(s.c2, mul(s.n1, s.w1)))} ${pt(off(i + 1, 1))}`),
  );
  for (let i = segs.length - 1; i >= 0; i -= 1) {
    const s = segs[i];
    d.push(`C${pt(sub(s.c2, mul(s.n1, s.w1)))} ${pt(sub(s.c1, mul(s.n0, s.w0)))} ${pt(off(i, -1))}`);
  }
  const pts = [];
  segs.forEach((s, i) => {
    pts.push(add(s.c1, mul(s.n0, s.w0)), add(s.c2, mul(s.n1, s.w1)), off(i, 1), off(i, -1));
  });
  pts.push(off(knots.length - 1, 1), off(0, 1));
  return { d: `${d.join(' ')} Z`, pts };
}

/** The ink box over every chain, plus any extra element the caller has to place. */
function box(parts) {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const pts of parts) {
    for (const [x, y] of pts) {
      x0 = Math.min(x0, x);
      y0 = Math.min(y0, y);
      x1 = Math.max(x1, x);
      y1 = Math.max(y1, y);
    }
  }
  return [x0, y0, x1, y1];
}

// Each chain is [knots, pad] where pad is the extra half-width the offset reaches; the
// control polygon already includes the offsets, so pad is only for the accent square.
const K = (p, w) => ({ p, w });

// ---------------------------------------------------------------------------------------
// A — one continuous ribbon: entry, apex, right leg, turn and flourish are a single sweep.
const A = {
  spine: [
    K([2.6, 20.6], 0.12),
    K([9.6, 3.4], 1.75),
    K([14.8, 12.6], 1.5),
    K([17.6, 19.2], 1.15),
    K([23.2, 21.6], 0.95),
    K([29.6, 21.9], 0.55),
    K([35.4, 19.0], 0),
  ],
  bar: [K([4.9, 15.55], 0.3), K([9.8, 15.1], 0.8), K([15.2, 14.75], 0.3)],
  accent: [35.6, 18.0, 2.0],
};

// B — a bold letter `A` (legs, apex, fused crossbar) with a separate shallow swash beneath.
const B = {
  spine: [K([2.9, 20.4], 0.7), K([8.4, 3.0], 1.85), K([14.0, 20.4], 0.75)],
  bar: [K([5.0, 14.9], 0.3), K([9.2, 14.5], 0.8), K([13.6, 14.1], 0.3)],
  swash: [
    K([3.6, 22.4], 0.05),
    K([6.0, 23.0], 0.6),
    K([14.0, 23.6], 0.9),
    K([24.0, 23.1], 0.7),
    K([35.4, 19.2], 0),
  ],
  accent: [35.6, 18.2, 2.0],
};

// C — a script `A`: the pen enters from the left, the letter leans right, the exit is long.
const C = {
  spine: [
    K([1.6, 19.6], 0.1),
    K([6.6, 12.4], 0.75),
    K([11.6, 3.0], 1.7),
    K([16.4, 17.2], 1.2),
    K([20.4, 21.4], 0.9),
    K([28.0, 22.0], 0.55),
    K([35.8, 18.8], 0),
  ],
  bar: [K([6.6, 14.9], 0.3), K([10.8, 14.4], 0.8), K([15.4, 13.9], 0.3)],
  accent: [36.0, 17.8, 2.0],
};

// B refined: a narrower, bolder letter, a crossbar whose taper hides inside both legs, and
// a shorter single shallow swash. B2 carries the accent fused to the swash tip; B2n has none.
const LETTER_B = [K([3.0, 20.6], 0.55), K([8.6, 2.8], 1.95), K([14.2, 20.6], 0.6)];
const BAR_B = [K([5.2, 14.95], 0.55), K([8.9, 14.75], 0.78), K([12.6, 14.55], 0.55)];
const SWASH_B = [K([4.4, 22.6], 0.05), K([9.8, 23.4], 0.8), K([25.4, 19.9], 0)];

const B2 = { spine: LETTER_B, bar: BAR_B, swash: SWASH_B, accent: [26.2, 18.9, 2.0] };
const B2n = { spine: LETTER_B, bar: BAR_B, swash: SWASH_B, accent: null };

// B3 — four-knot swash so the width ramps smoothly with the curve, and the accent square
// straddling the last stretch of the stroke instead of sitting beside it.
const SWASH_B3 = [K([4.6, 22.5], 0.15), K([8.8, 23.3], 0.55), K([15.6, 22.8], 0.85), K([27.4, 19.2], 0)];
const B3 = { spine: LETTER_B, bar: BAR_B, swash: SWASH_B3, accent: [25.6, 18.2, 2.0] };
const B3n = { spine: LETTER_B, bar: BAR_B, swash: SWASH_B3, accent: null };

// B4 — B3 with the pen taper held back: the feet and the swash keep enough weight to survive
// at 24 px instead of fading to a hairline.
const LETTER_B4 = [K([3.0, 20.6], 0.9), K([8.6, 2.8], 1.85), K([14.2, 20.6], 0.95)];
const SWASH_B4 = [K([4.6, 22.5], 0.35), K([8.8, 23.3], 0.75), K([15.6, 22.8], 0.9), K([27.4, 19.2], 0.2)];
const B4 = { spine: LETTER_B4, bar: BAR_B, swash: SWASH_B4, accent: [25.6, 18.0, 2.2] };

const CANDIDATES = { A, B, C, B2, B2n, B3, B3n, B4 };

const KEYS = ['A', 'B', 'C', 'B2', 'B2n', 'B3', 'B3n', 'B4'];
const shapes = {};
for (const [key, c] of Object.entries(CANDIDATES)) {
  const spine = ribbon(c.spine);
  const bar = ribbon(c.bar);
  const swash = c.swash ? ribbon(c.swash) : null;
  // The box comes from the ink itself, plus a uniform hairline of padding — never hand-set,
  // so no candidate can inherit someone else's empty margin.
  const parts = [spine.pts, bar.pts, swash ? swash.pts : bar.pts];
  if (c.accent) {
    parts.push([
      [c.accent[0], c.accent[1]],
      [c.accent[0] + c.accent[2], c.accent[1] + c.accent[2]],
    ]);
  }
  const [ix0, iy0, ix1, iy1] = box(parts);
  const pad = 0.25;
  const vb = `${n(ix0 - pad)} ${n(iy0 - pad)} ${n(ix1 - ix0 + 2 * pad)} ${n(iy1 - iy0 + 2 * pad)}`;
  shapes[key] = { spine: spine.d, bar: bar.d, swash: swash?.d ?? null, vb, accent: c.accent };
}

const hex = (c) => `#${c}`;
const mark = (key, size, color = 'currentColor', accentColor = hex('0F766E')) => {
  const s = shapes[key];
  return `<svg viewBox="${s.vb}" style="height:${size}px;width:auto" fill="${color}" xmlns="http://www.w3.org/2000/svg"><path d="${s.spine}"/>${s.swash ? `<path d="${s.swash}"/>` : ''}<path d="${s.bar}"/>${s.accent ? `<rect x="${s.accent[0]}" y="${s.accent[1]}" width="${s.accent[2]}" height="${s.accent[2]}" rx="0.5" fill="${accentColor}"/>` : ''}</svg>`;
};

const rows = [];for (const key of KEYS) {
  rows.push(
    `<div class="row"><span class="lab">${key} big</span><i id="cand-${key}-big">${mark(key, 460)}</i></div>`,
    `<div class="row"><span class="lab">${key} 160</span><i id="cand-${key}-160">${mark(key, 160)}</i></div>`,
    `<div class="row"><span class="lab">${key} 24</span><i id="cand-${key}-24">${mark(key, 24)}</i><canvas id="cand-${key}-24zoom"></canvas><span style="font:11px ui-monospace">&#8592; true 24 px raster, 8&#215; nearest</span></div>`,
    `<div class="row"><span class="lab">${key} 20</span><i>${mark(key, 20)}</i></div>`,
    `<div class="row ink"><span class="lab">${key} ink 96</span><i>${mark(key, 96, hex('FAF9F6'), hex('F5E6C8'))}</i></div>`,
    `<div class="row"><span class="lab">${key} lock</span><i style="display:inline-flex;align-items:center;gap:8px;height:28px">${mark(key, 28)}<span style="font:700 17px ui-sans-serif;letter-spacing:-.02em">Arbitrage<span style="color:${hex('0F766E')}">IQ</span></span></i></div>`,
  );
}
writeFileSync(
  'sheet.html',
  `<!doctype html><meta charset="utf-8"><style>
  body{margin:0;font:400 12px ui-sans-serif;background:#F3F1EC;color:#111827}
  .row{display:flex;align-items:center;gap:24px;padding:16px 22px;border-bottom:1px solid #E5E3DD}
  .ink{background:#111827;color:#FAF9F6;border-color:#2A2F3A}
  .lab{width:66px;opacity:.55;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
  i{display:block}
</style>${rows.join('\n')}
<script>
const jobs = ${JSON.stringify(KEYS)}.map(async (k) => {
  const svg = document.querySelector('#cand-' + k + '-24 > svg');
  const vb = svg.viewBox.baseVal;
  const h = 24, w = Math.round((24 * vb.width) / vb.height);
  const clone = svg.cloneNode(true);
  clone.setAttribute('width', w); clone.setAttribute('height', h);
  clone.removeAttribute('style');
  const img = new Image();
  img.src = 'data:image/svg+xml;base64,' + btoa(new XMLSerializer().serializeToString(clone));
  await img.decode();
  const small = document.createElement('canvas');
  small.width = w; small.height = h;
  small.getContext('2d').drawImage(img, 0, 0, w, h);
  const big = document.getElementById('cand-' + k + '-24zoom');
  big.width = w * 8; big.height = h * 8;
  const ctx = big.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(small, 0, 0, big.width, big.height);
});
window.__zoom = Promise.all(jobs);
</script>`,
);
writeFileSync('paths.json', JSON.stringify(shapes, null, 2));
for (const [k, s] of Object.entries(shapes)) console.log(`${k} viewBox="${s.vb}"\n  spine ${s.spine}\n  bar   ${s.bar}\n${s.swash ? '  swash ' + s.swash + '\n' : ''}`);
