# ARCHITECTURE.md — System Structure, Data Flow and API Boundaries

| Field | Value |
|---|---|
| **Status** | Approved specification. No source code exists yet. Nothing in the repository tree below has been created. |
| **Authority** | Fifth. Overrides `MASTER_PLAN.md` and `PHASES_DETAILED.md` on structure. Subordinate to `DECISIONS.md`, `BUSINESS_RULES.md`, `ACCEPTANCE_TESTS.md`, `PRD.md`. |
| **Rule** | This document describes the intended structure. Once code exists, it must be updated to describe the real code. It must never describe capabilities that were not built. |

---

## 1. Shape

One modular monolith. One FastAPI process. One SQLite database. One React SPA. No services, no queue, no orchestration layer.

**The single most important structural rule:** all money arithmetic happens in the backend. The frontend receives computed values, including decimal strings, and renders them. A formula in TypeScript would create a second source of truth and is prohibited (`AGENTS.md` rule 7).

---

## 2. Repository tree

```
arbitrageiq/
├── AGENTS.md                      # agent instructions (exists)
├── README.md                      # stub in T01; finalised in T16 (not during the docs stage)
├── .gitignore                     # created in T01
├── plans/                         # this specification set
│   ├── CONTEXT.md  PRD.md  TECH_STACK.md  ARCHITECTURE.md  MASTER_PLAN.md
│   ├── SECURITY.md  DECISIONS.md  INTEGRATIONS.md  PROGRESS.md
│   └── PHASES_DETAILED.md  BUSINESS_RULES.md  ACCEPTANCE_TESTS.md  GLOSSARY.md
│
├── backend/
│   ├── pyproject.toml             # project metadata + tool config (T01)
│   ├── requirements.txt           # pinned deps (T01)
│   ├── ruff.toml                  # lint config, including the float-in-money guard (T01)
│   ├── arbitrageiq/
│   │   ├── __init__.py
│   │   ├── config.py              # assumption defaults, ranges, validation (T03)
│   │   ├── money.py               # Decimal helpers, half-up rounding, ratio-to-"n/a" (T02)
│   │   ├── profit.py              # contribution, breakdown, unit economics, fee model (T04, T05)
│   │   ├── validation.py          # CSV read-as-text, header normalisation, row validation (T06, T07)
│   │   ├── allocator.py           # two heuristics, constraints, scenarios (T11, T12)
│   │   ├── models.py              # SQLAlchemy ORM tables, NUMERIC money (T08)
│   │   ├── db.py                  # engine, session, init, seed (T08)
│   │   ├── reconcile.py           # per-SKU aggregation over transactions (T09)
│   │   ├── schemas.py             # Pydantic request/response models, decimal-string money (T10)
│   │   ├── loaders.py             # bundled sample fixture loading (T09)
│   │   └── api.py                 # FastAPI app, routes, error handlers (T10)
│   └── tests/
│       ├── __init__.py            # (T01)
│       ├── test_money.py  test_profit.py  test_config.py  test_economics.py
│       ├── test_validation.py  test_validation_safety.py
│       ├── test_reconcile.py  test_db.py  test_allocator.py
│       ├── test_api.py  test_budget_api.py
│       └── fixtures/              # CSV fixtures for the AT-5 matrix
│           └── golden_v1.json     # fixture v1 parameters for AT-1 (T04)
│
├── frontend/
│   ├── package.json  package-lock.json
│   ├── vite.config.ts  tsconfig.json  tailwind.config.js  index.html
│   └── src/
│       ├── main.tsx  App.tsx           # router + layout shell (T13)
│       ├── api/
│       │   ├── client.ts               # typed fetch wrapper, error normalisation (T13)
│       │   └── types.ts                # mirrors schemas.py; money typed as string
│       ├── index.css                   # Tailwind entry + design tokens (T13)
│       ├── components/                 # AssumptionPanel, DemoBadge, EmptyState,
│       │                               # ErrorState, Loading, MoneyCell, PlanCard,
│       │                               # ImportSummary, RejectionTable (T14),
│       │                               # SkuTable, SkuDrilldown (T15), Disclaimer (T16)
│       └── views/
│           ├── Overview.tsx            # T14
│           ├── Import.tsx              # T14
│           ├── Profitability.tsx       # T15
│           ├── BudgetLab.tsx           # T15
│           └── Methodology.tsx         # T16
│
├── data/
│   ├── sample/                    # synthetic fixtures, committed (T08)
│   │   ├── products_sample.csv  transactions_sample.csv
│   └── private/                   # GITIGNORED. Never committed. (T01)
│
└── scripts/
    └── make_sample_data.py        # deterministic synthetic generator (T08)
```

