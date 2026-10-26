"""Unit-economics tests — AT-4.1 to AT-4.5 (task T05).

Every expected value below is hand-derived from ``plans/BUSINESS_RULES.md``
§4 (the ordered per-transaction algorithm), §5 (the fee model) and §8 (the derived
metrics), using the §10.1 golden-fixture parameters. None of them is produced by
the function under test (``plans/BUSINESS_RULES.md`` §10.4.2;
``plans/ACCEPTANCE_TESTS.md`` "Golden rule").

Steady-state single-unit case per §8: ``units_sold = 1``, ``returned_units = 0``,
ads and other charges zero, no settlement figure, ``resale_fraction = 0``.

Hand derivation with the §10.1 assumptions
(``L = 500.00``, ``product_gst_rate = 0.18``, closing 25.00 + shipping 65.00 +
fulfilment 0.00 = ``90.00``, ``gst_on_fees_rate = 0.18``, ``fee_gst_recoverable =
false``, ``zero_referral_below = 1000.00``, ``referral_rate = 0.08``)::

    fee_gst at one unit = round2(90.00 * 0.18) = 16.20, so below the 1,000 floor
    contribution(p)     = round2(p / 1.18) - 500.00 - 90.00 - 16.20
                        = round2(p / 1.18) - 606.20

    AT-4.1  (contribution >= 0):  need round2(p / 1.18) >= 606.20
      p = 715.32 -> 715.32 / 1.18 = 606.203389... -> round2 = 606.20 -> contribution   0.00  holds
      p = 715.31 -> 715.31 / 1.18 = 606.194915... -> round2 = 606.19 -> contribution  -0.01  fails

    AT-4.3  (contribution / e >= 0.20):  (e - 606.20) / e >= 0.20  =>  e >= 606.20 / 0.80 = 757.75
      p = 894.14 -> 894.14 / 1.18 = 757.745762... -> round2 = 757.75
                  -> contribution = 151.55, and 151.55 / 757.75 = 0.2 exactly            holds
      p = 894.13 -> 894.13 / 1.18 = 757.737288... -> round2 = 757.74
                  -> contribution = 151.54, and 151.54 / 757.74 = 0.19999736... < 0.20   fails

Both solved prices sit below the 1,000 zero-referral floor, so the no-referral
branch applies. The objective is **piecewise, not monotonic**: at ``p = 1000.00``
the referral switches on and contribution *drops* to 146.86
(``847.46 - 500.00 - 170.00 - 30.60``), so a solver may not binary-search the whole
domain.

AT-4.3 is asserted against the **exact** ``contribution / e`` quotient, because the
2-dp ``ratio(..., percent=True)`` display field reads ``20.00`` at both 894.14 and
894.13 and therefore cannot falsify the boundary.
"""

import json
from decimal import Decimal
from pathlib import Path

