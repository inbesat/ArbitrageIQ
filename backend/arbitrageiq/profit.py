"""Contribution engine: the per-transaction calculation (task T04).

Source of truth for the rules implemented here:
- ``plans/BUSINESS_RULES.md`` §4 — the per-transaction calculation, in exact order.
  Rounding happens once per line, half-up, at the end (step 12).
- ``plans/BUSINESS_RULES.md`` §5 — the fee model, used only when
  ``settlement_fees_total`` is absent.
- ``plans/BUSINESS_RULES.md`` §6 — rules S1-S3: a settlement total REPLACES the
  modelled fees and is never added to them.
- ``plans/BUSINESS_RULES.md`` §7 — TCS and TDS are cash-flow credits, never costs,
  so they are deliberately absent from every subtraction below.
- ``plans/BUSINESS_RULES.md`` §8 — the derived metrics and their zero-denominator
  ``"n/a"`` rule.
- ``plans/ACCEPTANCE_TESTS.md`` AT-1, AT-2.4, AT-3 — the expected values asserted by
  ``backend/tests/test_profit.py``.

``business_rules`` §3's GROSS/NET TRAP: ``units_sold`` is GROSS units shipped,
including the returned units. Revenue is earned on the net units, but product cost
and marketplace fees are modelled on the gross units (ADR-008, fee rule F1).

Rounding and the ``"n/a"`` ratio rule come from ``money.py``; this module does not
re-implement either. Import set is restricted by ``plans/ARCHITECTURE.md`` §3 to
``money`` and ``config`` plus the standard library.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from arbitrageiq.config import FeeAssumptions
from arbitrageiq.money import ratio, round_half_up

#: Fraction of landed cost recovered on a returned unit. Fixed at 0 in the MVP,
#: meaning a returned unit is written off (``business_rules`` §4). Named so a future
#: version can expose it; not a P0 slider.
RESALE_FRACTION = Decimal("0")

#: Which fee path produced the line, so a caller can see the §6 override fired.
FEE_SOURCE_MODEL = "model"
FEE_SOURCE_SETTLEMENT = "settlement"

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


@dataclass(frozen=True)
class LineInput:
    """One transaction row plus the landed unit cost of its product.

    ``selling_price`` and ``refund_per_returned_unit`` are GST-inclusive, as
    entered (``business_rules`` §3). ``units_sold`` is GROSS.
    """

    sku: str
    units_sold: int
    returned_units: int
    selling_price: Decimal
    landed_unit_cost: Decimal
    discount_per_unit: Decimal = _ZERO
    refund_per_returned_unit: Decimal | None = None
    ads_cost: Decimal = _ZERO
    other_charges: Decimal = _ZERO
    settlement_fees_total: Decimal | None = None
    transaction_id: str | None = None


@dataclass(frozen=True)
class LineBreakdown:
    """The full per-line breakdown, so a reconciliation can be read line by line."""

    sku: str
    transaction_id: str | None
    price_paid: Decimal
    ex_gst_unit_price: Decimal
    net_units: int
    gross_revenue: Decimal
    refunds: Decimal
    net_revenue: Decimal
    referral_fee: Decimal
    fees_ex_gst: Decimal
    fee_gst: Decimal
    product_cost: Decimal
    ads: Decimal
    other_charges: Decimal
    contribution: Decimal
    fee_source: str
    profit_per_unit: Decimal | str
    margin_pct: Decimal | str
    roi_pct: Decimal | str


def _fee_components(
    line: LineInput, assumptions: FeeAssumptions, price_paid: Decimal
) -> tuple[Decimal, Decimal, Decimal, str]:
    """Return ``(referral, fees_ex_gst, fee_gst, source)`` per §5, or §6 if settled."""
    if line.settlement_fees_total is not None:
        # Rule S1: the settlement figure REPLACES the model. Rule S2: it is
        # GST-inclusive, so split it rather than adding it to modelled fees.
        fees_ex_gst = round_half_up(
            line.settlement_fees_total / (_ONE + assumptions.gst_on_fees_rate)
        )
        fee_gst = round_half_up(line.settlement_fees_total - fees_ex_gst)
        return _ZERO, fees_ex_gst, fee_gst, FEE_SOURCE_SETTLEMENT

    # Rule F3: the floor is applied to p before the rate multiplication.
    referral = (
        price_paid * assumptions.referral_rate
        if price_paid >= assumptions.zero_referral_below
        else _ZERO
    )
    per_unit = (
        referral + assumptions.closing_fee + assumptions.shipping_fee + assumptions.fulfilment_fee
    )
    # Rule F1: fees are charged on GROSS units shipped, not net units.
    fees_ex_gst = round_half_up(per_unit * line.units_sold)
    # Rule F4: GST on fees is computed on the whole ex-GST fee, never per component.
    fee_gst = round_half_up(fees_ex_gst * assumptions.gst_on_fees_rate)
    return referral, fees_ex_gst, fee_gst, FEE_SOURCE_MODEL


def compute_line(line: LineInput, assumptions: FeeAssumptions) -> LineBreakdown:
    """Compute one transaction line, in the exact order of ``business_rules`` §4."""
    # 1. GST-inclusive price actually paid per unit.
    price_paid = line.selling_price - line.discount_per_unit

    # 2. Ex-GST price per unit.
    ex_gst = round_half_up(price_paid / (_ONE + assumptions.product_gst_rate))

    # 3. Refunded unit's ex-GST revenue; defaults to e when no refund is entered.
    if line.refund_per_returned_unit is None:
        ex_gst_refund = ex_gst
    else:
        ex_gst_refund = round_half_up(
            line.refund_per_returned_unit / (_ONE + assumptions.product_gst_rate)
        )

    # 4-6. Revenue is earned on the gross units, less the refunded units.
    gross_revenue = round_half_up(ex_gst * line.units_sold)
    refunds = round_half_up(ex_gst_refund * line.returned_units)
    net_revenue = round_half_up(gross_revenue - refunds)

    # 7. Fees, from the settlement override (§6) or the model (§5).
    referral, fees_ex_gst, fee_gst, fee_source = _fee_components(line, assumptions, price_paid)

    # 8. Product cost is written off on the gross units; resale recovery is 0.
    product_cost = round_half_up(
        line.landed_unit_cost * line.units_sold
        - RESALE_FRACTION * line.landed_unit_cost * line.returned_units
    )

    # 9-10. Advertising and any other charge are whole-line, not per unit.
    ads = line.ads_cost
    other = line.other_charges

    # 11. Contribution: GST on fees is dropped only when it is recoverable (§7 layer 2).
    # TCS and TDS are deliberately absent here — they are credits, never costs.
    contribution = (
        net_revenue
        - product_cost
        - fees_ex_gst
        - (_ZERO if assumptions.fee_gst_recoverable else fee_gst)
        - ads
        - other
    )

    # 12. Round HALF-UP, once, at the end of the line.
    contribution = round_half_up(contribution)

    net_units = line.units_sold - line.returned_units
    roi_denominator = line.landed_unit_cost * line.units_sold

    return LineBreakdown(
        sku=line.sku,
        transaction_id=line.transaction_id,
        price_paid=price_paid,
        ex_gst_unit_price=ex_gst,
        net_units=net_units,
        gross_revenue=gross_revenue,
        refunds=refunds,
        net_revenue=net_revenue,
        referral_fee=referral,
        fees_ex_gst=fees_ex_gst,
        fee_gst=fee_gst,
        product_cost=product_cost,
        ads=ads,
        other_charges=other,
        contribution=contribution,
        fee_source=fee_source,
        # §8: each ratio renders the literal "n/a" on a zero denominator.
        profit_per_unit=ratio(contribution, Decimal(net_units)),
        margin_pct=ratio(contribution, net_revenue, percent=True),
        roi_pct=ratio(contribution, roi_denominator, percent=True),
    )


# --- Unit economics (§8): the two solved prices -------------------------------
#
# §8 solves both prices on the STEADY-STATE SINGLE-UNIT case: one unit shipped, no
# returns, no ads, no other charges, no settlement figure. Each is a pricing floor,
# never a recommendation and never a forecast, and the returned record says so.
#
# The objective is PIECEWISE, not monotonic. The referral fee is charged only when
# p >= zero_referral_below, so crossing that floor makes contribution DROP (at the
# §10.1 assumptions: 241.25 at 999.99, then 146.86 at 1000.00). A solver must not
# binary-search the whole domain. It solves the no-referral branch, and only if
# that branch cannot answer does it walk up the referral branch, which is monotone.

_CENT = Decimal("0.01")
PRICE_FLOOR_BASIS = (
    "steady state, single unit, no returns, no ads - a pricing floor, not a forecast"
)
_BRANCH_TWO_WALK_LIMIT = 200_000


@dataclass(frozen=True)
class PriceFloor:
    """A solved steady-state price: a pricing floor, never a recommendation."""

    price: Decimal
    target_margin: Decimal | None = None
    steady_state: bool = True
    basis: str = PRICE_FLOOR_BASIS


def _steady_state_line(price: Decimal, landed_unit_cost: Decimal) -> LineInput:
    """§8's steady-state single-unit case, expressed as an ordinary line input."""
    return LineInput(
        sku="STEADY-STATE",
        units_sold=1,
        returned_units=0,
        selling_price=price,
        landed_unit_cost=landed_unit_cost,
    )


