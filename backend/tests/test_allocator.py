"""T11 acceptance tests: the Budget Lab allocator (`plans/ACCEPTANCE_TESTS.md` AT-7).

Every expected value below is derived from `plans/BUSINESS_RULES.md` §11 or
hand-computed from it — never from the allocator under test. The one numeric
expectation (`expected_profit` for the DIYA-SET-12 row) is worked through by hand
in the test body.

Owned rows: **AT-7.1–7.10, AT-7.13, AT-7.15.**
**Not claimed here** — T12 owns them: AT-7.11 (`sell_through` 0.4), AT-7.12
(`salvage` 0), AT-7.14 (conservative strictly worse than base) and AT-8.9
(`POST /budget/simulate`).

The sample catalogue is read from `data/sample/products_sample.csv` rather than
duplicated here, so AT-7.2/7.3/7.9 test the real fixture. AT-7.9's "very few
SKUs" bound is therefore tied to that catalogue and must be revisited if the
sample changes.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, replace
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pytest

from arbitrageiq.allocator import (
    CONSERVATIVE,
    Allocation,
    Candidate,
    Plan,
    PlanLine,
    allocate,
    check_invariants,
    expected_profit,
    expected_profit_per_unit,
    per_sold_unit,
    score,
)
from arbitrageiq.config import FeeAssumptions

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CATALOGUE = PROJECT_ROOT / "data" / "sample" / "products_sample.csv"

#: The §2 defaults: sell_through 0.80, salvage 0.50, cap 0.40 (BUSINESS_RULES §2).
ASSUMPTIONS = FeeAssumptions()
SELL_THROUGH = ASSUMPTIONS.default_sell_through
SALVAGE = ASSUMPTIONS.default_salvage
CAP = ASSUMPTIONS.default_max_share_per_sku

BUDGET_50K = Decimal("50000.00")
BUDGET_3K = Decimal("3000.00")
BUDGET_500 = Decimal("500.00")

#: §11.4's banned plan claims, plus the §11.4 list's full form (AT-7.15 asserts
#: the union so a future wording cannot slip through).
BANNED_CLAIMS = ("optimal", "best", "maximis", "guaranteed", "predicted sale")


def _paise(amount: Decimal) -> int:
    """Money as integer paise, floored (BUSINESS_RULES §11.5 — B10's basis)."""
    return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_DOWN))


def _sample_candidates() -> list[Candidate]:
    """The sample catalogue as allocator inputs; landed cost is supplier+inbound+packaging."""
    lines = SAMPLE_CATALOGUE.read_text(encoding="utf-8").splitlines()
    return [
        Candidate(
            sku=row["sku"],
            price=Decimal(row["target_price"]),
            landed_unit_cost=(
                Decimal(row["supplier_unit_cost"])
                + Decimal(row["inbound_unit_cost"])
                + Decimal(row["packaging_unit_cost"])
            ),
            min_order_qty=int(row["min_order_qty"]),
            max_supply=int(row["max_supply"]),
        )
        for row in csv.DictReader(lines)
    ]


def _candidate(sku: str) -> Candidate:
    return next(item for item in _sample_candidates() if item.sku == sku)


def _run(candidates, budget, *, max_share_per_sku=CAP) -> Allocation:
    return allocate(
        candidates,
        ASSUMPTIONS,
        budget=budget,
        sell_through=SELL_THROUGH,
        salvage=SALVAGE,
        max_share_per_sku=max_share_per_sku,
    )


def _serialise(allocation: Allocation) -> str:
    """A canonical, deterministic rendering of the whole result."""
    return json.dumps(asdict(allocation), default=str, sort_keys=True)


def _funded(plan: Plan) -> list[PlanLine]:
    return [line for line in plan.lines if line.qty > 0]