from arbitrageiq.config import FeeAssumptions
from arbitrageiq.profit import (
    LineInput,
    break_even_price,
    compute_line,
    minimum_price_for_target_margin,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE = json.loads((FIXTURES_DIR / "golden_v1.json").read_text(encoding="utf-8"))

# Fixture v1's §10.1 landed cost, reused for both solves.
_LANDED_UNIT_COST = Decimal(FIXTURE["landed_unit_cost"])

# Literal outputs of compute_line for the §10.1 fixture line, copied from
# plans/ACCEPTANCE_TESTS.md AT-1.1/AT-4.4/AT-4.5.
_GOLDEN_CONTRIBUTION = Decimal("1624.08")
_GOLDEN_MARGIN_PCT = Decimal("18.05")
_GOLDEN_ROI_PCT = Decimal("32.48")

# A ratio computed over the wrong denominator, used to prove AT-4.4/AT-4.5 are live.
_MARGIN_OVER_EX_GST_PRICE_PCT = Decimal("162.41")
_ROI_OVER_NET_UNITS_PCT = Decimal("36.09")

_NON_MONEY_LINE_KEYS = frozenset({"sku", "transaction_id", "units_sold", "returned_units"})

# §4.2's banned vocabulary, plus PRD §4.3's explicit "never a recommendation" for prices.
# Words banned outright in any solved-price field or basis text. "forecast" is
# deliberately NOT here: §8 requires the phrase "not a forecast", so it is governed
# by the negation-precision assertion below instead of a flat ban.
_BANNED_PRICE_WORDS = ("optimal", "best", "guaranteed", "recommend", "predict")


def _decimalise(value):
    return Decimal(value) if isinstance(value, str) else value


def golden_assumptions(**overrides) -> FeeAssumptions:
    """The §10.1 assumption set, built from the fixture file, with overrides."""
    kwargs = {key: _decimalise(value) for key, value in FIXTURE["assumptions"].items()}
    kwargs.update(overrides)
    return FeeAssumptions(**kwargs)


def golden_line(**overrides) -> LineInput:
    """The §10.1 transaction line, built from the fixture file, with overrides."""
    kwargs = {
        key: (value if key in _NON_MONEY_LINE_KEYS else _decimalise(value))
        for key, value in FIXTURE["line"].items()
    }
    kwargs["landed_unit_cost"] = _LANDED_UNIT_COST
    kwargs.update(overrides)
    return LineInput(**kwargs)


def steady_state_contribution(price: str) -> Decimal:
    """contribution for one shipped unit, no returns, no ads, at ``price``."""
    line = LineInput(
        sku="STEADY",
        units_sold=1,
        returned_units=0,
        selling_price=Decimal(price),
        landed_unit_cost=_LANDED_UNIT_COST,
    )
    return compute_line(line, golden_assumptions()).contribution


def steady_state_contribution_over_e(price: str) -> Decimal:
    """The EXACT contribution / e quotient at ``price`` — never the rounded field."""
    line = LineInput(
        sku="STEADY",
        units_sold=1,
        returned_units=0,
        selling_price=Decimal(price),
        landed_unit_cost=_LANDED_UNIT_COST,
    )
    breakdown = compute_line(line, golden_assumptions())
    return breakdown.contribution / breakdown.ex_gst_unit_price


# --- AT-4.1 -------------------------------------------------------------------


def test_at_4_1_break_even_price_is_715_32():
    result = break_even_price(golden_assumptions(), _LANDED_UNIT_COST)
    assert result.price == Decimal("715.32")


def test_at_4_1_break_even_boundary_holds_at_the_price_and_fails_one_paisa_below():
    assert steady_state_contribution("715.32") == Decimal("0.00")
    assert steady_state_contribution("715.32") >= Decimal("0")
    assert steady_state_contribution("715.31") == Decimal("-0.01")
    assert steady_state_contribution("715.31") < Decimal("0")


# --- AT-4.2 -------------------------------------------------------------------


def test_at_4_2_solved_prices_are_labelled_a_steady_state_pricing_floor():
    for result in (
        break_even_price(golden_assumptions(), _LANDED_UNIT_COST),
        minimum_price_for_target_margin(golden_assumptions(), _LANDED_UNIT_COST, Decimal("0.20")),
    ):
        assert result.steady_state is True
        basis = result.basis.lower()
        assert "pricing floor" in basis
        assert "steady state" in basis
        assert "not a forecast" in basis


def test_at_4_2_no_price_field_or_basis_text_claims_optimality_or_prediction():
    results = (
        break_even_price(golden_assumptions(), _LANDED_UNIT_COST),
        minimum_price_for_target_margin(golden_assumptions(), _LANDED_UNIT_COST, Decimal("0.20")),
    )
    for result in results:
        haystack = repr(result).lower()
        for word in _BANNED_PRICE_WORDS:
            assert word not in haystack, f"banned word {word!r} in a solved-price field"
        # "forecast" may appear only inside the required negation, never as a claim.
        assert haystack.count("forecast") == haystack.count("not a forecast")


# --- AT-4.3 -------------------------------------------------------------------


def test_at_4_3_minimum_price_for_a_target_margin_of_20_percent_is_894_14():
    result = minimum_price_for_target_margin(
        golden_assumptions(), _LANDED_UNIT_COST, Decimal("0.20")
    )
    assert result.price == Decimal("894.14")
    assert result.target_margin == Decimal("0.20")


def test_at_4_3_target_margin_boundary_holds_at_the_price_and_fails_one_paisa_below():
    # Asserted on the exact quotient: the rounded percent field reads 20.00 at both prices.
    assert steady_state_contribution_over_e("894.14") == Decimal("0.2")
    assert steady_state_contribution_over_e("894.14") >= Decimal("0.20")
    assert steady_state_contribution_over_e("894.13") < Decimal("0.20")


def test_at_4_3_the_solved_prices_sit_below_the_zero_referral_floor_so_no_referral_applies():
    # Guards the piecewise branch: at 1,000.00 the referral switches on and contribution drops.
    assert steady_state_contribution("999.99") > steady_state_contribution("1000.00")
    assert steady_state_contribution("1000.00") == Decimal("146.86")


# --- AT-4.4 and AT-4.5 (re-asserted here, per PHASES_DETAILED.md T05) ----------


def test_at_4_4_margin_denominator_is_net_revenue_not_the_ex_gst_price_or_units_sold():
    breakdown = compute_line(golden_line(), golden_assumptions())

    assert breakdown.net_revenue == Decimal("9000.00")
    assert breakdown.margin_pct == _GOLDEN_MARGIN_PCT
    # 1624.08 / 9000.00 * 100 = 18.05; over e (1000.00) or over units_sold it would be 162.41.
    assert breakdown.margin_pct != _MARGIN_OVER_EX_GST_PRICE_PCT


def test_at_4_5_roi_denominator_is_gross_shipped_inventory_cost_not_net_units():
    breakdown = compute_line(golden_line(), golden_assumptions())

    # 1624.08 / (500.00 * 10) * 100 = 32.48; over L * n (500.00 * 9) it would be 36.09.
    assert breakdown.roi_pct == _GOLDEN_ROI_PCT
    assert breakdown.roi_pct != _ROI_OVER_NET_UNITS_PCT
    assert breakdown.net_units == 9


# --- Golden fixture re-check (the code under it changed in T05) ----------------


def test_golden_fixture_v1_still_reproduces_1624_08_after_the_T05_change():
    breakdown = compute_line(golden_line(), golden_assumptions())
    assert breakdown.contribution == _GOLDEN_CONTRIBUTION