def _needed_ex_gst_price(
    target_margin: Decimal | None, assumptions: FeeAssumptions, landed_unit_cost: Decimal
) -> Decimal:
    """The ex-GST unit price required, on the no-referral branch, before rounding."""
    fixed_fees = assumptions.closing_fee + assumptions.shipping_fee + assumptions.fulfilment_fee
    fee_gst = (
        _ZERO if assumptions.fee_gst_recoverable else fixed_fees * assumptions.gst_on_fees_rate
    )
    needed = landed_unit_cost + fixed_fees + fee_gst
    if target_margin is None:
        return needed
    # contribution / e >= m  =>  e >= needed / (1 - m)
    return needed / (_ONE - target_margin)


def _solve_price(
    assumptions: FeeAssumptions, landed_unit_cost: Decimal, target_margin: Decimal | None
) -> Decimal:
    """Smallest 2-dp price satisfying the §8 condition, solved per branch."""
    if target_margin is not None and not _ZERO <= target_margin < _ONE:
        raise ValueError(f"target_margin must be in [0, 1), got {target_margin}")

    def holds(price: Decimal) -> bool:
        if price <= _ZERO:
            return False
        breakdown = compute_line(_steady_state_line(price, landed_unit_cost), assumptions)
        if target_margin is None:
            return breakdown.contribution >= _ZERO
        # AT-4.3: judged on the EXACT quotient, because the 2-dp display field reads
        # 20.00 on both sides of the boundary below.
        return breakdown.contribution / breakdown.ex_gst_unit_price >= target_margin

    needed_e = _needed_ex_gst_price(target_margin, assumptions, landed_unit_cost)
    gross_rate = _ONE + assumptions.product_gst_rate
    # Ceiling to the cent overshoots the true boundary by at most one cent, so the
    # walk-down below is bounded in practice.
    candidate = (needed_e * gross_rate / _CENT).to_integral_value(rounding=ROUND_CEILING) * _CENT

    if candidate < assumptions.zero_referral_below and holds(candidate):
        while candidate - _CENT > _ZERO and holds(candidate - _CENT):
            candidate -= _CENT
        return candidate

    # The answer sits at or above the referral floor, where contribution rises.
    candidate = assumptions.zero_referral_below
    for _ in range(_BRANCH_TWO_WALK_LIMIT):
        if holds(candidate):
            return candidate
        candidate += _CENT
    raise ValueError(
        f"no price up to {candidate} satisfies the §8 condition for this assumption set"
    )


def break_even_price(assumptions: FeeAssumptions, landed_unit_cost: Decimal) -> PriceFloor:
    """§8 break-even: the smallest steady-state price whose contribution is >= 0."""
    return PriceFloor(price=_solve_price(assumptions, landed_unit_cost, None))


def minimum_price_for_target_margin(
    assumptions: FeeAssumptions, landed_unit_cost: Decimal, margin: Decimal
) -> PriceFloor:
    """§8: the smallest steady-state price whose contribution / e >= ``margin``."""
    return PriceFloor(
        price=_solve_price(assumptions, landed_unit_cost, margin), target_margin=margin
    )
