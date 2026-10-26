# DECISIONS.md — Architecture Decision Records

| Field | Value |
|---|---|
| **Purpose** | The authoritative record of decisions that shape this project, and the alternatives rejected. |
| **Authority** | Highest, for the item it records. An approved dated entry here overrides any other document. |
| **Rule** | **Append only.** Never delete or rewrite history. A changed decision gets a new entry that supersedes the old one, and the old entry is marked `Superseded by ADR-nnn`. |
| **Status** | Approved specification. No source code exists. |

Dates are the date the decision was taken. `2026-10-26` is the planning and specification date. ADRs marked **DRAFT** are proposed with a recommended default and still need an explicit human yes.

---

## §0 Open approvals

These are the only decisions that still need a human response. Everything below this section is settled.

| ID | Question | Recommended default | Blocking? |
|---|---|---|---|
| **AP-1** | Is the portfolio total **₹26,761.53** (handbook Appendix A) a required golden test? | **No.** Requiring it forces a seed-for-seed reimplementation of the handbook's sample generator, which is not in the brief's scope. Use fixture v1 (₹1,624.08) as the arithmetic anchor, and a self-consistent internal invariant (per-SKU sums equal the portfolio total) instead. | No. The build can proceed either way. |
| **AP-2** | Tailwind CSS vs plain CSS modules for the frontend | **Tailwind.** One system, fast, no bespoke design language to maintain. | No. |
| **AP-3** | Is `GLOSSARY.md` wanted as a 14th file? | **Yes.** Term confusion is risk #1 in this project. | No. |
| **AP-4** | Does the frontend ship in the same repo (monorepo) or separately? | **Same repo**, `frontend/` and `backend/` side by side, as the brief's tree shows. | No. |

If a human does not respond, the recommended defaults stand and are recorded as accepted. Nothing is blocked.

---

## §1 Product and scope decisions

### ADR-001 — React + Vite + TypeScript, not Streamlit
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The frontend is a React + Vite + TypeScript single-page app with five views: Overview, Import, Profitability, Budget Lab, Methodology.

**Context.** The handbook builds its interface with Streamlit and Plotly. The planning brief explicitly mandates React and states the handbook's original Streamlit frontend need not be reused.

**Alternatives rejected.**
- *Streamlit* — fastest to write, but no real control over responsive layout, no reusable component model, and it would make the bespoke two-plan comparison UI and phone-width requirement awkward.
- *Server-rendered Jinja templates* — would keep one language, but gives up the shared typed API contract and the component structure the comparison views need.

**Consequences.** Two toolchains, two install steps, and a typed API client that must stay in sync with the backend. Compensated by the frontend being prohibited from doing any money arithmetic (`AGENTS.md` rule 7).

---

### ADR-002 — Five views, and what is not one of them
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** Exactly five user-facing views: Overview, Import, Profitability, Budget Lab, Methodology.

**Context.** The handbook's dashboards grew to seven pages; the brief fixes five.

**Alternatives rejected.**
- *Port the handbook's seven pages* — the two extra pages (trends, alerts) are SHOULD-priority there and unassigned in the brief.
- *Add an alerting centre* — belongs in P1 at most.

**Consequences.** Google Trends scoring and the alerts page leave P0 (Trends is P2; alerts are unassigned). A minimal stock-cover warning may return as P1 (ADR-003).

---

### ADR-003 — P0 / P1 / P2 boundary is frozen
**Date:** 2026-10-26 · **Status:** Accepted

**P0:** synthetic seed data; safe CSV import with per-row reject reasons and idempotent reimport; the Decimal contribution engine with visible configurable assumptions; the Budget Lab with two heuristics and a downside scenario; the five responsive views with real loading/empty/error states; local reproducibility with tests, a production frontend build, and no secrets.

**P1, only after every P0 acceptance row passes:** simple stock-cover warning, labelled "for human review"; one extra visualisation; optional public deployment with demo data only; `DELETE /import/{batch_id}` (per ADR-023 and AT-12.4).

**P2, never in this project:** live SP-API or any Amazon integration; wholesale price scraping; automated Google Trends ingestion; sales forecasting or ML; automated repricing or ordering; authentication; multi-tenancy or SaaS; Docker or PostgreSQL migration.