def _assert_b1_to_b4_b6(plan: Plan, candidates, budget: Decimal) -> None:
    by_sku = {item.sku: item for item in candidates}
    total = 0
    for line in plan.lines:
        assert type(line.qty) is int, f"B2: {line.sku} qty is not an int"  # AT-7.5
        assert line.qty >= 0, f"B2: {line.sku} qty is negative"  # AT-7.5
        candidate = by_sku[line.sku]
        if line.qty != 0:
            assert line.qty >= candidate.min_order_qty, f"B3: {line.sku}"  # AT-7.6
        assert line.qty <= candidate.max_supply, f"B4: {line.sku}"  # AT-7.7
        for value in (line.capital, line.expected_contribution, line.score):
            assert isinstance(value, Decimal) and value.is_finite(), f"B6: {line.sku}"  # B6
        assert _paise(line.capital) == _paise(candidate.landed_unit_cost) * line.qty, (
            f"B1: {line.sku} capital is not qty x landed cost"
        )
        total += _paise(line.capital)
    assert total <= _paise(budget), f"B1: spend {total} paise exceeds budget"  # AT-7.4
    assert _paise(plan.capital_used) == total, "B1: capital_used != summed line capital"
    assert isinstance(plan.budget_remaining, Decimal) and plan.budget_remaining.is_finite()
    assert isinstance(plan.expected_contribution, Decimal)
    assert plan.expected_contribution.is_finite()  # B6


# --- AT-7.2 ------------------------------------------------------------------


def test_at_7_2_budget_500_on_the_sample_catalogue_buys_nothing():
    allocation = _run(_sample_candidates(), BUDGET_500)

    for plan in (*allocation.base, *allocation.conservative):
        assert all(line.qty == 0 for line in plan.lines), plan.label
        assert plan.capital_used == Decimal("0.00")
        assert plan.expected_contribution == Decimal("0.00")


# --- AT-7.3 ------------------------------------------------------------------


def test_at_7_3_budget_3000_is_non_empty_within_budget_and_smaller_than_50k():
    candidates = _sample_candidates()
    small = _run(candidates, BUDGET_3K).base[0]
    large = _run(candidates, BUDGET_50K).base[0]

    assert _funded(small), "a Rs 3,000 budget must buy something from this catalogue"
    assert _paise(small.capital_used) <= _paise(BUDGET_3K)
    assert _paise(small.capital_used) < _paise(large.capital_used)
    assert sum(line.qty for line in small.lines) < sum(line.qty for line in large.lines)
    # Per-SKU monotonicity is deliberately NOT asserted. A greedy fill in
    # descending score can reach a lower-ranked SKU under a small budget and skip
    # it under a large one: on this catalogue the Rs 3,000 plan funds DIYA-SET-12
    # while the Rs 50,000 plan never reaches it, because TIFFIN-3 exhausts the
    # budget first.


# --- AT-7.4 / AT-7.5 / AT-7.6 / AT-7.7 ---------------------------------------


def test_at_7_4_spend_never_exceeds_budget_in_integer_paise():
    candidates = _sample_candidates()
    for budget in (BUDGET_500, Decimal("1000.00"), BUDGET_3K, Decimal("12345.67"), BUDGET_50K):
        for plan in _run(candidates, budget).base:
            assert _paise(plan.capital_used) <= _paise(budget), plan.label
            assert _paise(plan.capital_used) + _paise(plan.budget_remaining) == _paise(budget)


def test_at_7_5_all_quantities_are_integers():
    candidates = _sample_candidates()
    for plan in _run(candidates, BUDGET_50K).base:
        for line in plan.lines:
            assert type(line.qty) is int, f"{line.sku} qty is {type(line.qty).__name__}"


def test_at_7_6_every_non_zero_quantity_meets_min_order_qty():
    candidates = _sample_candidates()
    for plan in _run(candidates, BUDGET_50K).base:
        for line in _funded(plan):
            candidate = next(item for item in candidates if item.sku == line.sku)
            assert line.qty >= candidate.min_order_qty, f"{line.sku} is below MOQ"


