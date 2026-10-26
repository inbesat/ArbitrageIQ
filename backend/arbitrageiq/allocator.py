"""Budget Lab allocator: two transparent greedy heuristics (task T11).

Source of truth:

- ``plans/BUSINESS_RULES.md`` §11.2 — ``expected_profit(qty)``.
- ``plans/BUSINESS_RULES.md`` §11.3 / ADR-019 — the two scenarios.
- ``plans/BUSINESS_RULES.md`` §11.4 / ADR-016 / ADR-017 — the two strategies and
  the single shared score.
- ``plans/BUSINESS_RULES.md`` §11.5 — invariants B1-B10, enforced by
  :func:`check_invariants` before anything is returned.
- ``plans/ARCHITECTURE.md`` §4.3 — the flow, and the rule that an invariant
  breach must fail loudly rather than reach the user.

**Neither strategy is optimal and neither is a forecast** (ADR-016). Both rank by
one score and fill greedily. Because §11.2 is linear in ``qty`` and
``sell_through`` is a fraction, the score is *constant* in ``qty`` — so "greedy,
descending score" means the SKUs are ordered by their per-rupee rate and each is
filled to the smaller of its supply cap and what the budget still affords.

**No money arithmetic is re-implemented here.** ``per_sold_unit`` comes from the
steady-state single-unit line of ``profit.compute_line``, which keeps §7's
``fee_gst_recoverable`` switch and every fee rule authoritative. The budget is
compared in **integer paise** (B10), so a rounding edge cannot overspend.

This module imports ``money``, ``config`` and ``profit`` only — never ``db`` or
``api`` (``plans/ARCHITECTURE.md`` §3). It is pure: it persists nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from arbitrageiq.config import FeeAssumptions
from arbitrageiq.money import round_half_up
from arbitrageiq.profit import LineInput, compute_line

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HALF = Decimal("0.5")
_PAISE = Decimal("100")


@dataclass(frozen=True)
class Scenario:
    """A stress setting from ``BUSINESS_RULES.md`` §11.3."""

    name: str
    price_shock: Decimal
    sellthrough_shock: Decimal


#: §11.3's two scenarios. Conservative recomputes fees at the lower price.
BASE = Scenario("base", Decimal("1.00"), Decimal("1.00"))
CONSERVATIVE = Scenario("conservative", Decimal("0.95"), Decimal("0.75"))

PLAN_A = ("roi_first", "Plan A - ROI-first")
PLAN_B = ("diversified_cap", "Plan B - Diversified cap")


@dataclass(frozen=True)
class Candidate:
    """One catalogue row the allocator may spend on."""

    sku: str
    price: Decimal
    landed_unit_cost: Decimal
    min_order_qty: int
    max_supply: int


@dataclass(frozen=True)
class PlanLine:
    """One SKU inside a plan. ``assumed`` marks the sell-through/salvage dependence."""

    sku: str
    qty: int
    capital: Decimal
    expected_contribution: Decimal
    score: Decimal
    assumed: bool = True


@dataclass(frozen=True)
class Plan:
    """A whole plan: every candidate, in allocation order, including the zeros."""

    strategy: str
    label: str
    lines: tuple[PlanLine, ...]
    capital_used: Decimal
    budget_remaining: Decimal
    expected_contribution: Decimal


@dataclass(frozen=True)
class Allocation:
    """Both plans under the base scenario, and both under the conservative one."""

    base: tuple[Plan, Plan]
    conservative: tuple[Plan, Plan]


def _paise(amount: Decimal) -> int:
    """Money as integer paise, floored — the basis of B10's exact comparison."""
    return int((amount * _PAISE).to_integral_value(rounding=ROUND_DOWN))


def per_sold_unit(
    candidate: Candidate, assumptions: FeeAssumptions, *, price: Decimal | None = None
) -> Decimal:
    """§11.2's ``per_sold_unit``: ex-GST revenue per sold unit, before product cost.

    Derived from ``profit.compute_line``'s steady-state single-unit line, so the
    fee model, the referral floor and §7's ``fee_gst_recoverable`` switch all stay
    in one place. ``price`` defaults to the candidate's catalogue price.
    """
    effective = candidate.price if price is None else price
    line = LineInput(
        sku=candidate.sku,
        units_sold=1,
        returned_units=0,
        selling_price=effective,
        landed_unit_cost=candidate.landed_unit_cost,
    )
    return compute_line(line, assumptions).contribution + candidate.landed_unit_cost


