# PHASES_DETAILED.md — Sixteen Bounded Implementation Tasks

| Field | Value |
|---|---|
| **Status** | Approved specification. Day 0. No task has started. |
| **Authority** | Sixth, on task breakdown. Subordinate to `DECISIONS.md`, `BUSINESS_RULES.md`, `ACCEPTANCE_TESTS.md`, `PRD.md`, `TECH_STACK.md`, `ARCHITECTURE.md`, `MASTER_PLAN.md`. |
| **Count** | **16 tasks.** This count stays between 12 and 16. A task that cannot fit its timebox takes its fallback; it is never split into microphases. |
| **Rule** | Each task is one vertical slice that changes a testable user outcome. A task's file list is its **ownership boundary** — an agent does not write outside it without saying so first. |

---

## How to use this file

1. Read `../AGENTS.md`, then `CONTEXT.md`, then `PROGRESS.md`.
2. Take the **one** task whose prerequisites are met and whose status is not `Done`.
3. Before editing, state: the task ID, the files you will touch, the done condition, and the acceptance IDs that prove it.
4. Implement only that slice.
5. Run the task's checks: targeted test → full backend suite → frontend build where relevant.
6. Report using the format in `../AGENTS.md`, with pasted output.
7. Update `PROGRESS.md`, then stop for human review before committing.

**Definition of done for every task:** the named acceptance IDs pass, the full backend test suite is green, `npm run build` is clean if frontend files changed, the report is recorded in `PROGRESS.md`, and the full diff has been reviewed.

---

## Day 1 — Foundation and financial truth

### T01 — Repository skeleton and tooling

| | |
|---|---|
| **Objective** | A repository that installs, lints, tests (zero tests) and runs an empty API, with resolved dependency versions recorded. |
| **Prerequisite** | None. This is the first task. The documentation gate (CP-1) must be passed. |
| **Files owned** | `.gitignore`, `README.md` (stub only), `backend/pyproject.toml`, `backend/requirements.txt`, `backend/ruff.toml`, `backend/arbitrageiq/__init__.py`, `backend/arbitrageiq/api.py` (health route only), `backend/tests/__init__.py`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/tailwind.config.js`, `data/private/.gitkeep` |
| **Done condition** | `pip install -r backend\requirements.txt` succeeds; `uvicorn arbitrageiq.api:app --port 8000` serves `GET /health` returning 200; `ruff check backend` is clean; `cd frontend; npm ci; npm run build` succeeds; `.gitignore` covers every path in `SECURITY.md` §4.2; resolved versions recorded in `PROGRESS.md` §6 and in `TECH_STACK.md`. |
| **Checks** | Unit: none. Integration: `GET /health` → 200. E2E: frontend builds to `dist/`. |
| **Fallback** | If npm tooling stalls, ship the backend skeleton only, record the frontend as blocked, and move to T02 — the financial core does not depend on the frontend. |
| **Time** | 0.5 h |
| **Agent prompt** | "Create the repository skeleton for ArbitrageIQ per `plans/ARCHITECTURE.md` §2 and `plans/TECH_STACK.md` §5.1–5.4. Create only the files listed in T01 of `plans/PHASES_DETAILED.md`. Do not create any other application module. Include a `.gitignore` covering everything in `plans/SECURITY.md` §4.2, a Ruff config with a guard against float literals in money modules, and an `api.py` containing only `GET /health`. Then run the four verification commands and report the observed output verbatim." |

---

### T02 — Decimal money primitives

| | |
|---|---|
| **Objective** | One module owning money representation, rounding and ratio behaviour. |
| **Prerequisite** | T01 |
| **Files owned** | `backend/arbitrageiq/money.py`, `backend/tests/test_money.py` |
| **Done condition** | `round_half_up` is half-up and away from zero on exact halves; a ratio helper returns the literal `"n/a"` for a zero or missing denominator and never raises; a money value is always `Decimal`, never `float`; the module imports nothing project-local. |
| **Checks** | Unit: AT-2.1, AT-2.2, AT-2.3, AT-2.5. Integration: AT-2.6 lint pass on this module. E2E: — |
| **Fallback** | None needed. This task is small, and everything after it depends on it. |
| **Time** | 0.5 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/money.py` for ArbitrageIQ. Read `plans/BUSINESS_RULES.md` §4 (rounding rule and ratio rule) and §8 (zero-denominator behaviour), plus `plans/ACCEPTANCE_TESTS.md` AT-2. Write `backend/tests/test_money.py` first, with expectations taken from AT-2, then implement to make it pass. The module may import only `decimal` and `typing`. Do not implement any formula from §4 of BUSINESS_RULES beyond rounding and ratio handling — that belongs to T04." |