def test_at_7_7_every_quantity_is_within_max_supply():
    candidates = _sample_candidates()
    for budget in (BUDGET_3K, BUDGET_50K, Decimal("500000.00")):
        for plan in _run(candidates, budget).base:
            for line in plan.lines:
                candidate = next(item for item in candidates if item.sku == line.sku)
                assert line.qty <= candidate.max_supply, f"{line.sku} exceeds max_supply"


# --- AT-7.8 ------------------------------------------------------------------


def test_at_7_8_plan_b_never_spends_more_than_the_per_sku_cap():
    candidates = _sample_candidates()
    cap_paise = _paise(CAP * BUDGET_50K)

    plan_b = _run(candidates, BUDGET_50K).base[1]

    assert _funded(plan_b), "Plan B must buy something at Rs 50,000"
    for line in plan_b.lines:
        assert _paise(line.capital) <= cap_paise, f"{line.sku} breaches the 40% cap"


def test_at_7_8_plan_a_has_no_cap_and_may_exceed_it():
    """The cap is Plan B's only; this pins that the two plans really differ."""
    candidates = _sample_candidates()
    cap_paise = _paise(CAP * BUDGET_50K)

    plan_a = _run(candidates, BUDGET_50K).base[0]

    top = max((_paise(line.capital) for line in plan_a.lines), default=0)
    assert top > cap_paise, "Plan A unexpectedly stayed inside Plan B's cap"


# --- AT-7.9 ------------------------------------------------------------------


def test_at_7_9_plan_a_concentrates_into_fewer_skus_than_plan_b():
    plan_a, plan_b = _run(_sample_candidates(), BUDGET_50K).base

    funded_a = _funded(plan_a)
    funded_b = _funded(plan_b)

    assert funded_a, "Plan A must buy something at Rs 50,000"
    assert len(funded_a) <= len(funded_b), "Plan A must be at least as concentrated as Plan B"
    # "Very few", against this catalogue (AT-7.9 names the sample catalogue).
    assert len(funded_a) <= 3, f"Plan A spread over {len(funded_a)} SKUs"
    # Concentration is reported, not hidden: every line carries its quantity and capital.
    for line in funded_a:
        assert line.qty > 0 and _paise(line.capital) > 0


# --- AT-7.10 -----------------------------------------------------------------


def test_at_7_10_two_runs_are_byte_identical():
    candidates = _sample_candidates()

    first = _serialise(_run(candidates, BUDGET_50K))
    second = _serialise(_run(candidates, BUDGET_50K))

    assert first.encode("utf-8") == second.encode("utf-8")


# --- AT-7.13 -----------------------------------------------------------------


def test_at_7_13_a_sku_with_negative_per_unit_economics_gets_zero_in_plan_a():
    # EARBUD-BT-1 is the sample catalogue's loss-maker: price 1,150 against a
    # 1,002.00 landed cost leaves per_sold_unit well below the landed cost.
    loss_maker = _candidate("EARBUD-BT-1")
    winner = _candidate("TORAN-FLW-1")

    plan_a = allocate(
        [loss_maker, winner],
        ASSUMPTIONS,
        budget=BUDGET_50K,
        sell_through=SELL_THROUGH,
        salvage=SALVAGE,
        max_share_per_sku=CAP,
    ).base[0]

    qty = {line.sku: line.qty for line in plan_a.lines}
    assert qty["EARBUD-BT-1"] == 0, "B8: a loss-maker received a positive quantity"
    assert qty["TORAN-FLW-1"] > 0, "the profitable SKU was not funded"


def test_at_7_13_plan_b_also_refuses_the_loss_maker():
    loss_maker = _candidate("EARBUD-BT-1")
    winner = _candidate("TORAN-FLW-1")

    plan_b = allocate(
        [loss_maker, winner],
        ASSUMPTIONS,
        budget=BUDGET_50K,
        sell_through=SELL_THROUGH,
        salvage=SALVAGE,
        max_share_per_sku=CAP,
    ).base[1]

    qty = {line.sku: line.qty for line in plan_b.lines}
    assert qty["EARBUD-BT-1"] == 0