def expected_profit(
    candidate: Candidate,
    assumptions: FeeAssumptions,
    *,
    qty: int,
    sell_through: Decimal,
    salvage: Decimal,
    scenario: Scenario = BASE,
) -> Decimal:
    """§11.2: ``sold * per_sold_unit - qty * L + unsold * salvage * L``.

    ``min(1, sell_through)`` caps the fraction at one. Rounding happens once, at
    the end of the calculation.
    """
    price = candidate.price * scenario.price_shock
    share = min(_ONE, sell_through * scenario.sellthrough_shock)
    landed = candidate.landed_unit_cost
    unit = per_sold_unit(candidate, assumptions, price=price)
    quantity = Decimal(qty)
    sold = share * quantity
    unsold = quantity - sold
    return round_half_up(sold * unit - quantity * landed + unsold * salvage * landed)


def expected_profit_per_unit(
    candidate: Candidate,
    assumptions: FeeAssumptions,
    *,
    sell_through: Decimal,
    salvage: Decimal,
) -> Decimal:
    """What buying **one** unit is expected to earn — the SKU's per-unit economics.

    This is the quantity B8 means: a SKU whose per-unit economics are not positive
    can only drag a plan down, so it is never bought. ``per_sold_unit`` alone is
    not enough — it excludes the landed cost, so a SKU can show a positive
    ``per_sold_unit`` and still lose money on every unit.
    """
    return expected_profit(
        candidate, assumptions, qty=1, sell_through=sell_through, salvage=salvage
    )


def score(
    candidate: Candidate,
    assumptions: FeeAssumptions,
    *,
    qty: int,
    sell_through: Decimal,
    salvage: Decimal,
) -> Decimal:
    """ADR-017: the base/conservative blend per rupee of capital.

    The ``qty`` argument makes this the literal §11.4 formula; because every term
    is linear in ``qty`` it cancels, so the value does not depend on it.
    """
    risk_adjusted = _HALF * expected_profit(
        candidate, assumptions, qty=qty, sell_through=sell_through, salvage=salvage
    ) + _HALF * expected_profit(
        candidate,
        assumptions,
        qty=qty,
        sell_through=sell_through,
        salvage=salvage,
        scenario=CONSERVATIVE,
    )
    denominator = Decimal(qty) * candidate.landed_unit_cost
    if denominator <= _ZERO:
        # B6: a zero denominator must render a finite number, never a crash.
        return _ZERO
    return risk_adjusted / denominator


def _build(
    strategy: tuple[str, str],
    ordered: Sequence[Candidate],
    assumptions: FeeAssumptions,
    *,
    budget: Decimal,
    budget_paise: int,
    cap_paise: int | None,
    sell_through: Decimal,
    salvage: Decimal,
    scenario: Scenario,
) -> Plan:
    """Greedy fill in the given order, reporting ``scenario``'s contribution."""
    remaining = budget_paise
    lines: list[PlanLine] = []
    for candidate in ordered:
        unit_paise = _paise(candidate.landed_unit_cost)
        qty = 0
        # B8: a SKU whose base-case per-unit economics are not positive is never
        # bought. BUSINESS_RULES names Plan A; buying a money-loser is wrong in
        # both plans, so the filter is applied to each (recorded as a deviation).
        if (
            expected_profit_per_unit(
                candidate, assumptions, sell_through=sell_through, salvage=salvage
            )
            > _ZERO
        ):
            limit = remaining if cap_paise is None else min(remaining, cap_paise)
            affordable = candidate.max_supply if unit_paise == 0 else limit // unit_paise
            qty = min(candidate.max_supply, affordable)
            # B3: below the minimum order quantity the SKU is not bought at all.
            if qty < candidate.min_order_qty:
                qty = 0
            if qty > 0:
                remaining -= qty * unit_paise
        lines.append(
            PlanLine(
                sku=candidate.sku,
                qty=qty,
                capital=candidate.landed_unit_cost * qty,
                expected_contribution=expected_profit(
                    candidate,
                    assumptions,
                    qty=qty,
                    sell_through=sell_through,
                    salvage=salvage,
                    scenario=scenario,
                ),
                score=score(
                    candidate,
                    assumptions,
                    qty=1,
                    sell_through=sell_through,
                    salvage=salvage,
                ),
            )
        )

    capital_used = round_half_up(sum((line.capital for line in lines), _ZERO))
    return Plan(
        strategy=strategy[0],
        label=strategy[1],
        lines=tuple(lines),
        capital_used=capital_used,
        budget_remaining=round_half_up(budget - capital_used),
        expected_contribution=round_half_up(
            sum((line.expected_contribution for line in lines), _ZERO)
        ),
    )


