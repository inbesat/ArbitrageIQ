# GLOSSARY.md — Terms Used Precisely in This Project

| Field | Value |
|---|---|
| **Status** | Approved specification. |
| **Purpose** | This project's own vocabulary. Several of these words mean something narrower here than in general use, and mixing them up is the single highest-severity risk in the build. |
| **Rule** | If a term is used in code, a document, or the UI with a meaning different from this list, either fix the usage or add the term here with a `DECISIONS.md` entry. |

---

## Money terms — read these first

| Term | Meaning here |
|---|---|
| **Sales value** | What customers paid, GST included. Not earned by the seller; the GST portion is collected on the government's behalf. Shown for context only. |
| **Net revenue** | Sales value with GST removed, minus refunds. The money genuinely attributable to the seller. GST-free. An input to contribution. |
| **Marketplace payout** | What the marketplace actually transfers after deducting fees, GST on fees, and withholding. A **mixed** figure (partly ex-GST, partly a liability). Not profit. Shown only in a reconciliation. |
| **Contribution profit** | Net revenue − product cost − marketplace fees − GST on fees (unless recoverable) − ads − other charges. GST-free. **The product's headline number.** |
| **Accounting profit** | Contribution minus overheads and income tax. **Never computed, never estimated, never implied by this project.** |
| **Payout** | Shorthand for marketplace payout. Never a synonym for profit. |

> The single most damaging confusion in this project is treating a payout as profit. `BUSINESS_RULES.md` §10.3 demonstrates the gap with the golden fixture: a payout of ₹8,444.08 corresponds to a contribution of ₹1,624.08.

---

## Units and quantities

| Term | Meaning here |
|---|---|
| **`units_sold`** | **GROSS units shipped, including units later returned.** Not net. See `BUSINESS_RULES.md` §3. |
| **`returned_units`** | Units returned in this transaction line. `0 <= returned_units <= units_sold`. |
| **Net units (`n`)** | `units_sold − returned_units`. The denominator for profit per unit. |
| **`qty`** | In the Budget Lab, units of one SKU that a plan proposes to **buy**. Unrelated to units sold. |
| **MOQ** | Minimum order quantity. A purchase of a SKU must be `0` or `>= MOQ`; there is no partial MOQ. |
| **`max_supply`** | The most units a supplier can provide in the period. A hard cap on `qty`. |
| **Land** | Short for landed cost. |

---

## Costs and prices

| Term | Meaning here |
|---|---|
| **Landed cost (`L`)** | `supplier_unit_cost + inbound_unit_cost + packaging_unit_cost`. The full cost of putting one unit in the warehouse. |
| **`p`** | Price actually paid per unit, GST-inclusive: `selling_price − discount_per_unit`. |
| **`e`** | Ex-GST price per unit: `p / (1 + product_gst_rate)`. The seller's real revenue per unit. |
| **Referral fee** | A marketplace commission, modelled as a percentage of `p`, charged only when `p >= zero_referral_below`. |
| **Closing fee** | A fixed marketplace charge per shipped unit. |
| **Shipping / weight-handling fee** | A marketplace charge per shipped unit, modelled here as a flat amount. |
| **Fulfilment fee** | A marketplace charge per shipped unit. Present in the model; zero in the demo. |
| **`fees_ex_gst`** | The sum of the modelled marketplace fees, GST excluded. |
| **Settlement fees** | Actual fees reported by the marketplace for a line, GST-inclusive. **Replaces** the modelled fees; never added to them. |

---

## Tax and withholding

| Term | Meaning here |
|---|---|
| **Product GST** | GST inside the selling price. Removed from revenue via `p / (1 + product_gst_rate)`. Its rate depends on the product's classification and must be set per product type. |
| **GST on fees** | GST charged on marketplace services. A cost by default. |
| **ITC** | Input Tax Credit. Whether a seller may claim GST on fees back depends on their registration and circumstances. Modelled only as a configurable switch, `fee_gst_recoverable`. |
| **TCS** | Tax Collected at Source, under GST Section 52. Collected by the marketplace and, in general, a credit against the seller's own GST liability. **A cash-flow item, never a cost.** Never subtracted from contribution. |
| **TDS** | Tax Deducted at Source, under income-tax Section 194-O. Deducted by the marketplace and, in general, a credit against the seller's income tax. **A cash-flow item, never a cost.** Never subtracted from contribution. |
| **Withholding** | Umbrella for TCS and TDS. |

> Every rate above is an illustrative assumption with an effective date. None of it is tax advice. `BUSINESS_RULES.md` §7 carries the required disclaimer.

---

## The golden fixture

