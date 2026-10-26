# BUSINESS_RULES.md — Authoritative Money, Tax and Data Semantics

| Field | Value |
|---|---|
| **Status** | Approved specification. No source code exists yet. |
| **Authority** | Second-highest. Overrides PRD, ARCHITECTURE, TECH_STACK, PHASES_DETAILED on any money or data question. Subordinate only to an approved entry in `DECISIONS.md`. |
| **Change control** | Any change to a formula, a field semantic, the rounding rule, or the fixture requires human approval and a new dated entry in `DECISIONS.md`. Agents must not edit this file to make a test pass. |
| **Owner** | Project owner (human). |
| **Data policy** | Synthetic and owner-authorised data only. See `SECURITY.md`. |

> **Not tax advice.** Every GST, TCS, TDS, ITC and fee figure in this document is a **configurable modelling assumption with no legal force**. A qualified professional must verify any treatment before it is used for filing or a business decision. The application must never present these numbers as tax guidance.

---

## 0. Scope of these rules

These rules govern:

1. The five money terms and which one this product computes.
2. The complete set of configurable assumptions and their defaults.
3. The exact per-transaction calculation order and rounding behaviour.
4. The meaning of every input field, and every edge case.
5. The Budget Lab's expected-profit model, constraints and scenarios.
6. The product, transaction and assumption data schemas.

These rules do **not** govern: authentication, multi-tenancy, live marketplace integration, order execution, repricing, or forecasting. All are out of scope (see `PRD.md` §MVP boundaries).

---

## 1. The five things people call "profit"

Conflating these is the single most common beginner error, and it is the reason this product exists.