`data/private/`, `.env`, `*.db` and `*.sqlite*` are gitignored (`SECURITY.md` §4).

---

## 3. Module dependency rules

Allowed import direction, strictly one way:

```
money ──▶ config ──▶ profit ──▶ allocator
                        │
                        ▼
                     reconcile ──▶ db ──▶ models
                        │
validation ─────────────┴──────────▶ loaders
                        │
                        ▼
                    schemas ──▶ api        (api is the top; nothing imports api)
```

| Module | May import | Must never import |
|---|---|---|
| `money` | stdlib only (`decimal`, `typing`) | anything project-local |
| `config` | `money` | `profit`, `db`, `api` |
| `profit` | `money`, `config` | `db`, `api`, `validation` |
| `allocator` | `money`, `config`, `profit` | `db`, `api` |
| `validation` | stdlib, `pandas` | `profit`, `db`, `api` — validation must not depend on financial logic |
| `models` | `sqlalchemy` | `api` |
| `db` | `models` | `api` |
| `reconcile` | `profit`, `models`, `db` | `api` |
| `loaders` | `validation`, `models`, `db` | `api` |
| `schemas` | `pydantic`, `money` | `db`, `api` |
| `api` | everything | — (nothing imports it) |

**Why this matters.** `validation.py` being unable to import `profit.py` is what keeps "did this row load?" separable from "what does this row earn?". `money.py` importing nothing is what makes the rounding rule testable in isolation.

A task that needs to breach this table is a stop condition, not an implementation detail.

---

## 4. Request and response flow

### 4.1 Import

```
POST /import (multipart file + kind=products|transactions)
   │
   ├─ size guard (<= 5 MB)                        ──▶ 413
   ├─ row guard (<= 20,000 data rows)             ──▶ 413
   ├─ read as text: pandas.read_csv(dtype=str)     ──▶ CsvReadError ──▶ 422
   ├─ normalise headers (case, whitespace, BOM, alias map)   ──▶ 422 missing column
   ├─ per-row validate against the ColumnSpec list ──▶ rejects collected, not raised
   ├─ deduplicate on transaction_id and content hash
   │
   └─ one transaction: INSERT import_batch + valid rows
                                    │
                                    ▼
                      {imported, skipped, rejected:[{row, field, value, reason}]}
```

Nothing is persisted unless validation produced at least one acceptable row and the write succeeded. A rejected row never blocks a valid one.

### 4.2 Profitability

```
GET /profit/reconcile
   │
   ├─ load transactions joined to products
   ├─ load the active fee_assumptions record
   ├─ for each transaction line:
   │      profit.compute_line(...)  ──  BUSINESS_RULES.md §4, Decimal, round once
   ├─ group and sum the ROUNDED line values per SKU
   ├─ sum SKU totals for the portfolio
   └─ serialise: money as decimal strings, ratios as decimal strings or "n/a"
```

`GET /profit/sku/{sku}` runs the same line computation and returns both the totals and the per-line breakdown, so the drilldown reconciles by construction.

### 4.3 Budget Lab

```
POST /budget/simulate {budget, sell_through, salvage, max_share_per_sku, candidates?}
   │
   ├─ 422 if any control is out of range
   ├─ build Candidate objects from the catalogue
   ├─ for each scenario (Base, Conservative):
   │      expected_profit(sku, qty, scenario)     ──  BUSINESS_RULES.md §11.2
   ├─ score(qty) = (0.5·base + 0.5·conservative) / (qty · landed_cost)
   ├─ Plan A: greedy descending score, no concentration cap
   ├─ Plan B: greedy descending score, per-SKU cap enforced
   ├─ assert invariants B1–B10 before returning; a breach is a 500 and a bug, never a silent result
   └─ serialise both plans + the conservative scenario
```