| Term | Meaning here |
|---|---|
| **Fixture v1** | The synthetic scenario in `BUSINESS_RULES.md` §10.1: 10 units shipped, 1 returned, ₹1,180 inclusive price, 18% product GST, ₹500 landed cost, 8% referral, ₹25 + ₹65 fees, 18% GST on fees, ₹200 ads. |
| **₹1,624.08** | The contribution profit that fixture must produce, exactly, as a `Decimal`. Derived two independent ways and shown to agree. `ACCEPTANCE_TESTS.md` AT-1.1. |
| **Golden test** | A test asserting a hand-derived expected value that the implementation must match, where the expectation was **not** produced by the implementation. |
| **Demo data** | Synthetic data loaded from `data/sample/`. Always accompanied by the DEMO DATA badge. |

---

## Rounding and representation

| Term | Meaning here |
|---|---|
| **Half-up** | The rounding mode: `0.005 → 0.01`, `-0.005 → -0.01`. Applied **once per transaction line**. |
| **Per-line then sum** | The authoritative order: round each line to 2 dp, then add the rounded values to get SKU and portfolio totals. Never round an aggregate. |
| **`Decimal`** | Python's exact decimal type. The only type permitted for money. |
| **`NUMERIC`** | The SQLite column type for money. Never `REAL`, never `FLOAT`. |
| **Decimal string** | The JSON wire form of money, for example `"1624.08"`. Never a JSON number, because clients parse those as floats. |
| **`"n/a"`** | The literal string returned for a ratio whose denominator is zero. Never `0`, `NaN`, or `Infinity`. |

---

## The Budget Lab

| Term | Meaning here |
|---|---|
| **Base scenario** | Price and sell-through as estimated. No shock applied. |
| **Conservative scenario** | Downside: price × 0.95, sell-through × 0.75, with fees recomputed at the reduced price. Uniform across all SKUs. |
| **Sell-through** | The fraction of purchased units expected to sell. An **assumption**, never a measurement. |
| **Salvage** | The fraction of landed cost recovered on an unsold unit. An **assumption**. |
| **Expected profit** | The forward-looking estimate in `BUSINESS_RULES.md` §11.2. Distinct from realised contribution, which comes from actual transaction rows. |
| **Realised vs expected** | Realised = from loaded transactions. Expected = from assumptions. The two must never share a label or a column. |
| **Plan A — ROI-first** | A greedy heuristic ranking by risk-adjusted expected profit per rupee of capital, with no concentration cap. |
| **Plan B — Diversified cap** | The same score with a per-SKU cap on spend, default 40% of budget. |
| **Concentration cap** | `max_share_per_sku`. Applied to Plan B only. |
| **Heuristic** | A transparent rule of thumb. **Not** an optimisation, and never to be described as optimal. |
| **Invariant** | A condition that must hold for every returned plan: within budget, integer quantities, `0` or `>= MOQ`, `<= max_supply`, cap respected, no `NaN`, deterministic. |
| **Grouped knapsack** | The formal optimisation problem this tool deliberately does **not** solve. The handbook solves it exactly; this project does not, by decision. |

---

## Architecture and process

| Term | Meaning here |
|---|---|
| **Modular monolith** | One process, one database, internal modules with a strict import direction. No services. |
| **Trust boundary** | The line between what the operator controls and what an upload or request supplies. The backend is on the trusted side; the frontend is not a boundary. |
| **Acceptance ID** | An `AT-n.m` identifier in `ACCEPTANCE_TESTS.md`. A task is not done until its named IDs are observed to pass. |
| **ADR** | Architecture Decision Record. A dated entry in `DECISIONS.md`, append-only. |
| **Source-of-truth order** | The precedence list in `CONTEXT.md` §3, used to resolve a conflict between documents. |
| **Fallback / cut-line** | The pre-agreed smaller deliverable a task takes when it exceeds its timebox. Every task has one. |
| **Bounded task** | One vertical slice that changes a testable user outcome, with a named file ownership. There are exactly 16. |
| **P0 / P1 / P2** | Build now / only if every P0 acceptance row passes / never in this project. |
| **Demo badge** | The always-visible DEMO DATA indicator shown when synthetic data is loaded. |
| **Evidence** | Pasted command output in `PROGRESS.md`. The only thing that justifies the word "done". |

---

## Cross-references

- Definitions in full context: `BUSINESS_RULES.md`
- The fixture and its derivations: `BUSINESS_RULES.md` §10
- Terms proven by tests: `ACCEPTANCE_TESTS.md`
- Vocabulary choices that required a decision: `DECISIONS.md`
