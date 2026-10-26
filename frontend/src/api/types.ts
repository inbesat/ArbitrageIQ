/**
 * The API wire contract, mirrored from `backend/arbitrageiq/schemas.py`.
 *
 * Every monetary and ratio value is a decimal STRING (`plans/DECISIONS.md` ADR-024,
 * `plans/ACCEPTANCE_TESTS.md` AT-8.12). Nothing in this file, or in anything that
 * consumes it, may convert one to a JavaScript number, or do arithmetic on one:
 * the backend alone computes money (`AGENTS.md` rule 7, `plans/TECH_STACK.md` §3.1).
 *
 * `ratio` follows the same rule: `margin_pct` and `roi_pct` are the literal `"n/a"`
 * when the denominator is zero (`plans/BUSINESS_RULES.md` §8).
 */

/** A decimal string exactly as the backend serialised it. Never a number. */
export type Money = string;

/** A decimal string, or the literal `"n/a"` for an undefined ratio. */
export type Ratio = Money | 'n/a';

export interface Health {
  status: string;
  version: string;
  db: string;
}

export interface Assumptions {
  referral_rate: Money;
  zero_referral_below: Money;
  closing_fee: Money;
  shipping_fee: Money;
  fulfilment_fee: Money;
  product_gst_rate: Money;
  gst_on_fees_rate: Money;
  fee_gst_recoverable: boolean;
  tcs_rate: Money;
  tds_rate: Money;
  default_sell_through: Money;
  default_salvage: Money;
  default_budget: Money;
  default_max_share_per_sku: Money;
  effective_from: string;
  note: string;
}

export interface Product {
  sku: string;
  name: string;
  category: string;
  supplier_unit_cost: Money;
  inbound_unit_cost: Money;
  packaging_unit_cost: Money;
  target_price: Money;
  current_stock: number;
  min_order_qty: number;
  max_supply: number;
  cost_updated_on: string | null;
}

/** One rejected CSV row. `value` is the raw cell, echoed back for the operator. */
export interface Rejection {
  row: number;
  field: string;
  value: string | null;
  reason: string;
}

export interface ImportReport {
  imported: number;
  skipped: number;
  rejected_total: number;
  rejected: Rejection[];
  dry_run?: boolean;
  warnings?: string[];
}

export interface BreakdownLine {
  transaction_id: string | null;
  sku: string;
  net_units: number;
  fee_source: string;
  price_paid: Money;
  ex_gst_unit_price: Money;
  gross_revenue: Money;
  refunds: Money;
  net_revenue: Money;
  referral_fee: Money;
  fees_ex_gst: Money;
  fee_gst: Money;
  product_cost: Money;
  ads: Money;
  other_charges: Money;
  contribution: Money;
  profit_per_unit: Money;
  margin_pct: Ratio;
  roi_pct: Ratio;
}

export interface SkuProfit {
  sku: string;
  totals: { contribution: Money; line_count: number };
  assumptions: Assumptions;
  lines: BreakdownLine[];
}

export interface Reconcile {
  per_sku: Record<string, Money>;
  portfolio_total: Money;
}

export interface PlanLine {
  sku: string;
  qty: number;
  capital: Money;
  expected_contribution: Money;
  /** True while the line depends on the assumed sell-through or salvage value. */
  assumed: boolean;
}

export interface Plan {
  strategy: string;
  label: string;
  capital_used: Money;
  budget_remaining: Money;
  expected_contribution: Money;
  lines: PlanLine[];
}

export interface Simulation {
  budget: Money;
  sell_through: Money;
  salvage: Money;
  max_share_per_sku: Money;
  base: { plan_a: Plan; plan_b: Plan };
  conservative: { plan_a: Plan; plan_b: Plan };
  /** The uniform-shock limitation from `plans/BUSINESS_RULES.md` §11.3, verbatim. */
  disclosure: string;
}

/**
 * The what-if over one batch of units from `POST /api/v1/simulate/sku`. Every figure is
 * calculated by the backend from the terms and the active assumptions below; nothing here
 * is derived in the browser, and `inputs` echoes the terms that were actually used.
 */
export interface SkuSimulation {
  units: number;
  returned_units: number;
  inputs: {
    price: Money;
    landed_unit_cost: Money;
    referral_rate: Money;
    closing_fee: Money;
    returns_rate: Money;
    ads_per_unit: Money;
  };
  assumptions: Assumptions;
  line: BreakdownLine;
  /** What this figure is and is not, from `plans/BUSINESS_RULES.md` §4, verbatim. */
  basis: string;
}

/** The uniform failure body the backend returns for every 4xx and 5xx (AT-8.10). */
export interface ApiErrorBody {
  error: string;
  detail: string;
  field?: string;
}
