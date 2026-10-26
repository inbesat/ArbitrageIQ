# PRD.md — Product Requirements

| Field | Value |
|---|---|
| **Status** | Approved specification. No source code exists yet. |
| **Authority** | Fourth. Overrides `TECH_STACK.md`, `ARCHITECTURE.md`, `MASTER_PLAN.md` and `PHASES_DETAILED.md` on scope and UX. Subordinate to `DECISIONS.md`, `BUSINESS_RULES.md` and `ACCEPTANCE_TESTS.md`. |
| **Rule** | This document **links to** formulas in `BUSINESS_RULES.md`; it never copies them. Any formula written here would be a second source of truth. |
| **Change control** | Product scope, the P0/P1/P2 boundary, and the view list require human approval and a `DECISIONS.md` entry. |

---

## 1. Problem

A small Indian online reseller buys wholesale and sells on a marketplace. Their instinct is to subtract the purchase price from the selling price and call the difference profit. That number is wrong, usually by a large factor, because between the two prices sit:

- marketplace referral, closing, and shipping/weight-handling fees;
- GST on those marketplace services;
- GST embedded in the product price, which was never theirs;
- returns and refunds, which remove revenue but not the restocking cost;
- advertising.

The real figure — **contribution profit** — can be a fraction of the apparent margin, or negative. With a fixed budget and many candidate products, the reseller also has to decide *how to split the money*, and the highest-ROI product is not automatically the right answer: its supply may be capped, its minimum order quantity may force a lump, and the profit estimate rests on a sell-through assumption that nobody has measured.

**ArbitrageIQ makes that arithmetic visible, editable, and honest.**

---

## 2. Users and jobs

| Persona | Situation | Job to be done |
|---|---|---|
| **Priya, the first-time reseller** | ₹50,000, a laptop, 2–4 candidate products, no accounting background | "Tell me which of these actually makes money after everything, and stop me from believing a fake margin." |
| **Ravi, the small catalogue operator** | Already selling, 10+ SKUs, a spreadsheet full of orders | "Show me per-SKU contribution so I know what to restock and what to drop." |
| **Meera, the evaluator / mentor** | Assessing whether this tool is trustworthy | "Show me the assumptions behind every number and prove the arithmetic is testable." |

**Explicitly not a user:** anyone wanting live marketplace data, automated trading, tax filing, or a sales forecast. Those are out of scope (§6).

---

## 3. The core journey

```
Load demo data or upload a CSV
        │
        ▼
See what was accepted and what was rejected, with reasons
        │
        ▼
Review contribution profit per SKU, with a full breakdown and one drilldown
        │
        ▼
Adjust fees / GST / refund assumptions and watch the numbers move
        │
        ▼
Enter a budget, compare two buying strategies and a downside scenario
        │
        ▼
Read the methodology, understand what is assumed and what is not claimed
```

Every step must be reachable without reading documentation, and every rupee figure must be traceable to a stated assumption.

---

## 4. The five views

### 4.1 Overview
**Purpose:** convey one decision, not a dense dashboard.

- The headline card: total **contribution profit** for the loaded data, with the portfolio's net revenue and capital-at-cost beneath it.
- A plain-language verdict line: how many SKUs are profitable, how many are losing money.
- A **DEMO DATA** indicator, always visible when sample data is loaded.
- Entry points to Import, Profitability and Budget Lab.
- Empty state: what to do first, with a single primary action to load the synthetic sample.
- **Not** shown: any forecast, trend line, or prediction.

### 4.2 Import
**Purpose:** make ingestion trustworthy.

- File picker for `products` and `transactions` CSVs, plus a one-click "load synthetic sample".
- A **dry-run validation** action that reports what *would* happen without writing anything.
- Import summary: `imported`, `skipped (duplicate)`, `rejected`.
- A rejected-rows table: row number, field, offending value, human-readable reason.
- Caps stated in the UI: 5 MB and 20,000 rows per file.
- Empty state: explains the expected columns and offers the sample.
- Error state: an unreadable file produces a plain message, never a stack trace.