**Consequences.** A task that appears to need a P2 capability is a stop condition (`AGENTS.md` §Stop conditions), not an implementation opportunity.

---

## §2 Architecture and data decisions

### ADR-004 — One modular monolith
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** A single FastAPI process with internal modules: `config`, `money`, `profit`, `validation`, `reconcile`, `allocator`, `models`, `db`, `schemas`, `loaders`, `api`. No microservices, no message queue, no orchestration layer.

**Alternatives rejected.** *Separate services for import vs compute* — no scaling need, large operational cost. *A notebook or script* — no testable boundary, no stable contract for the frontend.

**Consequences.** Module boundaries are enforced by convention and review, not by the network. `ARCHITECTURE.md` states the allowed import direction and a task must not breach it.

---

### ADR-005 — SQLite via SQLAlchemy; PostgreSQL and Docker deferred
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** SQLite as the only datastore, accessed through SQLAlchemy ORM models. Money columns are `NUMERIC`. No Alembic migrations in P0.

**Alternatives rejected.** *PostgreSQL* and *Docker Compose* — both add setup time that a 4-day local-first build cannot absorb, and neither changes what the app proves.

**Consequences.** No concurrent-writer story and no migration tooling. Acceptable for a single-user local tool. Moving to PostgreSQL is a P2 item and would require revisiting the `NUMERIC` type mapping.

---

### ADR-006 — `Decimal` for all money; binary floats are banned
**Date:** 2026-10-26 · **Status:** Accepted · **Deviation from the handbook**

**Decision.** Every monetary value is `Decimal` in Python, `NUMERIC` in SQLite, and a decimal **string** on the JSON wire. Binary floats are never used for money anywhere.

**Context.** The handbook's own allocator dataclass declares `unit_cost: float` and its knapsack solver is numpy-vectorised over floats. The brief mandates pure `Decimal` money calculations. These genuinely conflict.

**Alternatives rejected.** *Follow the handbook's floats* — violates the brief and produces cent-level drift that breaks the golden fixture. *`float` internally, `Decimal` at the boundary* — the drift happens before the boundary, so the boundary conversion launders rather than fixes it. *Integer paise everywhere* — correct, but spreads a unit-convention into every layer and makes the JSON contract awkward; retained as the internal technique for budget arithmetic only, where it guarantees the never-overspend invariant.

**Consequences.** The allocator must be implemented in `Decimal` (or in integer paise for the spend comparison). Any numpy vectorisation must operate on integers, not floats. A lint rule guards the money modules.

---

### ADR-007 — Contribution profit is the headline number; accounting profit is never computed
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The product computes and displays **contribution profit** only. Sales value, net revenue, and marketplace payout are shown for context and reconciliation. Accounting profit is never computed, never estimated, and never implied.

**Alternatives rejected.** *Show a "true profit" figure including overheads* — requires inputs the tool does not have and would overstate confidence.

**Consequences.** Every screen showing a contribution figure must state that overheads and income tax are excluded.

---

### ADR-008 — `transactions.units_sold` is GROSS units shipped
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** `units_sold` counts every unit shipped, **including units later returned**. Revenue is earned on net units; fees and product cost are modelled on gross units.

**Context.** The golden fixture is 10 shipped with 1 returned. Revenue on 9, fees and cost on 10. If `units_sold` were read as net, the fixture breaks and every figure in the app becomes defensibly plausible and wrong.

**Alternatives rejected.** *Define `units_sold` as net* — would make the fixture ₹2,624.08-class arithmetic unreachable and would silently drop the fee/cost treatment of a returned unit.

**Consequences.** This is the highest-severity risk in the project. It is stated in `BUSINESS_RULES.md` §3, asserted by AT-1.1 and AT-1.3, and surfaced in `GLOSSARY.md`.

---

### ADR-009 — Settlement fees replace the fee model; they are never added to it
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** When a transaction carries `settlement_fees_total`, the engine uses that figure (defined as GST-inclusive, and split into ex-GST and GST parts) and does **not** apply the modelled referral/closing/shipping fees to that row.