# --- AT-7.15 -----------------------------------------------------------------


def test_at_7_15_no_banned_plan_claim_appears_in_the_payload_or_labels():
    allocation = _run(_sample_candidates(), BUDGET_50K)

    payload = _serialise(allocation).lower()

    for banned in BANNED_CLAIMS:
        assert banned not in payload, f"the payload claims {banned!r}"
    for plan in (*allocation.base, *allocation.conservative):
        assert plan.label and plan.strategy


# --- AT-7.1 — the randomised invariant sweep ---------------------------------


def _random_catalogue(rng: random.Random) -> list[Candidate]:
    """A valid random catalogue, always containing at least one loss-maker."""
    candidates = []
    for index in range(rng.randint(5, 12)):
        landed = (Decimal(rng.randrange(100, 500_001)) / Decimal("100")).quantize(Decimal("0.01"))
        price = ((landed * rng.choice((1, 2, 3, 4))) / Decimal(rng.choice((1, 2, 2, 3)))).quantize(
            Decimal("0.01")
        )
        candidates.append(
            Candidate(
                sku=f"SKU-{index:02d}",
                price=price,
                landed_unit_cost=landed,
                min_order_qty=rng.randint(1, 50),
                max_supply=rng.randint(0, 1000),
            )
        )
    index = rng.randrange(len(candidates))
    loser = candidates[index]
    candidates[index] = replace(loser, price=loser.landed_unit_cost)
    return candidates


def test_at_7_1_five_hundred_random_catalogues_hold_b1_to_b8():
    rng = random.Random(20261026)

    for _ in range(500):
        candidates = _random_catalogue(rng)
        budget = Decimal(rng.randrange(0, 5_000_001)) / Decimal("100")
        sell_through = Decimal(rng.randrange(0, 101)) / Decimal("100")
        salvage = Decimal(rng.randrange(0, 101)) / Decimal("100")
        max_share = Decimal(rng.randrange(1, 101)) / Decimal("100")

        allocation = allocate(
            candidates,
            ASSUMPTIONS,
            budget=budget,
            sell_through=sell_through,
            salvage=salvage,
            max_share_per_sku=max_share,
        )
        plan_a, plan_b = allocation.base

        for plan in (plan_a, plan_b):
            _assert_b1_to_b4_b6(plan, candidates, budget)

        # B5 — Plan B only.
        cap_paise = _paise(max_share * budget)
        for line in plan_b.lines:
            assert _paise(line.capital) <= cap_paise, f"B5: {line.sku}"

        # B8 — Plan A, non-positive per-unit economics.
        forsaken = {
            item.sku
            for item in candidates
            if expected_profit_per_unit(
                item, ASSUMPTIONS, sell_through=sell_through, salvage=salvage
            )
            <= 0
        }
        for line in plan_a.lines:
            if line.sku in forsaken:
                assert line.qty == 0, f"B8: {line.sku}"

        # B7 — determinism, on every one of the 500 catalogues.
        repeat = allocate(
            candidates,
            ASSUMPTIONS,
            budget=budget,
            sell_through=sell_through,
            salvage=salvage,
            max_share_per_sku=max_share,
        )
        assert _serialise(allocation) == _serialise(repeat), "B7: two runs differed"


# --- expected_profit / score against §11.2, hand-derived --------------------


