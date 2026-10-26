# ACCEPTANCE_TESTS.md — Independently Defined Expected Values and Acceptance Matrix

| Field | Value |
|---|---|
| **Status** | Approved specification. **No source code exists. No test has been run. No test result may be claimed from this file.** |
| **Authority** | Third-highest. Overrides PRD, ARCHITECTURE, PHASES_DETAILED on required observed outcomes. Subordinate to `BUSINESS_RULES.md` on money/data and to an approved `DECISIONS.md` entry. |
| **Golden rule** | **Expected values in this file are defined independently of the code under test.** They are derived by hand from `BUSINESS_RULES.md` §10 and are written before the implementation exists. If a test fails, the first hypothesis is a bug in the code, not a stale expectation. Changing an expectation requires an approved `DECISIONS.md` entry. |

> Every number below is a **synthetic fixture**. Nothing here reflects a real marketplace, a real settlement, or real Indian tax law.

---

## How to read this file

- Each test has an **ID** (`AT-n`), referenced by `PHASES_DETAILED.md` as a done condition.
- `[P0]` = must pass before any P1 work starts. `[P1]` = only if all P0 pass.
- `Owner` names the module that must satisfy it, per `ARCHITECTURE.md`.
- A task is not "done" because code was written. It is done when the named checks pass **and the observed output is reported**.

---

## AT-1 — Golden fixture v1 (the arithmetic anchor) `[P0]` — Owner: `profit.py`

Fixture exactly as `BUSINESS_RULES.md` §10.1. Assert `Decimal("1624.08")`.

| # | Input variation | Expected | Why |
|---|---|---|---|
| AT-1.1 | Fixture v1 as stated | `Decimal("1624.08")` | The single most important assertion in the project |
| AT-1.2 | Fixture v1 with `fee_gst_recoverable = true` | `Decimal("1956.00")` (= 1624.08 + 331.92; fee GST removed: `9000.00 - 1844.00 - 5000.00 - 200.00`) | Proves the ITC switch is not a no-op |
| AT-1.3 | Fixture v1 with `returned_units = 0` | `Decimal("2624.08")` | Proves the return path is live. Derivation below |
| AT-1.4 | Fixture v1 with `settlement_fees_total = 2175.92` present | equals AT-1.1 (`1624.08`) | Proves §6 override is equivalent when the settlement figure matches the model, and never additive |
| AT-1.5 | Fixture v1 with `settlement_fees_total = 2175.92` **and** a changed `referral_rate` | still `1624.08` | Proves the fee model is genuinely bypassed, not merely overridden |
| AT-1.6 | Fixture v1 with `discount_per_unit = 118.00` | recompute by hand at implementation time and record before asserting |
| AT-1.7 | Fixture v1 with `product_gst_rate = 0.12` | recompute by hand at implementation time and record before asserting |
| AT-1.8 | Fixture v1 with `selling_price = 900.00` | referral becomes `0` (below the ₹1,000 floor); recompute and record |

**AT-1.3 derivation (independent, by hand):** with 0 returns, `gross_revenue = 10000.00` unchanged, `refunds = 0` so `net_revenue = 10000.00`, `fees_ex_gst = 1844.00`, `fee_gst = 331.92`, `product_cost = 5000.00`, `ads = 200.00`. Contribution `= 10000.00 - 1844.00 - 331.92 - 5000.00 - 200.00 = 2624.08`.

> **Process note.** AT-1.6 through AT-1.8 carry partially unverified expectations on purpose. The implementing agent must recompute each by hand from `BUSINESS_RULES.md` §4, write the derivation into the test file as a comment, and then assert. Any expectation that cannot be derived by hand must be **deleted**, not guessed.

---

## AT-2 — Rounding and money type `[P0]` — Owner: `money.py`, `profit.py`

| # | Check | Expected |
|---|---|---|
| AT-2.1 | `round_half_up(Decimal("0.005"))` | `Decimal("0.01")` |
| AT-2.2 | `round_half_up(Decimal("0.004"))` | `Decimal("0.00")` |
| AT-2.3 | `round_half_up(Decimal("-0.005"))` | `Decimal("-0.01")` (away from zero, documented choice) |
| AT-2.4 | Rounding is applied **per line then summed**, not at the aggregate | Two lines of `0.005` produce `0.02`, not `0.01` |
| AT-2.5 | No `float` appears in any money result | Type check: every monetary output is `Decimal` |
| AT-2.6 | Static check: no float literal in `money.py`, `profit.py`, `allocator.py` money paths | Lint rule passes |
| AT-2.7 | Transport round-trip through JSON | `Decimal("1624.08")` in ⇒ `"1624.08"` out ⇒ back to `Decimal("1624.08")`, exact |