| Term | Meaning | Includes GST? | Computed by ArbitrageIQ? |
|---|---|---|---|
| **Sales value** | What customers paid. GST is collected on the government's behalf, not earned. | Yes | Shown for context only |
| **Net revenue** | Sales value with GST removed, minus refunds on returned units. | No | **Yes** — direct input to contribution |
| **Marketplace payout** | What the marketplace actually transfers after deducting fees, GST on fees and withholding. | Mixed | Shown for reconciliation/education only |
| **Contribution profit** | Net revenue − product cost − marketplace fees − GST on fees (unless recoverable) − ads − other charges. **This is the product's headline number.** | No | **Yes** |
| **Accounting profit** | Contribution minus overheads (rent, salaries, depreciation, software, the owner's own time) and income tax. | No | **No, never.** Must never be implied. |

**Hard rule:** every screen that shows a rupee figure derived from contribution must state that it excludes overheads and income tax. A user must never read "contribution profit ₹X" as "money in my bank".

---

## 2. Configurable assumptions (the `fee_assumptions` object)

Assumptions are **dated, editable records**, never hardcoded constants. They are stored in the database, exposed via the assumptions API, and displayed next to every derived figure.

| Key | Type | Default | Unit | Notes |
|---|---|---|---|---|
| `referral_rate` | Decimal | `0.08` | fraction of price paid | Illustrative only. Real rates vary by category, price band and date. |
| `zero_referral_below` | Decimal | `1000.00` | ₹ | Referral charged only when price paid ≥ this. Models reported 2026 change. Illustrative. |
| `closing_fee` | Decimal | `25.00` | ₹ per unit shipped | Illustrative. |
| `shipping_fee` | Decimal | `65.00` | ₹ per unit shipped | Illustrative. |
| `fulfilment_fee` | Decimal | `0.00` | ₹ per unit shipped | Present for completeness; zero in the demo. |
| `product_gst_rate` | Decimal | `0.18` | fraction | Per-product-*type*. Must be set per SKU category. Illustrative. |
| `gst_on_fees_rate` | Decimal | `0.18` | fraction of marketplace fees | Reported rate for marketplace services. |
| `fee_gst_recoverable` | bool | `false` | — | `false` = conservative (GST on fees is a cost). `true` = ITC claimed, GST on fees excluded from contribution. |
| `tcs_rate` | Decimal | `0.005` | fraction of net taxable value | Section 52. **Cash-flow item, not a cost.** Never subtracted from contribution. |
| `tds_rate` | Decimal | `0.001` | fraction of gross sales | Section 194-O. **Cash-flow item, not a cost.** Never subtracted from contribution. |
| `default_sell_through` | Decimal | `0.80` | fraction | Budget Lab assumption. |
| `default_salvage` | Decimal | `0.50` | fraction of landed cost | Budget Lab assumption. |
| `default_budget` | Decimal | `50000.00` | ₹ | Budget Lab default. |
| `default_max_share_per_sku` | Decimal | `0.40` | fraction of budget | Concentration cap for the capped heuristic. |
| `effective_from` | date | creation date | — | Every assumption row carries the date it became effective. |
| `note` | text | — | — | Free text; must carry the source or "ILLUSTRATIVE DEMO ASSUMPTION". |

**Rules**

- **R1.** Defaults are illustrative fixtures, not market truth. Every assumption row must be labelled as such in the UI.
- **R2.** Rates are validated on write: `referral_rate`, `product_gst_rate`, `gst_on_fees_rate`, `tcs_rate`, `tds_rate` and `default_sell_through` must be in `[0, 1]`; `default_salvage` in `[0, 1]`; fees and budget must be `>= 0`. `default_max_share_per_sku` must be in `(0, 1]`.
- **R3.** TCS and TDS are **withholding credits**, never costs. Including them in contribution would be an error.
- **R4.** `fee_gst_recoverable = true` removes GST on fees from contribution and must be paired with a visible warning that ITC eligibility depends on the seller's registration, which this tool cannot determine.

---

## 3. Field semantics — read this before writing any formula

> ### ⚠️ THE GROSS/NET TRAP
> **`transactions.units_sold` is GROSS units shipped, and it INCLUDES returned units.**
>
> The golden fixture is 10 units shipped with 1 returned. Revenue is earned on **9**. Marketplace fees and product cost are modelled on **10**.
>
> If anyone — human or agent — reads `units_sold` as *net*, the fixture silently becomes ₹1,624.08 → wrong, and every figure in the app is defensibly plausible and wrong. This is the highest-severity risk in the project.

| Field | Table | Type | Required | Semantics |
|---|---|---|---|---|
| `sku` | products | text | Yes | Primary key. Case-sensitive, stored trimmed. Unique. |
| `name` | products | text | Yes | Display name. |
| `category` | products | text | Yes | Used to select `product_gst_rate`. |
| `supplier_unit_cost` | products | Decimal ≥ 0 | Yes | Wholesale purchase price per unit, GST-inclusive as paid. |
| `inbound_unit_cost` | products | Decimal ≥ 0 | Yes | Freight-in per unit. |
| `packaging_unit_cost` | products | Decimal ≥ 0 | Yes | Packaging per unit. |
| `target_price` | products | Decimal > 0 | Yes | Planned GST-**inclusive** selling price. |
| `current_stock` | products | int ≥ 0 | Yes | On-hand units. |
| `min_order_qty` | products | int ≥ 1 | Yes | MOQ. |
| `max_supply` | products | int ≥ 0 | Yes | Maximum units the supplier can supply in the period. |
| `cost_updated_on` | products | date | No | Optional; unused in P0. Retained for a possible future stale-cost warning (not scheduled). Null allowed. |
| `transaction_id` | transactions | text | Yes | Unique. Primary key. Deduplication key. |
| `order_date` | transactions | date | Yes | `YYYY-MM-DD`. |
| `sku` | transactions | text | Yes | Must exist in `products`, else the row is rejected. |
| `units_sold` | transactions | int ≥ 0 | Yes | **GROSS units shipped, including returned units.** |
| `returned_units` | transactions | int ≥ 0 | Yes | Must satisfy `0 ≤ returned_units ≤ units_sold`, else reject. |
| `selling_price` | transactions | Decimal > 0 | Yes | GST-inclusive price paid before discount. |
| `discount_per_unit` | transactions | Decimal ≥ 0 | Yes | `0 ≤ discount_per_unit ≤ selling_price`. |
| `refund_per_returned_unit` | transactions | Decimal ≥ 0 | No | **GST-INCLUSIVE** refund per returned unit. Blank/absent ⇒ the refund defaults to the ex-GST selling price (`e_refund = e`). |
| `settlement_fees_total` | transactions | Decimal ≥ 0 | No | Actual settlement fees, **GST-inclusive**. When present, replaces the fee model (see §6). |
| `ads_cost` | transactions | Decimal ≥ 0 | No | Advertising for this line. Default `0`. |
| `other_charges` | transactions | Decimal ≥ 0 | No | Any other cost for this line. Default `0`. |

**Landed cost L** is always `supplier_unit_cost + inbound_unit_cost + packaging_unit_cost`.

---

## 4. The per-transaction calculation, in exact order

This is the algorithm. Order matters. Rounding happens **once per line**, at the end.

```
Inputs: one transaction row + its product row + the active fee_assumptions

1.  p        = selling_price - discount_per_unit                    # GST-inclusive price paid
2.  e        = round_2( p / (1 + product_gst_rate) )                # ex-GST price per unit
3.  e_refund = round_2( refund_per_returned_unit / (1 + product_gst_rate) )   if refund present else e
4.  gross_revenue = e * units_sold
5.  refunds       = e_refund * returned_units
6.  net_revenue   = gross_revenue - refunds
7.  fees_ex_gst, fee_gst = fee_components(p, units_sold, row, assumptions)    # see §5 and §6
8.  product_cost  = L * units_sold - resale_fraction * L * returned_units     # resale_fraction default 0
9.  ads           = ads_cost
10. other         = other_charges
11. contribution  = net_revenue - product_cost - fees_ex_gst
                    - (0 if fee_gst_recoverable else fee_gst) - ads - other
12. contribution  = round_2(contribution)                            # HALF-UP, once, at line end
Investigate: never store an unrounded intermediate in the database.
```

`resale_fraction` (fraction of landed cost recovered on a returned unit) is **fixed at `0` in the MVP**, meaning a returned unit is written off. It is a named constant so a future version can expose it. Do **not** silently expose it as a slider in P0.

**Rounding rule (authoritative).** Money is `Decimal`. Round **half-up to 2 decimal places at the end of each transaction line**, then **sum the rounded line values** to get per-SKU and portfolio totals. Never round at the end of an aggregate. Never use binary floats for money anywhere: not in arithmetic, not in storage, not in JSON transport.

**Ratio rule (authoritative).** Any ratio with a zero or missing denominator (profit per unit with 0 net units, margin with 0 net revenue, ROI with 0 inventory cost) is rendered as the string `"n/a"`. It is **never** `0`, `inf`, or `NaN`.

---

## 5. The fee model

Used **only** when `settlement_fees_total` is absent (see §6).

```
referral       = (p >= zero_referral_below) ? p * referral_rate : 0
closing        = closing_fee
shipping       = shipping_fee
fulfilment     = fulfilment_fee
fees_ex_gst    = (referral + closing + shipping + fulfilment) * units_sold      # GROSS units
fee_gst        = round_2(fees_ex_gst * gst_on_fees_rate)
```

**Rules**

- **F1.** Fees are charged on **gross units shipped**, because the returned unit's order was still processed by the marketplace. This is the conservative treatment and it is what produces the golden fixture.
- **F2.** The referral fee is charged on `p` (the GST-inclusive price paid). Real fee bases may differ (some use the ex-GST value or include shipping). This is a documented assumption, not a claim.
- **F3.** The zero-referral floor is applied to `p` **before** rate multiplication, per the formula above.
- **F4.** GST on fees is computed on `fees_ex_gst`, never on individual components separately.

---

## 6. Settlement fees override the model — the double-count guard

> **Rule S1 (Critical).** If a transaction row has a non-null `settlement_fees_total`, the engine uses **that figure** and **does not** apply the §5 model to that row. It is never added to the modelled fees.
>
> **Rule S2.** `settlement_fees_total` is defined as GST-**inclusive**. It is split into `fees_ex_gst = total / (1 + gst_on_fees_rate)` and `fee_gst = total - fees_ex_gst`, so the `fee_gst_recoverable` switch still behaves consistently.
>
> **Rule S3.** A test must exist that proves a row with settlement data produces a different result from the modelled path, and that the two are never summed.

---

## 7. GST layers, and what is deliberately not modelled

These are six separate layers. Mixing them is the second-most-common error after §3.

| # | Layer | Treatment in ArbitrageIQ |
|---|---|---|
| 1 | **Marketplace fees** | Modelled per §5, or taken from settlement per §6. Not hardcoded. |
| 2 | **GST on marketplace fees** | Modelled at `gst_on_fees_rate`. Counted as a cost by default. Recoverable only if `fee_gst_recoverable = true`, with a warning. |
| 3 | **GST on product sales** | Removed from revenue via `p / (1 + product_gst_rate)`. Prices are treated as GST-inclusive. Rate is per product type and must be set by the user. |
| 4 | **TCS under Section 52** | **Cash-flow credit only. Never a cost. Not deducted from contribution.** Displayed for information where a payout reconciliation is shown. |
| 5 | **TDS under Section 194-O** | **Cash-flow credit only. Never a cost. Not deducted from contribution.** |
| 6 | **Income tax on profit** | **Not modelled at all.** Must be stated wherever the product defines profit. |

**Required disclaimer text**, to appear on the Methodology view and beside any GST control:

> Marketplace fee rates, GST rates and thresholds in this tool are illustrative demo assumptions with a recorded effective date. They are not current Amazon or Indian tax figures. This tool is not tax advice, is not an accounting system, and does not determine your GST registration obligations or ITC eligibility. Verify with a qualified professional.

---

## 8. Derived metrics

Using: `n = units_sold - returned_units` (net units), `e` = ex-GST price, `L` = landed cost, `contribution` = the line value from §4.

| Metric | Formula | Denominator | Zero-denominator result |
|---|---|---|---|
| Profit per unit | `contribution / n` | net units | `"n/a"` |
| Margin % | `contribution / net_revenue * 100` | net revenue | `"n/a"` |
| ROI % | `contribution / (L * units_sold) * 100` | inventory cost of units **shipped** | `"n/a"` |
| Break-even price | smallest `p` such that single-unit contribution ≥ 0, steady state, no returns | — | — |
| Minimum price for target margin `m` | smallest `p` such that `contribution / e >= m`, steady state, no returns | — | — |
| Inventory cover (not scheduled — listed for completeness) | `current_stock / average_daily_net_units` | daily net units | `"n/a"` |

Break-even and target-margin prices are solved on the **steady-state single-unit** case (no returns, no ads) and must be labelled as such — they are a pricing floor, not a forecast.

---

## 9. Aggregation

- **Per SKU:** sum the rounded per-line contributions of all transactions for that SKU.
- **Portfolio:** sum the per-SKU totals.
- Percentages are rounded to 2 dp at display time only.
- Duplicate `transaction_id` values are rejected at import, so double-counting cannot occur by reimport.

---

## 10. Golden fixture v1 — the ₹1,624.08 scenario

> **This is a synthetic test fixture.** It is not a real Amazon settlement, not a real order, and not tax advice. It exists solely to pin the arithmetic.

### 10.1 Stated assumptions

| Assumption | Value |
|---|---|
| `units_sold` (GROSS, includes returned) | 10 |
| `returned_units` | 1 |
| `selling_price` (GST-inclusive) | ₹1,180.00 |
| `discount_per_unit` | ₹0.00 |
| `product_gst_rate` | 18% |
| Landed cost `L` = supplier + inbound + packaging | ₹500.00 per unit shipped |
| `referral_rate`, charged only if `p >= 1000` | 8% |
| `zero_referral_below` | ₹1,000.00 (so the referral applies here) |
| `closing_fee` | ₹25.00 per unit |
| `shipping_fee` | ₹65.00 per unit |
| `fulfilment_fee` | ₹0.00 |
| `gst_on_fees_rate` | 18% |
| `fee_gst_recoverable` | `false` (GST on fees is a cost) |
| `ads_cost` | ₹200.00 total |
| `resale_fraction` on returned unit | 0 (written off) |
| Fees on the returned unit's order reversed? | No (conservative) |
| `settlement_fees_total` | absent (so the §5 model applies) |

### 10.2 Derivation A — the engine's order of operations

```
p              = 1180.00 - 0            = 1180.00
e              = 1180.00 / 1.18         = 1000.00            (exact)
gross_revenue  = 1000.00 * 10           = 10000.00
refunds        = 1000.00 * 1            = 1000.00            (e_refund defaults to e)
net_revenue    = 10000.00 - 1000.00     =  9000.00
referral       = 1180.00 * 0.08         =    94.40           (p >= 1000, so charged)
fees_ex_gst    = (94.40 + 25 + 65 + 0) * 10
                                        =   184.40 * 10 = 1844.00
fee_gst        = 1844.00 * 0.18         =   331.92
product_cost   = 500.00 * 10 - 0        =  5000.00
ads            =                          200.00
contribution   = 9000.00 - 1844.00 - 331.92 - 5000.00 - 200.00
               = 6824.08 - 5000.00 - 200.00
               = 1624.08
```

### 10.3 Derivation B — independent reconciliation via the payout route

This route is deliberately different: it starts from cash and removes liabilities. If A and B agree, the model is internally consistent.

```
sales value (gross, GST-inclusive)   = 10 * 1180       = 11800.00
refund paid to customer (inclusive)  =  1 * 1180       =  1180.00
cash from customers                  = 11800 - 1180    = 10620.00
marketplace retained (fees + GST)    = 1844.00 + 331.92 = 2175.92
marketplace payout                   = 10620 - 2175.92 =  8444.08
GST owed to government               = (10 * 180) - (1 * 180) = 1800 - 180 = 1620.00
less product cost                    =                        5000.00
less advertising                     =                         200.00
contribution                         = 8444.08 - 1620 - 5000 - 200
                                     = 1624.08
```

**A and B agree exactly: ₹1,624.08.**

### 10.4 Mandatory obligations arising from this fixture

1. A backend test must assert **exactly** `Decimal("1624.08")` — not a float, not an approximation, not a rounded string.
2. The expected value in that test must be written from the table in §10.1, **never** produced by running the function under test.
3. `fee_gst_recoverable = true` on the same fixture must yield a **different** value, `Decimal("1956.00")` — the only term removed is `fee_gst`, so `9000.00 − 1844.00 − 5000.00 − 200.00 = 1956.00` (and `1624.08 + 331.92 = 1956.00`). Both must be tested so the switch cannot be a no-op. See `DECISIONS.md` ADR-030 for the correction of an earlier erroneous ₹1,955.11 in this clause.
4. Removing the return (`returned_units = 0`) while keeping `units_sold = 10` must yield a **different** value, proving the return path is live.

> **On generalisation.** The return treatment in this fixture (returned unit written off, fees on the returned order not reversed) is a **stated assumption**. It must not be presented as how Amazon or any marketplace actually behaves.

---

## 11. Budget Lab — expected profit, constraints and scenarios

### 11.1 Two different profits — never conflate them

| | Profitability view | Budget Lab |
|---|---|---|
| Basis | **Realised** — from actual transaction rows | **Expected** — from assumptions |
| Trust | Observed demo data | ASSUMED. Labelled everywhere. |
| Formula | §4 | §11.2 |

Both appear in the UI. They must never share a label, colour key, or column without the word "expected" or "assumed".

### 11.2 Expected profit for buying `qty` units

```
per_sold_unit = e(price) - fee_cost_per_order(price) - ads_per_unit      # ex-GST rev minus fees, before product cost
sold          = min(1, sell_through) * qty   # 1 is a dimensionless fraction cap, not money
unsold        = qty - sold
expected_profit(qty) = sold * per_sold_unit
                     - qty * L
                     + unsold * salvage * L
```

`sell_through` and `salvage` are **assumptions**. Every plan line that depends on them carries an `ASSUMED` flag.

### 11.3 Scenarios

| Scenario | `price_shock` | `sellthrough_shock` |
|---|---|---|
| Base | 1.00 | 1.00 |
| Conservative (downside) | 0.95 | 0.75 |

The conservative scenario **recomputes fees at the lower price**. It is a uniform shock applied to all SKUs.

> **Required honesty statement (must appear in the Budget Lab UI):** A uniform downside shock cannot demonstrate the main benefit of diversification. Because every SKU is stressed equally, a diversified plan can score *worse* in the conservative scenario than a concentrated one, even though it is genuinely more resilient to a product-specific failure such as a supplier default, a stock-out, or a listing suspension. The scenario is a stress test of price and sell-through, not proof of diversification.

### 11.4 The two strategies

| | Plan A — ROI-first | Plan B — Diversified cap |
|---|---|---|
| Score | `risk_adjusted_contribution / (qty * L)` | **Identical score** |
| Concentration cap | none | `max_share_per_sku` of budget (default 40%) |
| Method | greedy, descending score | greedy, descending score, cap-aware |
| Labelled "optimal"? | **No** | **No** |

```
risk_adjusted_contribution(qty) = 0.5 * expected_profit(qty, Base)
                                + 0.5 * expected_profit(qty, Conservative)
score(qty)                      = risk_adjusted_contribution(qty) / (qty * L)
```

**Both are transparent heuristics.** The product must never claim, imply, or display the words "optimal", "best", "maximises profit", "guaranteed", or "predicted sales" for either plan. The documentation and UI must state that a product with high ROI may have a small supply cap, that MOQ creates lumps, and that the most attractive-looking numbers rest on the weakest assumption (`sell_through`).

### 11.5 Constraints — the invariants

Enforced on every plan, no exceptions:

| ID | Invariant |
|---|---|
| B1 | `sum(qty * L for all SKUs) <= budget` |
| B2 | `qty` is a non-negative integer for every SKU |
| B3 | `qty == 0` or `qty >= min_order_qty` |
| B4 | `qty <= max_supply` |
| B5 | Plan B only: `qty * L <= max_share_per_sku * budget` per SKU |
| B6 | No `NaN`, no `Infinity`, no `None` in any monetary output |
| B7 | Identical inputs produce identical outputs (deterministic; no randomness, no clock dependence) |
| B8 | A SKU with non-positive per-unit economics must never receive a positive `qty` in Plan A |
| B9 | Budget ₹500 with the sample catalogue buys nothing |
| B10 | Every milestone/target price must be met; rounding must never push spend one rupee over budget |

The budget is enforced in **integer paise** internally, so B10 can never fail through a rounding edge.

---

## 12. Explicitly out of scope — must not be claimed

The application must never do or imply any of the following:

1. Real Amazon fee rates, real GST slabs, or real demand figures.
2. Scraping, bypassing access controls, or using seller-account credentials.
3. Optimal allocation, mathematically or otherwise.
4. Sales forecasting, machine learning, or "AI predicts sales".
5. Automated repricing, ordering, or listing changes.
6. Accounting profit, tax filing, or GST compliance advice.
7. Authentication, multi-user access, multi-tenancy, or SaaS.
8. Treating synthetic sell-through as evidence of real marketplace demand.

---

## 13. Cross-references

- Expected values and test matrix: `ACCEPTANCE_TESTS.md`
- Approved decisions and rejected alternatives: `DECISIONS.md`
- Trust boundaries and import safety limits: `SECURITY.md`
- Module layout implementing these rules: `ARCHITECTURE.md`
- User-facing scope: `PRD.md`
- Task-by-task build order: `PHASES_DETAILED.md`