**Alternatives rejected.** *Add settlement fees on top of modelled fees* — double-counts every fee and would inflate costs unpredictably. *Ignore settlement data entirely* — discards the more accurate source.

**Consequences.** Requires AT-1.4 and AT-1.5, which prove both the equivalence case and the bypass case.

---

### ADR-010 — Rounding happens once per transaction line, then lines are summed
**Date:** 2026-10-26 · **Status:** Accepted · **Adopted from the handbook**

**Decision.** Money is rounded half-up to 2 decimal places at the end of each transaction line. Per-SKU and portfolio totals are the sums of already-rounded line values.

**Context.** The brief does not specify a rounding rule. The handbook defines one, and it is the only rule that makes the golden fixture reproducible.

**Alternatives rejected.** *Round only at display time* — leaves unrounded drift in stored aggregates. *Round at the end of the portfolio* — a different number than the fixture's, and hides per-line behaviour.

**Consequences.** Line-level rounding is authoritative. AT-2.4 asserts the difference explicitly.

---

### ADR-011 — A zero-denominator ratio renders as `"n/a"`, never `0`
**Date:** 2026-10-26 · **Status:** Accepted · **Adopted from the handbook**

**Decision.** Profit per unit with zero net units, margin with zero net revenue, and ROI with zero inventory cost all render as the string `"n/a"`.

**Alternatives rejected.** *Return `0`* — indistinguishable from a genuine break-even, and actively misleading. *Raise an error* — turns a legitimate data state (a fully returned order) into a crash.

**Consequences.** The API type for these fields permits a decimal string or `"n/a"`. The frontend must render both. Asserted by AT-3.1–AT-3.3.

---

## §3 Financial-model decisions

### ADR-012 — Configurable, dated assumptions; no hardcoded rates
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** Referral rate, zero-referral floor, closing fee, shipping fee, product GST rate, GST on fees rate, the ITC switch, TCS and TDS rates, and the Budget Lab's sell-through and salvage defaults are all stored as dated, editable `fee_assumptions` records with a mandatory note field.

**Alternatives rejected.** *Constants in code* — unverifiable and untestable against a user's real settlement. *User-typed values per request with no record* — no audit trail, no reproducibility.

**Consequences.** Every assumption row carries an `effective_from` date and must be labelled illustrative in the UI. Range validation is specified in `BUSINESS_RULES.md` R2.

---

### ADR-013 — TCS and TDS are cash-flow credits and never costs
**Date:** 2026-10-26 · **Status:** Accepted · **Adopted from the handbook**

**Decision.** TCS (Section 52) and TDS (Section 194-O) are displayed for reconciliation context and are **never** subtracted from contribution profit.

**Alternatives rejected.** *Treat them as costs* — they are credits against other liabilities, so treating them as costs would understate contribution and mislead.

**Consequences.** A test asserts that changing a TCS or TDS rate does not change contribution.

---

### ADR-014 — GST on fees is a cost by default, with an explicit ITC switch
**Date:** 2026-10-26 · **Status:** Accepted · **Adopted from the handbook**

**Decision.** `fee_gst_recoverable` defaults to `false`, so GST on marketplace fees is counted as a cost. Setting it to `true` removes it from contribution and must display a warning that ITC eligibility depends on the seller's registration, which this tool cannot determine.

**Alternatives rejected.** *Default to recoverable* — optimistic and would overstate profit. *Omit the switch* — removes a legitimate and instructive treatment.

**Consequences.** AT-1.2 proves the switch changes the result (₹1,624.08 → ₹1,956.00: the only term removed is `fee_gst`, so `9000.00 − 1844.00 − 5000.00 − 200.00`), so it cannot be a silent no-op. The original figure of ₹1,955.11 in this entry was an arithmetic error and was corrected by ADR-030.

---

### ADR-015 — A returned unit is written off; resale recovery is fixed at zero in P0
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The fraction of landed cost recovered on a returned unit is a named constant fixed at `0`. A returned unit's product cost is lost, and the marketplace fees on its order are not reversed.

**Alternatives rejected.** *Expose resale recovery as a P0 control* — adds a slider whose value is unknowable and which would tempt users to model returns optimistically. *Reverse the fees on the returned order* — contradicts the conservative treatment the fixture depends on.