The invariant assertion sits at the boundary on purpose: a plan that overspends or breaches an MOQ must fail loudly rather than reach the user.

### 4.4 Frontend

```
view mounts ──▶ api/client.ts ──▶ fetch ──▶ FastAPI
                    │
                    ├─ ok    ──▶ render; money rendered as received (string), never parsed to a number
                    ├─ 4xx   ──▶ typed error state with the server's message
                    ├─ 5xx   ──▶ generic error state with retry
                    └─ network failure ──▶ offline error state with retry
```

Every view implements four states: **loading, empty, error, content**. A view missing any of them fails AT-10.

---

## 5. Data model (ERD)

```
┌──────────────────────────┐
│ products                 │
├──────────────────────────┤
│ sku                PK    │
│ name                     │
│ category                 │
│ supplier_unit_cost NUMERIC│
│ inbound_unit_cost  NUMERIC│
│ packaging_unit_cost NUMERIC│
│ target_price       NUMERIC│
│ current_stock      INT   │
│ min_order_qty      INT   │
│ max_supply         INT   │
│ cost_updated_on    DATE NULL │
└───────────┬──────────────┘
            │ 1
            │
            │ N
┌───────────┴──────────────┐        ┌────────────────────────┐
│ transactions             │        │ import_batches         │
├──────────────────────────┤        ├────────────────────────┤
│ transaction_id     PK    │        │ id                PK   │
│ order_date         DATE  │        │ filename               │
│ sku                FK ───┼───────▶│ content_hash   UNIQUE  │
│ units_sold    INT (GROSS)│  N   1 │ row_count              │
│ returned_units     INT   │────────┤ rejected_count         │
│ selling_price      NUMERIC│        │ kind                   │
│ discount_per_unit  NUMERIC│        │ created_at             │
│ refund_per_returned_unit NUMERIC NULL │
│ settlement_fees_total    NUMERIC NULL │
│ ads_cost           NUMERIC│        └────────────────────────┘
│ other_charges      NUMERIC│
│ import_batch_id    FK ────┘
└──────────────────────────┘

┌───────────────────────────────────┐      ┌────────────────────────────┐
│ fee_assumptions                   │      │ budget_plan_runs           │
├───────────────────────────────────┤      ├────────────────────────────┤
│ id                           PK   │      │ id                    PK   │
│ effective_from               DATE │      │ created_at                 │
│ referral_rate                NUM  │      │ budget                NUM  │
│ zero_referral_below          NUM  │      │ sell_through          NUM  │
│ closing_fee                  NUM  │      │ salvage               NUM  │
│ shipping_fee                 NUM  │      │ max_share_per_sku     NUM  │
│ fulfilment_fee               NUM  │      │ strategy                   │
│ product_gst_rate             NUM  │      │ scenario                   │
│ gst_on_fees_rate             NUM  │      └──────────┬─────────────────┘
│ fee_gst_recoverable          BOOL │                 │ 1
│ tcs_rate                     NUM  │                 │ N
│ tds_rate                     NUM  │      ┌──────────┴─────────────────┐
│ default_sell_through         NUM  │      │ budget_plan_lines          │
│ default_salvage              NUM  │      ├────────────────────────────┤
│ default_budget               NUM  │      │ run_id             FK      │
│ default_max_share_per_sku    NUM  │      │ sku                FK      │
│ note                         TEXT │      │ qty                 INT    │
└───────────────────────────────────┘      │ capital             NUM    │
                                           │ expected_contribution NUM  │
                                           └────────────────────────────┘
```

**Rules**

- **Money columns are `NUMERIC`.** Never `REAL`, never `FLOAT`. Enforced by a test that inspects the reflected column types (AT-6.5).
- `transactions.transaction_id` is the deduplication key and is unique.
- `import_batches.content_hash` is unique, which is what makes reimport idempotent.
- `fee_assumptions` is append-mostly: a change creates a new dated row. Exactly one row is "active" for a given date.
- `budget_plan_runs` / `budget_plan_lines` exist so a plan can be reproduced and displayed later. They are written by `/budget/simulate` only when the caller asks to save; a dry simulation need not persist.