def check_invariants(
    plan: Plan,
    *,
    budget: Decimal,
    candidates: Sequence[Candidate],
    max_share_per_sku: Decimal | None = None,
) -> None:
    """Enforce B1-B6 and B10 on one plan; raise ``ValueError`` on any breach.

    ``plans/ARCHITECTURE.md`` §4.3 puts this at the boundary on purpose: a plan
    that overspends or breaches an MOQ must fail loudly rather than reach the
    user, so T12 maps this to a 500 and never to a plausible-looking result.
    """
    by_sku = {candidate.sku: candidate for candidate in candidates}
    budget_paise = _paise(budget)
    cap_paise = None if max_share_per_sku is None else _paise(max_share_per_sku * budget)
    total = 0

    for line in plan.lines:
        candidate = by_sku.get(line.sku)
        if candidate is None:
            raise ValueError(f"B2: plan line {line.sku!r} matches no candidate")
        if type(line.qty) is not int:
            raise ValueError(f"B2: {line.sku} qty is {type(line.qty).__name__}, not int")
        if line.qty < 0:
            raise ValueError(f"B2: {line.sku} qty is negative")
        if line.qty != 0 and line.qty < candidate.min_order_qty:
            raise ValueError(f"B3: {line.sku} qty {line.qty} is below its minimum order quantity")
        if line.qty > candidate.max_supply:
            raise ValueError(f"B4: {line.sku} qty {line.qty} exceeds its supply cap")
        for name, value in (
            ("capital", line.capital),
            ("expected_contribution", line.expected_contribution),
            ("score", line.score),
        ):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f"B6: {line.sku} {name} is not a finite Decimal: {value!r}")
        line_paise = _paise(line.capital)
        if line_paise != _paise(candidate.landed_unit_cost) * line.qty:
            raise ValueError(f"B1: {line.sku} capital {line.capital} is not qty x landed cost")
        if cap_paise is not None and line_paise > cap_paise:
            raise ValueError(f"B5: {line.sku} capital {line.capital} exceeds the per-SKU cap")
        total += line_paise

    for name, value in (
        ("capital_used", plan.capital_used),
        ("budget_remaining", plan.budget_remaining),
        ("expected_contribution", plan.expected_contribution),
    ):
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError(f"B6: plan {name} is not a finite Decimal: {value!r}")

    if total > budget_paise:
        raise ValueError(f"B10: spend {plan.capital_used} exceeds the budget {budget}")
    if _paise(plan.capital_used) != total:
        raise ValueError(f"B1: capital_used {plan.capital_used} is not the summed line capital")
    if _paise(plan.capital_used) + _paise(plan.budget_remaining) != budget_paise:
        raise ValueError(
            f"B1: capital_used {plan.capital_used} + budget_remaining "
            f"{plan.budget_remaining} does not equal the budget {budget}"
        )


def allocate(
    candidates: Sequence[Candidate],
    assumptions: FeeAssumptions,
    *,
    budget: Decimal,
    sell_through: Decimal,
    salvage: Decimal,
    max_share_per_sku: Decimal,
) -> Allocation:
    """Run both strategies under both scenarios and enforce every invariant.

    Inputs are expected to be validated at the API boundary (T12); this function
    re-checks only the two things it cannot work without.
    """
    if budget < _ZERO:
        raise ValueError(f"budget must be >= 0, got {budget}")
    if not _ZERO < max_share_per_sku <= _ONE:
        raise ValueError(f"max_share_per_sku must be in (0, 1], got {max_share_per_sku}")

    ordered = sorted(
        candidates,
        key=lambda candidate: (
            -score(
                candidate,
                assumptions,
                qty=1,
                sell_through=sell_through,
                salvage=salvage,
            ),
            candidate.sku,
        ),
    )
    budget_paise = _paise(budget)
    cap_paise = _paise(max_share_per_sku * budget)

    base = (
        _build(
            PLAN_A,
            ordered,
            assumptions,
            budget=budget,
            budget_paise=budget_paise,
            cap_paise=None,
            sell_through=sell_through,
            salvage=salvage,
            scenario=BASE,
        ),
        _build(
            PLAN_B,
            ordered,
            assumptions,
            budget=budget,
            budget_paise=budget_paise,
            cap_paise=cap_paise,
            sell_through=sell_through,
            salvage=salvage,
            scenario=BASE,
        ),
    )
    conservative = (
        _build(
            PLAN_A,
            ordered,
            assumptions,
            budget=budget,
            budget_paise=budget_paise,
            cap_paise=None,
            sell_through=sell_through,
            salvage=salvage,
            scenario=CONSERVATIVE,
        ),
        _build(
            PLAN_B,
            ordered,
            assumptions,
            budget=budget,
            budget_paise=budget_paise,
            cap_paise=cap_paise,
            sell_through=sell_through,
            salvage=salvage,
            scenario=CONSERVATIVE,
        ),
    )

    # §4.3: assert B1-B10 before returning; a breach is a bug, never a silent plan.
    check_invariants(base[0], budget=budget, candidates=candidates)
    check_invariants(
        base[1], budget=budget, candidates=candidates, max_share_per_sku=max_share_per_sku
    )
    check_invariants(conservative[0], budget=budget, candidates=candidates)
    check_invariants(
        conservative[1], budget=budget, candidates=candidates, max_share_per_sku=max_share_per_sku
    )
    return Allocation(base=base, conservative=conservative)