**Consequences.** Must be labelled a stated assumption and never presented as how a real marketplace behaves.

---

### ADR-016 — Two transparent heuristics, no optimality claim
**Date:** 2026-10-26 · **Status:** Accepted · **Deviation from the handbook**

**Decision.** The Budget Lab offers exactly two strategies — Plan A (ROI-first greedy, no concentration cap) and Plan B (the same score with a per-SKU cap). Both are greedy heuristics. The words "optimal", "best", "maximises", and "guaranteed" are banned **as claims about a plan** (a statement that a product's apparent appeal may rest on a weak assumption is not a plan claim and is permitted).

**Context.** The handbook implements four plans, two of which are *exact* group-knapsack solutions. The brief requires two transparent heuristics and forbids the optimality claim.

**Alternatives rejected.** *Port the handbook's exact DP solver* — violates the brief's honesty constraint, and its float arithmetic violates ADR-006. *Offer four plans* — more surface, more explanation, no additional decision value for the user.

**Consequences.** The handbook's Appendix A plan values are **not reproducible** and must not be ported as expectations. A string assertion (AT-7.15) enforces the language ban.

---

### ADR-017 — Allocation score is a base/conservative blend per rupee of capital
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** `score(qty) = (0.5 · expected_profit(qty, Base) + 0.5 · expected_profit(qty, Conservative)) / (qty · landed_cost)`, and both plans rank by this single score.

**Alternatives rejected.** *Rank by base-case ROI only* — ignores the downside entirely and makes the two plans differ only by their cap. *Weight conservative more heavily* — an arbitrary choice with no basis; an even blend is the most defensible default and is visible as an assumption.

**Consequences.** The weighting is displayed in the Methodology view as an assumption, not a finding.

---

### ADR-018 — Concentration cap defaults to 40% of budget
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** `default_max_share_per_sku = 0.40`, editable, applied only to Plan B.

**Alternatives rejected.** *The handbook's 25%* — tighter, but arbitrary; 40% is the brief's example and is configurable anyway.

**Consequences.** Plan B is meaningfully different from Plan A out of the box. Asserted by AT-7.8.

---

### ADR-019 — The conservative scenario is a uniform price and sell-through shock
**Date:** 2026-10-26 · **Status:** Accepted · **Adopted from the handbook**

**Decision.** Conservative means price × 0.95 and sell-through × 0.75 for every SKU, with fees recomputed at the reduced price. The UI must state that a uniform shock cannot demonstrate the benefit of diversification.

**Alternatives rejected.** *Per-SKU shocks* — implies knowledge of which SKU will fail, which the tool does not have. *Drop the scenario* — removes the honest uncertainty story the brief requires.

**Consequences.** A diversified plan may score worse in the conservative scenario than a concentrated one. That outcome is expected, must be stated, and must not be hidden or massaged.

---

### ADR-020 — Seed catalogue targets a portfolio total of ₹26,761.53, but that is not a golden test
**Date:** 2026-10-26 · **Status:** **DRAFT — see AP-1**

**Decision (recommended).** The sample-data generator aims for a realistic nine-to-ten-SKU catalogue including at least one loss-making SKU, but the handbook's ₹26,761.53 portfolio total is **not** a required acceptance value. The required arithmetic anchor is fixture v1 (₹1,624.08). Aggregate correctness is enforced by internal invariants instead.

**Context.** Reproducing ₹26,761.53 requires the handbook's exact generator seed and algorithm, which the brief does not require and which the handbook's own author never executed.

**Alternatives rejected.** *Require ₹26,761.53* — makes the test depend on a generator that may not be faithfully recoverable, which is exactly how a suite acquires a permanently red test. *Ship no aggregate check* — loses the check that catches aggregation and rounding bugs.

**Consequences.** Aggregation is verified by AT-6.2 and AT-6.3 (per-SKU sums equal the portfolio total exactly) and by AT-6.6 (a loss-making SKU exists), rather than by an externally sourced constant.

---

## §4 Schema and interface decisions

### ADR-021 — The brief's CSV field names are canonical; handbook names are accepted as aliases
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** `products` uses `sku, name, category, supplier_unit_cost, inbound_unit_cost, packaging_unit_cost, target_price, current_stock, min_order_qty, max_supply`. `transactions` uses `transaction_id, sku, order_date, units_sold, returned_units, selling_price, discount_per_unit, refund_per_returned_unit, settlement_fees_total, ads_cost, other_charges`. The handbook's divergent header names are accepted through the same normalisation path used for case, whitespace, and BOM handling. `cost_updated_on` is retained as an optional products column.

**Alternatives rejected.** *Use the handbook's names* — the brief's names are the documented contract. *Accept both as equal* — two names for one field invites silent divergence.

**Consequences.** Header normalisation and alias mapping must be tested (AT-5.2, AT-5.7). Extra unknown columns are ignored with a warning.

---

### ADR-022 — `refund_per_returned_unit` is GST-inclusive
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The refund field is defined as a GST-**inclusive** amount per returned unit, converted to ex-GST in the engine exactly as the selling price is. When absent, the refund defaults to the ex-GST selling price.

**Context.** The brief's field name for this value is `refund_inclusive_per_return`; the handbook calls the same concept `refund_per_returned_unit`. The two names imply different semantics, and the brief's name is the explicit one. `refund_per_returned_unit` is retained as the canonical column name (per ADR-021) with `refund_inclusive_per_return` accepted as an alias.

**Alternatives rejected.** *Treat it as ex-GST* — would understate refunds by the GST factor and is contradicted by the brief's own field name.

**Consequences.** Documented in `BUSINESS_RULES.md` §3, and exercised by the return-path tests.

---

### ADR-023 — API surface is fixed at nine P0 endpoint operations over eight paths
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** `GET /health`, `GET /assumptions`, `PUT /assumptions`, `GET /products`, `POST /import/validate`, `POST /import`, `GET /profit/sku/{sku}`, `GET /profit/reconcile`, `POST /budget/simulate`, plus the FastAPI `/docs`. `DELETE /import/{batch_id}` is P1.

**Alternatives rejected.** *Fewer endpoints with query flags* — harder to test and harder to document. *More endpoints, one per view* — couples the API to the UI.

**Consequences.** Every endpoint's happy path and failure modes are specified in `ACCEPTANCE_TESTS.md` AT-8. Error bodies are typed and uniform.

---

### ADR-024 — Money crosses the wire as a decimal string
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** Every monetary field is serialised as a JSON string containing a decimal literal (for example `"1624.08"`). `"n/a"` is permitted for ratio fields.

**Alternatives rejected.** *JSON numbers* — parsed as IEEE floats by every mainstream client, reintroducing exactly the drift ADR-006 eliminates.

**Consequences.** The TypeScript client treats money as `string` and never does arithmetic on it. Asserted by AT-8.12 and AT-2.7.

---

## §5 Process decisions

### ADR-025 — Documentation is generated and audited before any source code
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The order is: plan → human approval → generate these 13 documents → cross-document audit → authorise bounded implementation tasks. Documentation time is counted inside the four-day budget and is capped at 2 hours.

**Alternatives rejected.** *Write code and document afterwards* — guarantees drift and removes the audit gate. *Document for a week* — the brief forbids inflating a 20–28 hour plan.

**Consequences.** The Day-1 documentation gate is blocking. If the docs audit reveals an unresolved contradiction, implementation does not start.

---

### ADR-026 — 16 bounded tasks, not hundreds of microphases
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** `PHASES_DETAILED.md` contains exactly 16 tasks. Each is a vertical slice that changes a testable user outcome and names: objective, prerequisite, files owned, done condition, unit/integration/E2E checks, fallback, time estimate, and a suggested agent prompt.

**Alternatives rejected.** *A phase-per-function breakdown* — consumes planning context, encourages checkbox completion, and produces no testable outcome. The brief names this anti-pattern explicitly.

**Consequences.** A task that cannot be finished in its box takes its fallback; it is not split into microphases. The count stays between 12 and 16.

---

### ADR-027 — Allocator and profit assumptions are surfaced, never buried
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** Every Budget Lab plan line carries an `ASSUMED` flag. Every displayed money figure has an adjacent affordance to the assumptions that produced it. `sell_through` and `salvage` are labelled assumptions unless measured, and nothing in this project measures them.

**Alternatives rejected.** *Show numbers with a global disclaimer* — a disclaimer separated from the number it qualifies is ignored.

**Consequences.** A UI acceptance check (AT-10.6) fails a view that shows an unexplained figure.

---

### ADR-028 — Both original documents are treated as reference, not as authority
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The planning brief and the project handbook are recorded as source material. Where this document set departs from either, the departure is recorded above. Neither PDF is re-read to settle a conflict.

**Context.** The handbook's own text states its API, UI, database and Docker sections were syntax-checked rather than executed, and one of its own database test files is annotated as never having been run by its author.

**Alternatives rejected.** *Treat the handbook's code listings as a specification to copy* — would import float money, an exact-optimisation allocator, and an unexecuted database layer into a project that forbids all three.

**Consequences.** No handbook code is copied. It is read for financial semantics and pedagogical framing only.

---

### ADR-029 — Handbook schedule anchors are not portable
**Date:** 2026-10-26 · **Status:** Accepted

**Decision.** The handbook's dated plan (15 October – 12 November 2026, Gates 1–4, exam pauses) is discarded. Timing comes solely from `MASTER_PLAN.md`'s four-day structure.

**Alternatives rejected.** *Map the handbook's dates onto four days* — the handbook's plan is a multi-week study schedule, not a four-day build, and its gates measure different things.

**Consequences.** Handbook content requirements survive (privacy caveats, synthetic-data policy, method transparency); handbook dates and gate names do not appear in this set.

---

### ADR-030 — Corrective entry: the ITC-switch expected value is ₹1,956.00, not ₹1,955.11
**Date:** 2026-10-26 · **Status:** Accepted · **Corrects ADR-014**

**Decision.** The expected contribution for fixture v1 with `fee_gst_recoverable = true` is `Decimal("1956.00")`. The value ₹1,955.11 written into ADR-014, `BUSINESS_RULES.md` §10.4.3 and `ACCEPTANCE_TESTS.md` AT-1.2 was an arithmetic error and has been corrected in all three.

**Context.** The cross-document audit caught the error. The stated derivation and the stated value contradicted each other: `1624.08 + 331.92 = 1956.00` exactly (`.08 + .92 = 1.00`), so the parenthetical in AT-1.2 already falsified ₹1,955.11.

**Derivation (two independent routes).**
- Engine order of operations: with ITC on, the only term removed is `fee_gst`, so `9000.00 − 1844.00 − 5000.00 − 200.00 = 1956.00`.
- Payout route: `8444.08 − (1620.00 − 331.92) − 5000.00 − 200.00 = 8444.08 − 1288.08 − 5200.00 = 1956.00`.

**Why an ADR is required.** `AGENTS.md` rule 4 forbids changing an expected value to make a test pass without human approval and a `DECISIONS.md` entry. This is the reverse case — a wrong expectation being corrected to the arithmetically derived one — but the rule applies either way, so the correction is recorded here rather than made silently.

**Human sign-off.** This correction is flagged in the Stage-2 summary as an open item. The derivation is verifiable by hand before approval.

**Alternatives rejected.** *Leave ₹1,955.11 and adjust the fixture so it produces that number* — would corrupt the fixture to match a typo. *Silently edit the three files* — violates the append-only rule and the approval gate.

**Consequences.** AT-1.2 now asserts `Decimal("1956.00")`. No other figure moves: the ₹1,624.08 anchor, AT-1.3's ₹2,624.08, the settlement-override values and every Budget Lab number are unaffected.

---

None yet.

**Corrected entries (not superseded — history preserved):**

- **ADR-014** stated the ITC-switch result as ₹1,955.11. That figure was an arithmetic error; the correct value is ₹1,956.00. **ADR-030** records the correction. ADR-014's decision text is unchanged.

---

## Cross-references

- Authority order and conflict rules: `CONTEXT.md` §3
- Money semantics behind ADR-006 to ADR-020: `BUSINESS_RULES.md`
- Expected values behind ADR-008, ADR-009, ADR-011, ADR-016: `ACCEPTANCE_TESTS.md`
- Scope behind ADR-002 and ADR-003: `PRD.md`
- Module layout behind ADR-004: `ARCHITECTURE.md`