---

## 6. API boundaries

Base path: **`/api/v1`** — chosen and recorded at T10 (`backend/arbitrageiq/api.py`, `API_PREFIX`). Every path in the table below, and in `ACCEPTANCE_TESTS.md` AT-8, is **relative to the chosen prefix**; the table lists bare paths. `/docs` and `/openapi.json` stay at the root default.

| Method | Path | Purpose | Success | Failure |
|---|---|---|---|---|
| GET | `/health` | liveness + DB reachability | 200 | 503 |
| GET | `/assumptions` | read the active assumption set | 200 | — |
| PUT | `/assumptions` | update assumptions (validated, dated) | 200 | 422 |
| GET | `/products` | catalogue list | 200 (may be empty) | — |
| POST | `/import/validate` | dry-run validation, writes nothing | 200 | 413, 422 |
| POST | `/import` | validate and persist | 200 | 413, 422 |
| GET | `/profit/sku/{sku}` | one SKU, totals + line breakdown | 200 | 404 |
| GET | `/profit/reconcile` | all SKUs + portfolio totals | 200 (may be empty state) | — |
| POST | `/budget/simulate` | both plans + downside scenario | 200 | 422, 500 on invariant breach |
| GET | `/docs` | OpenAPI UI (FastAPI default) | 200 | — |
| DELETE | `/import/{batch_id}` | **P1 only** — remove a batch | 200 | 404 |

**Uniform error body.** Every non-2xx response returns the same shape, and never a bare string, a traceback, a file path, or SQL text:

```json
{ "error": "validation_failed", "detail": "Human-readable explanation.", "field": "returned_units" }
```

`error` is a stable machine string; `detail` is safe to display; `field` is optional and present for field-level failures.

**Money on the wire.** All monetary fields are JSON strings containing decimal literals (`"1624.08"`). Ratio fields are decimal strings or the literal `"n/a"` (ADR-024).

---

## 7. Error boundaries

| Layer | Responsibility | Rule |
|---|---|---|
| `money` | Never raises for a ratio; returns `"n/a"` | A zero denominator is data, not an exception |
| `config` | Raises on an out-of-range assumption | Caught at the API boundary → 422 |
| `validation` | Collects per-row rejects; raises `CsvReadError` only for a file that cannot be read at all | One bad row never fails the file |
| `db` | Propagates `SQLAlchemyError` | Mapped to 500 without leaking SQL text |
| `allocator` | Raises on invariant breach after solving | A breach is a bug and must surface, never be smoothed over |
| `api` | Single exception handler normalises every response | The only place an HTTP status is decided |
| `client.ts` | Normalises network, 4xx and 5xx into typed states | A view never inspects a raw status code |

**Global rule.** No user-supplied content is ever interpolated into SQL (parameterised queries only), evaluated, or written into a log line.

---

## 8. What this architecture deliberately does not have

- No authentication, session, or user model — single local user (P2: `DECISIONS.md` ADR-003).
- No caching layer — the dataset is small and SQLite is local.
- No background workers or scheduler.
- No external network calls of any kind (`INTEGRATIONS.md`).
- No state management library in the frontend — view-local state plus a typed API client is sufficient for five views.
- No design-system package — a small set of local components (ADR-002, ADR-027).

Each was considered and rejected because it adds surface without changing what the app proves.

---

## Cross-references

- Field semantics behind the ERD: `BUSINESS_RULES.md` §3, §13
- Formulas behind the flow diagrams: `BUSINESS_RULES.md` §4, §11
- Acceptance checks that prove each boundary: `ACCEPTANCE_TESTS.md` AT-5, AT-6, AT-7, AT-8
- Stack and version strategy: `TECH_STACK.md`
- Upload limits and privacy: `SECURITY.md`
- Task-to-file ownership: `PHASES_DETAILED.md`