---

### T03 — Assumption configuration model

| | |
|---|---|
| **Objective** | The dated, validated assumption set that every financial calculation reads. |
| **Prerequisite** | T02 |
| **Files owned** | `backend/arbitrageiq/config.py`, `backend/tests/test_config.py` |
| **Done condition** | Every key in `BUSINESS_RULES.md` §2 exists with the stated default and type; validation rejects every out-of-range value named in R2 with a specific message naming the field; the active-assumption lookup is by effective date; the module imports only `money`. |
| **Checks** | Unit: defaults match the §2 table; each R2 violation raises a distinct error. Integration: — (the API surface arrives in T10). E2E: — |
| **Fallback** | If dated lookup proves fiddly, ship a single active record plus an `effective_from` field, and record the simplification in `PROGRESS.md` as a deviation. |
| **Time** | 0.5 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/config.py` for ArbitrageIQ from the table in `plans/BUSINESS_RULES.md` §2 and the validation rules R2 and R3. Every default, type and range must match that table exactly — do not invent a rate. Money fields are `Decimal`, rates are `Decimal` in the documented range, booleans are booleans. Write the tests first from §2 and R2. Import only `money` plus the standard library." |

---

### T04 — Contribution engine and the golden fixture

| | |
|---|---|
| **Objective** | The per-transaction contribution calculation, reproducing ₹1,624.08 exactly, with a full breakdown and the settlement-override rule. |
| **Prerequisite** | T02, T03 |
| **Files owned** | `backend/arbitrageiq/profit.py`, `backend/tests/test_profit.py`, `backend/tests/fixtures/golden_v1.json` |
| **Done condition** | `compute_line` follows `BUSINESS_RULES.md` §4 in the stated order, rounds once per line, returns a full breakdown (net revenue, product cost, fees, GST on fees, ads, other, contribution), and returns `Decimal("1624.08")` for fixture v1. A non-null `settlement_fees_total` bypasses the fee model entirely. `fee_gst_recoverable = true` changes the result. `units_sold` is treated as gross. |
| **Checks** | Unit: AT-1.1, AT-1.2, AT-1.3, AT-1.4, AT-1.5, AT-2.4, AT-2.7, AT-3.1–3.6. Integration: a reconciliation test showing the breakdown sums to the headline. E2E: — |
| **Fallback** | AT-1.6, AT-1.7 and AT-1.8 (variant expectations needing hand derivation) may be deferred to T16 with an explicit `PROGRESS.md` note. The primary fixture is never deferred. |
| **Time** | 2.0 h. **The highest-value block in the project.** |
| **Agent prompt** | "Implement `backend/arbitrageiq/profit.py` for ArbitrageIQ. Read `plans/BUSINESS_RULES.md` §3 (especially the gross-vs-net warning), §4, §5, §6 and §10 in full before writing anything. Derive the expected values for AT-1.1 to AT-1.5 **by hand** from the fixture table in §10.1 and write them as literals in `backend/tests/test_profit.py` (first, failing). Then implement to make them pass. The module may import only `money` and `config`. Never use `float`. Never apply the fee model to a line that carries settlement fees. If any expected value does not reproduce exactly, treat it as a code bug and report it — do not adjust the expectation." |

---

### T05 — Unit economics

| | |
|---|---|
| **Objective** | Profit per unit, margin %, ROI %, break-even price and target-margin price. |
| **Prerequisite** | T04 |
| **Files owned** | `backend/arbitrageiq/profit.py` (economics functions only), `backend/tests/test_economics.py` |
| **Done condition** | Each metric uses the denominator specified in `BUSINESS_RULES.md` §8; `n/a` is returned for a zero denominator; break-even and target-margin prices are solved on the steady-state single-unit case and are labelled as a pricing floor; the break-even boundary is correct at `p` and `p − 0.01`. |
| **Checks** | Unit: AT-4.1, AT-4.3, AT-4.4, AT-4.5. Integration: AT-4.2, the response carries the steady-state marker. E2E: — |
| **Fallback** | Target-margin price may be dropped if the solve is slow; then remove AT-4.3 from the task's claims and note it in `PROGRESS.md`. Break-even is not droppable. |
| **Time** | 1.0 h |
| **Agent prompt** | "Add the unit-economics functions to `backend/arbitrageiq/profit.py`, per `plans/BUSINESS_RULES.md` §8. Denominators must match that table exactly — margin uses net revenue, ROI uses landed cost times gross units shipped. Ratios with a zero denominator return the literal `'n/a'`. Break-even and target-margin prices use the steady-state single-unit case and must be flagged as a pricing floor. Tests first, from AT-4." |

---

**★ CP-2 gate:** `pytest backend/tests/test_profit.py -q` must be green, including `1624.08` exactly, before any CSV or database code is written.

---

## Day 2 — Ingestion, persistence and API

### T06 — CSV validation core

| | |
|---|---|
| **Objective** | A CSV reader that never crashes, keeps good rows, rejects bad ones with reasons, and enforces caps. |
| **Prerequisite** | T03 (for the assumption ranges it validates against) |
| **Files owned** | `backend/arbitrageiq/validation.py`, `backend/tests/test_validation.py`, `backend/tests/fixtures/*.csv` |
| **Done condition** | Files are read as text; headers are normalised for case, whitespace and BOM and mapped through the alias table in `DECISIONS.md` ADR-021; each row is validated against a `ColumnSpec` list with type, range and referential checks; rejects are collected, never raised; a file that cannot be read at all raises `CsvReadError`; the 5 MB and 20,000-row caps are enforced before parsing; rejection reports are bounded. |
| **Checks** | Unit: AT-5.1–5.7, AT-5.10–5.16, AT-5.19, AT-5.20. Integration: AT-5.22, no path, SQL text or traceback in any message. E2E: — |
| **Fallback** | Alias-column support may be dropped (accept only the canonical names), with AT-5.2 recorded as cut and `ADM` noted in `PROGRESS.md`. The caps and the reject behaviour are not droppable. |
| **Time** | 2.0 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/validation.py` per `plans/BUSINESS_RULES.md` §3 and `plans/ARCHITECTURE.md` §4.1, proved by `plans/ACCEPTANCE_TESTS.md` AT-5.1–5.7 and AT-5.10–5.16. Read all files as text (`dtype=str`) and parse every cell explicitly to `Decimal`, `int` or `date` — pandas must never compute money. Collect per-row rejects with row number, field, offending value and a plain-language reason. Never raise for a bad row; raise `CsvReadError` only for a file that cannot be read. This module must not import `profit`, `db` or `api`. Create the CSV fixtures under `backend/tests/fixtures/` to match the AT-5 matrix." |

---

### T07 — CSV attack and edge matrix

| | |
|---|---|
| **Objective** | The remaining import safety cases: duplicate handling, formula injection, hostile filenames, concurrency. |
| **Prerequisite** | T06 |
| **Files owned** | `backend/arbitrageiq/validation.py` (duplicate detection and sanitisation only), `backend/arbitrageiq/money.py` (only if a shared sanitiser is needed), `backend/tests/test_validation_safety.py`, `backend/tests/fixtures/malicious_*.csv` |
| **Done condition** | Duplicate `transaction_id` within a file keeps the first and rejects the rest with a reason; a text cell beginning `=`, `+`, `-` or `@` is stored as literal text (export-time neutralisation applies only if the P1 export feature exists); a filename containing `../`, `/`, `\` or a drive letter is used only as a display label; two concurrent imports of the same content resolve deterministically to one winner. |
| **Checks** | Unit: AT-5.8, AT-5.17, AT-5.18. Integration: AT-5.21, AT-5.9 (idempotency, shared with T09). E2E: — |
| **Fallback** | Concurrency (AT-5.21) may be deferred if the database write path is not ready; it is then T09's responsibility and must be recorded as moved, not dropped. |
| **Time** | 1.0 h |
| **Agent prompt** | "Extend the import path with the safety cases in `plans/ACCEPTANCE_TESTS.md` AT-5.8, AT-5.17, AT-5.18 and AT-5.21. Formula-injection neutralisation must be a single shared helper: it applies at storage time in P0, and must also be applied at export time if the P1 export feature is ever added. Filenames are display labels only — never a path. Add malicious fixtures under `backend/tests/fixtures/`. Tests first." |

---

### T08 — Persistence models, seed and the sample generator

| | |
|---|---|
| **Objective** | Real tables with `NUMERIC` money, and a deterministic synthetic dataset that loads. |
| **Prerequisite** | T03 |
| **Files owned** | `backend/arbitrageiq/models.py`, `backend/arbitrageiq/db.py`, `scripts/make_sample_data.py`, `data/sample/products_sample.csv`, `data/sample/transactions_sample.csv`, `backend/tests/test_db.py` |
| **Done condition** | The ERD in `ARCHITECTURE.md` §5 exists with the stated keys and nullability; every money column reflects as `NUMERIC`, never `REAL`; `python -m arbitrageiq.db init` creates the schema and `seed` loads `data/sample/` and prints an observed summary; the generator is deterministic (byte-identical output across runs); the catalogue contains at least one loss-making SKU; no real brand, person, phone number, address or order ID appears anywhere. |
| **Checks** | Unit: AT-6.5 (reflected column types), AT-6.6 (a loss-making SKU exists). Integration: AT-6.4, seed summary matches the generated file's actual row count. E2E: — |
| **Fallback** | If the generator is troublesome, hand-author a smaller synthetic CSV — but it must still be deterministic, still contain a loss-making SKU, and still contain no real data. Record the simplification. |
| **Time** | 1.5 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/models.py` and `db.py` from `plans/ARCHITECTURE.md` §5, and `scripts/make_sample_data.py` producing deterministic synthetic fixtures under `data/sample/`. Money columns are `NUMERIC`; add a test that reflects the schema and asserts no money column is `REAL`. Per `plans/DECISIONS.md` ADR-020, the portfolio total is **not** a fixed target — do not tune the data to a specific total; instead ensure at least one SKU loses money and that the data exercises both the return path and the settlement-override path. No real names, numbers or addresses." |

---

### T09 — Import, reconcile and idempotency

| | |
|---|---|
| **Objective** | Loading files into the database without duplicating, and summing contribution per SKU from real rows. |
| **Prerequisite** | T04, T06, T07, T08 |
| **Files owned** | `backend/arbitrageiq/reconcile.py`, `backend/arbitrageiq/loaders.py`, `backend/tests/test_reconcile.py` |
| **Done condition** | Importing a file twice changes no row count; per-SKU totals equal the sum of rounded line contributions exactly; the portfolio total equals the sum of SKU totals exactly; the bundled sample loads through `loaders.py`; reconciliation reads the active assumptions, not defaults. |
| **Checks** | Unit: AT-6.2, AT-6.3. Integration: AT-6.1 (idempotent reimport), AT-5.9, AT-5.21 if it moved here. E2E: — |
| **Fallback** | If the content-hash mechanism is the blocker, dedupe on `transaction_id` alone and record the narrower guarantee explicitly in `PROGRESS.md` and `DECISIONS.md`. |
| **Time** | 1.0 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/reconcile.py` and `loaders.py` per `plans/ARCHITECTURE.md` §4.2. Aggregation sums **already-rounded** per-line contributions (`plans/BUSINESS_RULES.md` §9) — never re-round an aggregate. Prove idempotency by importing the sample twice and asserting the row count is unchanged, and by asserting the portfolio total is identical both times (AT-6.1). Tests first." |

---

### T10 — REST API and error contract

| | |
|---|---|
| **Objective** | The nine P0 endpoints with a uniform, safe error body and decimal-string money. |
| **Prerequisite** | T09 |
| **Files owned** | `backend/arbitrageiq/schemas.py`, `backend/arbitrageiq/api.py`, `backend/tests/test_api.py` |
| **Done condition** | All endpoints in `ARCHITECTURE.md` §6 behave as specified; every non-2xx response uses `{error, detail, field?}`; every monetary field is a JSON string; ratio fields are strings or `"n/a"`; size and row caps surface as 413 with the cap named; a missing `sku` is 404; an out-of-range assumption is 422 naming the field; no response contains a path, SQL text or traceback; `/docs` renders; `POST /budget/simulate` may be a stub that returns 501 **only until T12** — 501 is not permitted after T12. |
| **Checks** | Unit: AT-8.1–8.12. Integration: AT-5.22 over every endpoint response (re-asserts the T06/T07 sanitisation at the API boundary). E2E: manual `/docs` exercise of `/profit/sku/{sku}` with fixture v1 → `1624.08`. |
| **Fallback** | `PUT /assumptions` may ship as read-only (GET only) if write-path validation is the blocker; record AT-8.3 as cut. |
| **Time** | 2.0 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/schemas.py` and `api.py` per `plans/ARCHITECTURE.md` §6, with acceptance from `plans/ACCEPTANCE_TESTS.md` AT-8.1–8.12. Decide and record the base-path prefix here. Money is serialised as a decimal string — verify by asserting the raw JSON contains `\"1624.08\"` and not `1624.08`. One exception handler normalises every error to `{error, detail, field?}`; no handler may leak SQL text, a path or a traceback. `/budget/simulate` may be a temporary 501 stub until T12, but it must exist and it must return the uniform error shape; **the 501 stub must be removed by T12**." |

---

**★ CP-3 gate:** AT-5, AT-6 and AT-8 green; an oversized, empty, binary or malformed upload produces a safe 4xx with nothing persisted; a re-upload changes no row count.

---

## Day 3 — Budget Lab and the interface

### T11 — Allocator heuristics and invariants

| | |
|---|---|
| **Objective** | Two transparent greedy strategies that respect the budget and every constraint, provably. |
| **Prerequisite** | T04, T05, T08 |
| **Files owned** | `backend/arbitrageiq/allocator.py`, `backend/tests/test_allocator.py` |
| **Done condition** | `expected_profit` matches `BUSINESS_RULES.md` §11.2; `score` matches ADR-017; Plan A ranks by score with no cap; Plan B applies the per-SKU spend cap; every invariant B1–B10 holds; spend is compared in integer paise so a rounding edge cannot breach the budget; a SKU with non-positive per-unit economics receives zero in Plan A; output is deterministic; no `float` appears in any money path. |
| **Checks** | Unit: AT-7.2–7.10, AT-7.13, AT-7.15. Integration: AT-7.1, the 500-case randomised sweep asserting B1–B8 on every run. E2E: — |
| **Fallback** | If the randomised sweep is slow to write without `hypothesis`, use a fixed seed and 500 explicit cases — the sweep must still exist, because AT-7.1 is the single check that catches a budget breach. |
| **Time** | 1.5 h |
| **Agent prompt** | "Implement `backend/arbitrageiq/allocator.py` from `plans/BUSINESS_RULES.md` §11 and `plans/DECISIONS.md` ADR-016 and ADR-017. Two greedy strategies, one shared score. **No `float` and no numpy** — money is `Decimal`, and the spend comparison is in integer paise so the never-overspend invariant is exact. Write the invariant property test (AT-7.1) first: 500 randomised catalogues asserting B1–B8 on every run. Add a string assertion that no plan label or payload contains 'optimal', 'best', 'maximises' or 'guaranteed'. This module may import `money`, `config` and `profit` only." |

---

### T12 — Budget simulation endpoint and downside scenario

| | |
|---|---|
| **Objective** | Wiring the allocator to the API, with the conservative scenario and the required honesty statement. |
| **Prerequisite** | T10, T11 |
| **Files owned** | `backend/arbitrageiq/api.py` (`/budget/simulate` only), `backend/arbitrageiq/schemas.py` (budget schemas only), `backend/tests/test_budget_api.py` |
| **Done condition** | `POST /budget/simulate` returns both plans plus the conservative scenario, each with capital used, budget remaining, expected contribution, per-SKU quantities, and a per-line ASSUMED flag; the conservative row reflects price × 0.95 and sell-through × 0.75 with fees recomputed; a budget of ₹500 buys nothing; out-of-range controls are 422 naming the field; an invariant breach returns 500 and never a silently wrong plan; the response carries the uniform-diversification limitation text. |
| **Checks** | Unit: AT-7.11, AT-7.12, AT-7.14. Integration: AT-8.9. E2E: ₹50,000 and ₹500 exercised through the API. |
| **Fallback** | If persisting plan runs is the blocker, return the plan without storing it and update `ARCHITECTURE.md` §5 to say so (this is `MASTER_PLAN.md` drop-list item 6). |
| **Time** | 1.0 h |
| **Agent prompt** | "Wire the allocator to `POST /budget/simulate` per `plans/ARCHITECTURE.md` §4.3 and `plans/ACCEPTANCE_TESTS.md` AT-8.9. Assert the invariants at the API boundary: a breach returns 500 and never a plausible-looking plan. Include the conservative scenario and the required honesty statement about uniform shocks, taken from `plans/BUSINESS_RULES.md` §11.3. Exercise ₹50,000 and ₹500 in the tests." |

---

### T13 — Frontend shell, typed API client and design tokens

| | |
|---|---|
| **Objective** | A five-route shell that renders loading, empty, error and content states, with money treated as a string end to end. |
| **Prerequisite** | T01, T10 |
| **Files owned** | `frontend/src/main.tsx`, `App.tsx`, `frontend/src/api/client.ts`, `frontend/src/api/types.ts`, `frontend/src/components/` (DemoBadge, EmptyState, ErrorState, Loading, MoneyCell, AssumptionPanel), `frontend/tailwind.config.js`, `frontend/src/index.css` |
| **Done condition** | Five routes exist and are reachable; the client normalises network, 4xx and 5xx into typed states; every money field is typed `string` and is never parsed to a number; the DEMO DATA badge is always visible when sample data is loaded; the palette follows `TECH_STACK.md` §3 and §6 (navy/near-white neutrals, teal/green for positive, amber for warnings) and never relies on colour alone; layout is usable at 375 px. |
| **Checks** | Unit: none in P0. Integration: AT-10.1 (informative empty state on every view, no blank panel, no crash). E2E: AT-10.2, the sample loads and the badge appears. |
| **Fallback** | If routing is the blocker, render all five views in one scrollable page with anchors and record the simplification; the view *content* requirements are not droppable. |
| **Time** | 1.0 h |
| **Agent prompt** | "Create the frontend shell for ArbitrageIQ per `plans/ARCHITECTURE.md` §2 and §4.4, and `plans/PRD.md` §4 and §5. Five routes. A typed `fetch` wrapper normalising network, 4xx and 5xx into four renderable states. `api/types.ts` declares every monetary field as `string` and the client never calls `Number()` or `parseFloat` on one. Build the shared state components first. No state-management library, no component library, no charting library, no icon package." |

---

### T14 — Overview and Import views

| | |
|---|---|
| **Objective** | A hero view that conveys one decision, and an import view that makes ingestion trustworthy. |
| **Prerequisite** | T13 |
| **Files owned** | `frontend/src/views/Overview.tsx`, `frontend/src/views/Import.tsx`, `frontend/src/components/ImportSummary.tsx`, `frontend/src/components/RejectionTable.tsx` |
| **Done condition** | Overview shows portfolio contribution, net revenue and capital at cost, plus a plain-language profitable/loss-making count and links onward; it shows no forecast or trend; Import offers a file picker, a dry-run action and a one-click synthetic sample load; the import summary shows imported, skipped and rejected counts; the rejection table lists row number, field, value and reason; the 5 MB and 20,000-row caps are stated; an unreadable file produces a plain message and never a stack trace. |
| **Checks** | Unit: none in P0. Integration: AT-10.3, a CSV with three bad rows reports three rejections with row numbers. E2E: dry run persists nothing; a real import updates the summary. |
| **Fallback** | The dry-run button may be dropped if the endpoint wiring stalls, but the real import path and its rejection report are not droppable. |
| **Time** | 1.0 h |
| **Agent prompt** | "Implement `Overview.tsx` and `Import.tsx` per `plans/PRD.md` §4.1 and §4.2, with acceptance from AT-10.3. The Overview conveys a single decision, not a dashboard — no charts, no trends, no forecast. The Import view must show a per-row rejection reason and must state the caps. All four states must exist on both views. No money arithmetic in TypeScript." |

---

### T15 — Profitability and Budget Lab views

| | |
|---|---|
| **Objective** | The reconciliation table with a working drilldown, and the two-plan comparison with an immediate downside scenario. |
| **Prerequisite** | T12, T13 |
| **Files owned** | `frontend/src/views/Profitability.tsx`, `frontend/src/views/BudgetLab.tsx`, `frontend/src/components/SkuTable.tsx`, `frontend/src/components/SkuDrilldown.tsx`, `frontend/src/components/PlanCard.tsx` |
| **Done condition** | The Profitability table shows every column in `PRD.md` §4.3; a loss-making SKU is distinguishable **without relying on colour alone**; the drilldown shows the per-line breakdown and reconciles to the headline figure; `n/a` renders for zero-denominator ratios; Budget Lab has an editable budget, sell-through and salvage, each labelled ASSUMED, a cap control, two plan cards and a conservative row; controls recompute immediately; ₹500 visibly buys nothing with an explanation; the honesty statement from `BUSINESS_RULES.md` §11.3 is present verbatim. |
| **Checks** | Unit: none in P0. Integration: AT-10.4, AT-10.5, AT-10.6, AT-10.7, AT-10.8, AT-10.9. E2E: the drilldown reconciles; moving sell-through to 0.4 moves the numbers with no error state. |
| **Fallback** | The drilldown is the per-line table only — no chart is in P0. The cap control may become read-only. The reconciliation requirement is not droppable. |
| **Time** | 2.0 h |
| **Agent prompt** | "Implement `Profitability.tsx` and `BudgetLab.tsx` per `plans/PRD.md` §4.3 and §4.4, proved by AT-10.4 to AT-10.9. The drilldown must reconcile to the headline figure by construction — it renders what the API returns, and the API computes both the same way. Loss-making SKUs need a non-colour indicator. Include the honesty statement from `plans/BUSINESS_RULES.md` §11.3 verbatim. No money arithmetic in TypeScript and no charting library." |

---

**★ CP-4 gate:** AT-7 green including the randomised sweep; AT-10.1 to AT-10.9 green; the full core journey works locally.

---

## Day 4 — Methodology, accessibility and stabilisation

### T16 — Methodology view, responsive and accessibility pass, stabilisation

| | |
|---|---|
| **Objective** | The trust page, a genuinely responsive five-view app, and a reproducible, evidenced, honest release. |
| **Prerequisite** | T14, T15 |
| **Files owned** | `frontend/src/views/Methodology.tsx`, `frontend/src/components/Disclaimer.tsx`, any `frontend/src/**` file for responsive and accessibility fixes, `backend/tests/` for any deferred variant expectations, `README.md`, `plans/PROGRESS.md` |
| **Done condition** | Methodology shows the five money terms, the active assumptions with effective dates, the §7 disclaimer verbatim, the returned-unit and fee-reversal treatment, the TCS/TDS cash-flow statement, and the not-an-optimisation statement; all five views are usable at 375 px with no horizontal scroll; keyboard-only navigation reaches every control with a visible focus ring; an invalid assumption is rejected with the previous value retained; no screen contains "optimal", "guaranteed" or a prediction claim; a fresh clone with a new virtual environment reproduces `pytest` green and `npm run build` clean using README steps only; a secret sweep is clean; three SKUs recomputed by hand agree with the app; screenshots show the running application; `PROGRESS.md` carries pasted output for every claim. |
| **Checks** | Unit: AT-1.6–1.8 if deferred from T04. Integration: AT-9.1–9.9, AT-10.10–10.15. E2E: AT-11.1–11.10, the full clean-install run. |
| **Fallback** | Hosting and every P1 item are already cut. If time runs short, ship Methodology as structured unstyled text, run the accessibility pass at keyboard-and-contrast level only, and record precisely what was not checked. **Never skip the clean-install test.** |
| **Time** | 4.0 h (the day's whole block: 1.5 h Methodology + responsive/a11y, 2.5 h stabilisation, plus README and demo) |
| **Agent prompt** | "Implement `Methodology.tsx` and run the stabilisation pass per `plans/PRD.md` §4.5 and `plans/MASTER_PLAN.md` §3 CP-5. Methodology content is specified verbatim in `plans/BUSINESS_RULES.md` §7 and §11 — do not paraphrase the disclaimer. Then: perform a fresh-clone install in a new directory, run `pytest`, `ruff check`, `npm run build`, and the secret sweep, and paste every command and its raw output into `plans/PROGRESS.md`. Write the README from the commands that actually worked. Do not claim any result you did not observe. Nothing is deployed; hosting is P1 and out of scope." |

---

## P1 tasks — not scheduled, listed only so nobody invents them

These exist only if **every** P0 acceptance row has passed and time remains. They are not in the 16. Adding one requires an `ACCEPTANCE_TESTS.md` row and a `DECISIONS.md` entry.

| Candidate | Acceptance row |
|---|---|
| Simple stock-cover warning, labelled "for human review" | AT-12.1 |
| One additional visualisation with an accessible text alternative | AT-12.2 |
| Optional public deployment, demo data only, CORS allowlisted | AT-12.3 |
| `DELETE /import/{batch_id}` | AT-12.4 |

---

## Dependency graph

```
T01 ──▶ T02 ──▶ T03 ──┬──▶ T04 ──▶ T05
                      ├──▶ T06 ──▶ T07
                      └──▶ T08

T04, T05, T08 ────────▶ T11 ──┐
                              ├──▶ T12 ──┐
T04, T06, T07, T08 ──▶ T09 ──▶ T10 ──────┘        │
                                                  │
T01, T10 ──▶ T13 ──┬──▶ T14 ───────────────────────┼──▶ T16
                   └──▶ T15 ◀── T12 ───────────────┘
```

Critical path: **T01 → T02 → T03 → T06 → T07 → T09 → T10 → T12 → T15 → T16**.

`T11` (allocator) can run in parallel with `T06`–`T10` because it depends only on `T04`, `T05` and `T08`, and it touches no shared file — **if** two agents are used, `allocator.py` and `validation.py`/`db.py` must be in separate worktrees (`AGENTS.md` rule 2).

---

## Cross-references

- Acceptance IDs and expected values: `ACCEPTANCE_TESTS.md`
- Formulas every task implements: `BUSINESS_RULES.md`
- Checkpoints and the drop-list: `MASTER_PLAN.md`
- File ownership boundaries: `ARCHITECTURE.md` §2
- Commands each task runs: `TECH_STACK.md` §5
- Evidence tracker: `PROGRESS.md`