---

## AT-3 — Zero, null and degenerate inputs `[P0]` — Owner: `profit.py`, API

| # | Input | Expected |
|---|---|---|
| AT-3.1 | `units_sold = 0`, `returned_units = 0` | `contribution = Decimal("0.00")`; `profit_per_unit = "n/a"`; `margin_pct = "n/a"` |
| AT-3.2 | `net_revenue = 0` but ads `> 0` | `contribution < 0`; `margin_pct = "n/a"` (never a division error) |
| AT-3.3 | `L = 0` (all three cost fields zero) | `roi_pct = "n/a"` |
| AT-3.4 | `returned_units = units_sold` (100% return) | `net_revenue = 0`, `product_cost = 0`, fees still charged on all shipped units, contribution is negative and finite |
| AT-3.5 | Negative per-unit economics | contribution is negative; no imaginary profit; `"n/a"` ratios behave per AT-3.1–3.3 |
| AT-3.6 | No `NaN`, `Infinity`, or `null` appears in any API money field across AT-1–AT-3 | assertion over the whole response object |

---

## AT-4 — Unit economics `[P0]` — Owner: `profit.py`

| # | Check | Expected |
|---|---|---|
| AT-4.1 | Break-even price for fixture v1 parameters (steady state, no returns, no ads) | Solution where single-unit contribution is exactly ≥ 0; boundary verified at `p` and `p - 0.01` |
| AT-4.2 | Break-even is labelled steady-state | The response carries a flag/field marking it as a pricing floor, not a forecast |
| AT-4.3 | Minimum price for target margin `m = 0.20` | Smallest `p` where `contribution / e >= 0.20`; boundary verified either side |
| AT-4.4 | Margin % denominator | `net_revenue`, not `e`, not `units_sold` |
| AT-4.5 | ROI % denominator | `L * units_sold` (gross shipped), not `L * n` |

---

## AT-5 — CSV validation: edge and attack matrix `[P0]` — Owner: `validation.py`, API

Every case must produce a **safe, human-readable** outcome. "Safe" means: no traceback, no stack trace, no file path, no SQL fragment, no server version, and no partial database write.

| # | Input | Expected response | Status |
|---|---|---|---|
| AT-5.1 | Missing required column (`products` without `sku`) | 422, lists every missing column name | 422 |
| AT-5.2 | Unexpected extra column | accepted, extra column ignored and reported as a warning | 200 |
| AT-5.3 | Empty file (0 bytes) | 422, "file is empty" | 422 |
| AT-5.4 | Header-only file | 200, `0 imported, 0 rejected` | 200 |
| AT-5.5 | Binary / non-UTF-8 content | 422, "not a readable CSV/text file" | 422 |
| AT-5.6 | Malformed quoted CSV | 422, row number reported | 422 |
| AT-5.7 | UTF-8 BOM prefix | accepted, headers normalised | 200 |
| AT-5.8 | Duplicate `transaction_id` within one file | later row rejected with reason; first kept | 200 |
| AT-5.9 | Re-upload of an already-imported file | 200, `0 imported, N skipped (duplicate)`; row count unchanged | 200 |
| AT-5.10 | `returned_units > units_sold` | row rejected with reason | 200 |
| AT-5.11 | `discount_per_unit > selling_price` | row rejected with reason | 200 |
| AT-5.12 | Non-numeric money value (`"abc"`, `"₹1,180"`, `"1180.00.00"`) | row rejected with the offending value quoted | 200 |
| AT-5.13 | Negative value in a `>= 0` field | row rejected with reason | 200 |
| AT-5.14 | `sku` in transactions absent from products | row rejected with reason, citing the SKU | 200 |
| AT-5.15 | File > 5 MB | 413, size cap named | 413 |
| AT-5.16 | File > 20,000 data rows | 413, row cap named, nothing written | 413 |
| AT-5.17 | Spreadsheet formula payload in a text cell (`=cmd\|'/c calc'!A0`, `@SUM(1)`) | `[P0 storage]` stored as literal text. `[P1 export]` only if the P1 export feature exists, prefixed (`'`) so it cannot execute | 200 |
| AT-5.18 | Filename containing `../` or a path | filename used only as a display label, never as a path | 200 |
| AT-5.19 | Mixed valid and invalid rows | 200 with `imported > 0` and a complete `rejected[]` list carrying row number + reason | 200 |
| AT-5.20 | The rejected-row list for a 19,000-row file | bounded; rejection report capped and summarised, never an unbounded payload | 200 |
| AT-5.21 | Two concurrent imports of the same file | exactly one wins on content hash; no duplicate rows | 200 |
| AT-5.22 | Any AT-5 case | response never contains a filesystem path, SQL text, or Python traceback | assertion over all responses |