### 4.3 Profitability
**Purpose:** the core reconciliation.

- Per-SKU table: SKU, name, units shipped, net units, net revenue, product cost, fees, GST on fees, ads, other, **contribution**, profit per unit, margin %, ROI %.
- Loss-making SKUs are visually distinguishable **without relying on colour alone** — an icon or a text marker accompanies any colour.
- Sorting and a simple text filter.
- **Break-even price** and the price needed for a target margin, each flagged as a pricing floor, never a recommendation (see `ACCEPTANCE_TESTS.md` AT-4).
- **Drilldown** for one SKU: the per-line breakdown, the active assumptions, and a reconciliation showing that the line contributions sum to the headline figure.
- Ratios with a zero denominator render as `n/a` (see `BUSINESS_RULES.md` §8) — never as `0` and never as an error.
- Empty state: no transactions yet, with a link to Import.

### 4.4 Budget Lab
**Purpose:** the decision support.

- An editable budget, defaulting to ₹50,000.
- Editable `sell_through` and `salvage`, each labelled **ASSUMED**.
- An editable concentration cap for the capped strategy, defaulting to 40%.
- Two plan cards — **Plan A: ROI-first** and **Plan B: Diversified cap** — each showing capital used, budget remaining, expected contribution, and per-SKU quantities.
- A **conservative (downside)** row: price × 0.95, sell-through × 0.75, with fees recomputed.
- The required honesty statement, verbatim, that a uniform downside shock cannot demonstrate the benefit of diversification (`BUSINESS_RULES.md` §11.3).
- Immediate recomputation when a control moves.
- Empty state: no catalogue yet.
- **Never** claim a **plan** is "optimal", "best", "maximises", or "guaranteed", and never claim real-world sales. (A statement that a product's apparent appeal may rest on a weak assumption is not a plan claim and is permitted — see `BUSINESS_RULES.md` §11.4.)

### 4.5 Methodology
**Purpose:** the trust page.

- The five money terms — sales value, net revenue, marketplace payout, contribution profit, accounting profit — with what is and is not computed.
- The full list of active assumptions with their effective dates, every one labelled illustrative.
- The disclaimer text from `BUSINESS_RULES.md` §7, verbatim.
- The statement that a returned unit is written off and that fees on a returned order are not reversed.
- The statement that TCS and TDS are cash-flow credits and are not costs.
- The statement that the allocation heuristics are not optimisation.
- What is explicitly not modelled: overheads, income tax, and anything requiring a live marketplace.

---

## 5. Constraints that shape the product

| Constraint | Consequence |
|---|---|
| Money must be exact | `Decimal` end to end; the UI never does arithmetic on money (`DECISIONS.md` ADR-006, ADR-024) |
| "Sales value ≠ payout ≠ contribution" | Three distinct figures, never one blended "profit" number |
| Assumptions are uncertain | Every derived figure carries a visible assumptions affordance |
| Synthetic or owner-authorised data only | A persistent DEMO DATA badge; no third-party/real seller data anywhere |
| No live integration | The import path is the only data source; `INTEGRATIONS.md` states what is deferred |
| Four days, two people | Five views, sixteen tasks, no P2 scope creep |
| Must be demoable | Real loading, empty and error states on every view; phone-width responsive |

---

## 6. MVP boundaries

### In scope (P0)
1. Synthetic seed catalogue and transaction set.
2. Safe CSV import for `products` and `transactions` with per-row reject reasons, size and row caps, and idempotent reimport.
3. The `Decimal` contribution engine with a per-SKU breakdown and cell-level drilldown.
4. Configurable, dated, visible fee / GST / refund assumptions.
5. The Budget Lab with two heuristics, a hard budget, MOQ and stock constraints, an optional concentration cap, and a downside scenario.
6. The five responsive views with genuine loading, empty and error states.
7. Local reproducibility: tests, a production frontend build, sample fixtures, README, no secrets.

### P1 — only after every P0 acceptance row passes
- A simple stock-cover warning, labelled "for human review".
- One additional visualisation.
- Optional public deployment with demo data only.
- `DELETE /import/{batch_id}` (per `DECISIONS.md` ADR-023 and `ACCEPTANCE_TESTS.md` AT-12.4).

### P2 — explicitly not in this project
Live SP-API or any Amazon integration; wholesale price scraping; automated Google Trends ingestion; sales forecasting or machine learning; automated repricing or ordering; authentication; multi-tenant SaaS; Docker or PostgreSQL migration.

### Anti-goals — things this product must never do or say
- Present synthetic sell-through as expected real demand.
- Claim an allocation is optimal.
- Compute or imply accounting profit.
- Give tax or GST advice.
- Scrape, automate a seller account, or execute an order.
- Blend the five money terms into a single "profit" figure.

---

## 7. Edge cases the product must handle gracefully

| Case | Required behaviour |
|---|---|
| No data loaded | Informative empty state on every view; no blank panels, no crashes |
| A fully returned order | `net_revenue = 0`, ratios show `n/a`, contribution is negative and finite |
| A loss-making SKU | Clearly visible, never hidden by an average |
| Zero-price or zero-cost input | Handled; ratios show `n/a`; no division error |
| A CSV with mixed valid and invalid rows | Valid rows load; every invalid row is reported with a row number and a reason |
| A duplicate file uploaded twice | No duplicates; a clear "skipped" count |
| An oversized file | Rejected with the cap named, nothing written |
| An assumption set out of range | Rejected with a clear message; the previous value is retained |
| A budget too small to buy anything | Both plans buy nothing, with an explanation — not an error |
| A supplier cap smaller than the MOQ | The SKU cannot be bought; reported, not crashed |
| Backend unreachable from the UI | A clear error state with a retry, not a spinner forever |

---

## 8. Definition of done

The product is done when a reviewer can, following only the README:

1. Start the local backend and frontend.
2. Load the synthetic product and transaction data.
3. See per-SKU contribution with a breakdown and one working drilldown that reconciles to the headline figure.
4. Enter ₹50,000, compare **Plan A** and **Plan B**, and inspect the conservative downside scenario.
5. Change an assumption (`sell_through`, a fee, a GST rate) and watch the numbers change without losing clarity about what is assumed.
6. Reproduce the golden fixture: **₹1,624.08** contribution for the stated scenario.
7. Observe the budget, MOQ, stock-cap and concentration-cap invariants holding.
8. Run the backend test suite and the frontend production build cleanly in a fresh environment.
9. Use all five views at desktop and phone widths.
10. Find no secret, no third-party/real seller data, and no claim of optimality anywhere.

If hosting slips, a stable local demo with screenshots is sufficient. Generated, unexecuted code is never presented as working.

---

## 9. Out-of-scope interactions deliberately absent

- No chat interface. No assistant panel. This is a tool, not a conversation.
- No "AI predicts sales" or confidence-score banner.
- No login screen.
- No settings page beyond the assumptions exposed on Budget Lab and Methodology.
- No onboarding wizard or carousel.
- No dark-mode toggle, theme picker, or animation system.

Each of these was considered and rejected as surface area that does not serve the core journey.

---

## Cross-references

- Every formula and field semantic referenced above: `BUSINESS_RULES.md`
- The acceptance matrix that proves this document: `ACCEPTANCE_TESTS.md`
- Decisions behind the view list and boundaries: `DECISIONS.md` ADR-001 to ADR-003
- System shape and API boundaries: `ARCHITECTURE.md`
- Build order: `PHASES_DETAILED.md`
- Upload safety and privacy: `SECURITY.md`