def test_expected_profit_and_score_match_the_hand_derived_business_rules_values():
    """DIYA-SET-12 (BUSINESS_RULES §11.2), worked by hand in this docstring.

    price 499.00, landed 210+6+6 = 222.00, sell_through 0.80, salvage 0.50,
    qty 10. Base: e = round(499/1.18) = 422.88; referral 0 (499 < 1,000) so the
    fees are 25 + 65 + 0 = 90.00 ex-GST and GST is round(90 x 0.18) = 16.20;
    per_sold_unit = 422.88 - 90.00 - 16.20 = 316.68. sold = 8, unsold = 2, so
    EP = 8 x 316.68 - 10 x 222 + 2 x 0.5 x 222 = 2533.44 - 2220 + 222 = 535.44.
    Conservative: price x 0.95 = 474.05; e = round(474.05/1.18) = 401.74;
    per_sold_unit = 401.74 - 90.00 - 16.20 = 295.54; sell_through = 0.60, so
    sold = 6, unsold = 4 and EP = 6 x 295.54 - 2220 + 4 x 0.5 x 222 = -2.76.
    Risk-adjusted = 0.5 x 535.44 + 0.5 x -2.76 = 266.34 over 10 x 222 = 2,220.
    """
    diya = _candidate("DIYA-SET-12")
    assert diya.landed_unit_cost == Decimal("222.00")
    assert per_sold_unit(diya, ASSUMPTIONS) == Decimal("316.68")

    base = expected_profit(
        diya, ASSUMPTIONS, qty=10, sell_through=Decimal("0.80"), salvage=Decimal("0.50")
    )
    conservative = expected_profit(
        diya,
        ASSUMPTIONS,
        qty=10,
        sell_through=Decimal("0.80"),
        salvage=Decimal("0.50"),
        scenario=CONSERVATIVE,
    )
    blended = score(
        diya, ASSUMPTIONS, qty=10, sell_through=Decimal("0.80"), salvage=Decimal("0.50")
    )

    assert base == Decimal("535.44")
    assert conservative == Decimal("-2.76")
    assert blended == Decimal("266.34") / Decimal("2220.00")


def test_the_score_ranking_is_stable_across_quantities():
    """§11.4's score rounds at the line end, so it is not exactly constant in
    ``qty``; what must hold is that the choice of ``qty`` cannot reorder the
    catalogue, because the greedy ranks on a single value per SKU."""
    candidates = _sample_candidates()

    def order(qty: int) -> list[str]:
        return [
            item.sku
            for item in sorted(
                candidates,
                key=lambda item: (
                    -score(item, ASSUMPTIONS, qty=qty, sell_through=SELL_THROUGH, salvage=SALVAGE)
                ),
            )
        ]

    assert order(1) == order(137)


# --- check_invariants: a breach must be loud --------------------------------


def test_check_invariants_raises_on_an_overspending_plan():
    candidate = _candidate("TORAN-FLW-1")
    line = PlanLine(
        sku="TORAN-FLW-1",
        qty=120,
        capital=Decimal("31320.00"),
        expected_contribution=Decimal("0.00"),
        score=Decimal("0.20"),
    )
    plan = Plan(
        strategy="roi_first",
        label="Plan A - ROI-first",
        lines=(line,),
        capital_used=Decimal("31320.00"),
        budget_remaining=Decimal("0.00"),
        expected_contribution=Decimal("0.00"),
    )

    with pytest.raises(ValueError, match="B10"):
        check_invariants(plan, budget=Decimal("1000.00"), candidates=[candidate])


def test_check_invariants_raises_on_a_supply_breach():
    candidate = _candidate("TORAN-FLW-1")
    line = PlanLine(
        sku="TORAN-FLW-1",
        qty=candidate.max_supply + 1,
        capital=candidate.landed_unit_cost * (candidate.max_supply + 1),
        expected_contribution=Decimal("0.00"),
        score=Decimal("0.20"),
    )
    plan = Plan(
        strategy="roi_first",
        label="Plan A - ROI-first",
        lines=(line,),
        capital_used=line.capital,
        budget_remaining=Decimal("0.00"),
        expected_contribution=Decimal("0.00"),
    )

    with pytest.raises(ValueError, match="B4"):
        check_invariants(plan, budget=Decimal("999999.00"), candidates=[candidate])