---

## AT-6 — Idempotency and reconciliation `[P0]` — Owner: `reconcile.py`, `db.py`

| # | Check | Expected |
|---|---|---|
| AT-6.1 | Import → reconcile → import same file → reconcile | portfolio total identical both times |
| AT-6.2 | Per-SKU totals | sum of rounded per-line contributions equals the SKU total exactly |
| AT-6.3 | Portfolio total | equals the sum of SKU totals exactly (no re-rounding) |
| AT-6.4 | Seed catalogue loads | 10 products; transaction count matches the generated fixture file (asserted from the fixture, not from a constant in code) |
| AT-6.5 | Money stored in SQLite | retrieved value is bit-identical `Decimal`; column type is `NUMERIC`, never `REAL` |
| AT-6.6 | Sample catalogue contains a loss-making SKU | at least one SKU has negative contribution, proving the engine does not flatter the data |

---

## AT-7 — Budget Lab invariants `[P0]` — Owner: `allocator.py`

| # | Check | Expected |
|---|---|---|
| AT-7.1 | Randomised property test: 500 random catalogues × random budgets | AT-7 invariants B1–B8 hold on every run, no exceptions |
| AT-7.2 | Budget ₹500, sample catalogue | every `qty = 0`; spend `= 0` |
| AT-7.3 | Budget ₹3,000 | plan is non-empty, spend `<= 3000`, quantities shrink versus ₹50,000 |
| AT-7.4 | Spend never exceeds budget | asserted in **integer paise**, so no rounding edge can breach it |
| AT-7.5 | All quantities are integers | type assertion |
| AT-7.6 | Every non-zero quantity `>= min_order_qty` | per SKU |
| AT-7.7 | Every quantity `<= max_supply` | per SKU |
| AT-7.8 | Plan B: every SKU spend `<= 0.40 * budget` | per SKU |
| AT-7.9 | Plan A on the sample catalogue | concentrates into very few SKUs (that is the point of Plan A); concentration is reported, not hidden |
| AT-7.10 | Determinism | two runs, identical byte-for-byte output |
| AT-7.11 | `sell_through` lowered to 0.4 | every expected profit falls; ordering is stable; no error |
| AT-7.12 | `salvage = 0` | unsold units contribute no recovery; results remain finite |
| AT-7.13 | A SKU with negative per-unit economics | receives `qty = 0` in Plan A |
| AT-7.14 | Conservative scenario worse than base for every plan | asserted, confirming the shock is applied |
| AT-7.15 | Response never contains the word "optimal" or "guaranteed" | string assertion over the serialised payload and any plan labels |

---

## AT-8 — REST API contract `[P0]` — Owner: `api.py`

| # | Endpoint | Method | Happy path | Failure cases asserted |
|---|---|---|---|---|
| AT-8.1 | `/health` | GET | 200 `{status, version, db}` | 503 when the DB is unreachable |
| AT-8.2 | `/assumptions` | GET | 200, full assumption object | — |
| AT-8.3 | `/assumptions` | PUT | 200, echoed validated object | 422 on out-of-range rate; 422 on negative fee (see `BUSINESS_RULES.md` R2) |
| AT-8.4 | `/products` | GET | 200 list | 200 empty list when catalogue is empty (not 404) |
| AT-8.5 | `/import/validate` | POST | 200 dry-run report, **nothing persisted** | 413 oversize; 422 unreadable; 422 missing column |
| AT-8.6 | `/import` | POST | 200 `{imported, skipped, rejected[]}` | same as AT-8.5, plus AT-5.8/5.9 idempotency |
| AT-8.7 | `/profit/sku/{sku}` | GET | 200 full breakdown | 404 unknown SKU with a clean error body |
| AT-8.8 | `/profit/reconcile` | GET | 200 per-SKU + portfolio totals | 200 empty-state body when no transactions exist |
| AT-8.9 | `/budget/simulate` | POST | 200 both plans + conservative scenario | 422 budget `<= 0`; 422 `max_share_per_sku` outside `(0,1]`; 422 unknown SKU in candidate list |
| AT-8.10 | Any endpoint | — | — | error bodies are typed and consistent: `{error, detail, field?}` — never a bare string |
| AT-8.11 | `/docs` | GET | 200 OpenAPI UI | — |
| AT-8.12 | Every money field | — | serialised as a JSON **string** decimal, never a float | type assertion across all payloads |

> `DELETE /import/{batch_id}` is **P1**, not P0. It must not appear as a P0 done condition.

---

## AT-9 — Security and privacy acceptance `[P0]` — Owner: whole repo

| # | Check | Expected |
|---|---|---|
| AT-9.1 | Secret scan over the repo | no `password`, `secret`, `token`, `api_key`, or private key material |
| AT-9.2 | `.gitignore` | covers `.env`, `*.db`, `*.sqlite*`, `data/private/`, virtualenvs, `node_modules`, build output |
| AT-9.3 | Database access | every query is parameterised; no string-built SQL; no `eval` on user content |
| AT-9.4 | Logs | contain no row values, no filenames with user content, no PII (no customer name, phone, or address) |
| AT-9.5 | Sample data | contains no real person, brand, phone number, address, or real order ID |
| AT-9.6 | Production CORS | allowlist, not `*` (documented in `SECURITY.md`; local dev may use a localhost allowlist) |
| AT-9.7 | Upload limits | 5 MB and 20,000 rows enforced **server-side** even if the client checks too |
| AT-9.8 | Export safety | `[P0 storage]` stored as literal text. `[P1 export]` only if the P1 export feature exists: any exported cell beginning `=`, `+`, `-`, or `@` is neutralised |
| AT-9.9 | No live integration | no outbound call to Amazon or any marketplace anywhere in the codebase |

---

## AT-10 — End-to-end user journey `[P0]` — Owner: frontend + API

| # | Journey step | Expected observable |
|---|---|---|
| AT-10.1 | Fresh start, no data | every view shows an informative empty state, never a blank panel or a crash |
| AT-10.2 | Load the synthetic sample | catalogue and transactions appear; DEMO DATA badge is visible |
| AT-10.3 | Upload a CSV with 3 bad rows | import summary shows `imported` and `rejected`, each rejection with a row number and a reason |
| AT-10.4 | Open Profitability | per-SKU table with contribution; a loss-making SKU is visibly distinguishable **without relying on colour alone** |
| AT-10.5 | Open one SKU drilldown | the full breakdown reconciles to the headline contribution figure |
| AT-10.6 | Every displayed money figure | has a visible assumptions/methodology affordance adjacent to it |
| AT-10.7 | Budget Lab, ₹50,000 | both plans render; capital used shown; assumptions labelled ASSUMED |
| AT-10.8 | Lower the budget to ₹500 | both plans visibly buy nothing, with an explanatory message |
| AT-10.9 | Move `sell_through` to 0.4 | expected profits fall immediately; no error state |
| AT-10.10 | Set an invalid assumption (e.g. 150% GST) | rejected with a clear message; previous value retained |
| AT-10.11 | Open Methodology | the disclaimer text, the five profit terms, and the downside-scenario limitation all present verbatim |
| AT-10.12 | Resize to phone width (375 px) | no horizontal scroll, no clipped controls, all five views usable |
| AT-10.13 | Keyboard-only navigation | every interactive control reachable and operable; visible focus ring |
| AT-10.14 | Whole journey | no screen contains the word "optimal", "guaranteed", or a claim of sales prediction |
| AT-10.15 | Whole journey | loading, empty, and error states all reachable and informative |

---

## AT-11 — Reproducibility and release readiness `[P0]` — Owner: whole repo

| # | Check | Expected |
|---|---|---|
| AT-11.1 | Clean clone into a **new** directory | succeeds |
| AT-11.2 | Fresh virtual environment + install from the pinned requirements | succeeds with README steps only |
| AT-11.3 | `pytest` | all P0 tests pass |
| AT-11.4 | `ruff check` and format check | clean |
| AT-11.5 | `npm ci` and `npm run build` | production build succeeds, no TypeScript errors |
| AT-11.6 | Backend + frontend started per README | both reachable; the five views work |
| AT-11.7 | Secrets | none; `.env` and database files ignored |
| AT-11.8 | README | states startup steps, the synthetic-data policy, and every deferred integration |
| AT-11.9 | Screenshots / demo video | depict the actually running application, never mock screens |
| AT-11.10 | Independent recomputation | a human recomputes 3 SKUs by hand and agrees with the app |

> Until source code exists, **every row above is unverified.** No agent may write a pass/fail status into `PROGRESS.md` without pasting the observed command output.

---

## AT-12 — P1 acceptance `[P1 — only if every P0 row above passes]`

| # | Check | Expected |
|---|---|---|
| AT-12.1 | Simple inventory warning | SKUs below a stock-cover threshold are flagged, labelled "for human review", with no repricing instruction |
| AT-12.2 | One extra visualisation | renders with the loaded (synthetic) data and has an accessible text alternative |
| AT-12.3 | Public deployment (optional) | demo data only, CORS allowlisted, no secrets in the environment, size limits active |
| AT-12.4 | `DELETE /import/{batch_id}` | removes exactly the batch's rows; totals recompute correctly |

---

## Traceability — acceptance ID → build task

| Task (`PHASES_DETAILED.md`) | Acceptance IDs |
|---|---|
| T01 Repository skeleton and tooling | AT-11.2 (install from pinned requirements); `GET /health` 200 |
| T02 Decimal money primitives | AT-2.1–2.3, AT-2.5, AT-2.6 |
| T03 Assumption configuration model | AT-8.3 via T10 (the R2 validation rules the endpoint surfaces) |
| T04 Contribution engine and the golden fixture | AT-1.1–1.5, AT-2.4, AT-2.7, AT-3.1–3.6 |
| T05 Unit economics | AT-4.1–4.5 |
| T06 CSV validation core | AT-5.1–5.7, AT-5.10–5.16, AT-5.19, AT-5.20, AT-5.22 |
| T07 CSV attack and edge matrix | AT-5.8, AT-5.9, AT-5.17, AT-5.18, AT-5.21 |
| T08 Persistence models, seed and the sample generator | AT-6.4, AT-6.5, AT-6.6 |
| T09 Import, reconcile and idempotency | AT-6.1–6.3, AT-5.9, AT-5.21 if it moved here |
| T10 REST API and error contract | AT-8.1–8.12 (re-asserts AT-5.22 at the API boundary) |
| T11 Allocator heuristics and invariants | AT-7.1–7.10, AT-7.13–7.15 |
| T12 Budget simulation endpoint and downside scenario | AT-7.11, AT-7.12, AT-7.14, AT-8.9 |
| T13 Frontend shell, typed API client and design tokens | AT-10.1, AT-10.2 |
| T14 Overview and Import views | AT-10.3 |
| T15 Profitability and Budget Lab views | AT-10.4–10.9 |
| T16 Methodology view, responsive and accessibility pass, stabilisation | AT-1.6–1.8 (if deferred from T04), AT-9.1–9.9, AT-10.10–10.15, AT-11.1–11.10 |
| **P1 candidates (unscheduled — see `PHASES_DETAILED.md` "P1 tasks")** | AT-12.1, AT-12.2, AT-12.3, AT-12.4 |

---

## What this file must never contain

- A claimed test run, pass count, or timing, before source code exists.
- An expected value copied from a running implementation.
- Real Amazon fees, real GST slabs, real demand, or real settlement data.
- A P2 capability dressed as an acceptance test.

## Cross-references

- All formulas and field semantics: `BUSINESS_RULES.md`
- Module ownership: `ARCHITECTURE.md`
- Task definitions consuming these IDs: `PHASES_DETAILED.md`
- Privacy and upload rules: `SECURITY.md`
- Decisions that changed an expectation: `DECISIONS.md`
