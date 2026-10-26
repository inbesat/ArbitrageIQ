"""Contribution-engine tests: the golden fixture and the breakdown (task T04).

Every expected value below is copied from ``plans/ACCEPTANCE_TESTS.md`` (AT-1,
AT-2, AT-3) or from a hand derivation written out in a comment, per
``plans/BUSINESS_RULES.md`` §10.4.2: an expectation must never be produced by
running the implementation under test. The fixture *parameters* are loaded from
``tests/fixtures/golden_v1.json``, which stores no expectations at all.

Hand derivation of AT-1.1 (independent of the code, from ``plans/BUSINESS_RULES.md``
§10.2 Derivation A, with the §10.3 payout route as the cross-check):

    p             = 1180.00 - 0.00           = 1180.00
    e             = 1180.00 / 1.18           = 1000.00          (exact)
    gross_revenue = 1000.00 * 10             = 10000.00
    refunds       = 1000.00 * 1              =  1000.00         (e_refund defaults to e)
    net_revenue   = 10000.00 - 1000.00       =  9000.00
    referral      = 1180.00 * 0.08           =    94.40         (p >= 1000, so charged)
    fees_ex_gst   = (94.40 + 25 + 65 + 0) * 10 = 1844.00        (GROSS units shipped)
    fee_gst       = 1844.00 * 0.18           =   331.92
    product_cost  = 500.00 * 10 - 0          =  5000.00
    contribution  = 9000.00 - 1844.00 - 331.92 - 5000.00 - 200.00
                  = 1624.08

    Cross-check (§10.3, payout route): 10*1180 = 11800; -1180 refund = 10620 cash;
    -2175.92 retained = 8444.08 payout; -1620.00 GST owed; -5000.00; -200.00 = 1624.08.
"""

import ast
import json
from decimal import Decimal
from pathlib import Path

from arbitrageiq.config import FeeAssumptions
from arbitrageiq.profit import LineInput, compute_line

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / "arbitrageiq"

FIXTURE = json.loads((FIXTURES_DIR / "golden_v1.json").read_text(encoding="utf-8"))

MONEY_FIELDS = (
    "price_paid",
    "ex_gst_unit_price",
    "gross_revenue",
    "refunds",
    "net_revenue",
    "referral_fee",
    "fees_ex_gst",
    "fee_gst",
    "product_cost",
    "ads",
    "other_charges",
    "contribution",
)
RATIO_FIELDS = ("profit_per_unit", "margin_pct", "roi_pct")


#: Line keys that are not money and must never be coerced to ``Decimal``.
_NON_MONEY_LINE_KEYS = frozenset({"sku", "transaction_id", "units_sold", "returned_units"})


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
    kwargs["landed_unit_cost"] = Decimal(FIXTURE["landed_unit_cost"])
    kwargs.update(overrides)
    return LineInput(**kwargs)


# --------------------------------------------------------------------------- #
# AT-1 — the golden fixture
# --------------------------------------------------------------------------- #


def test_at_1_1_fixture_v1_contribution_is_1624_08():
    result = compute_line(golden_line(), golden_assumptions())
    assert result.contribution == Decimal("1624.08")


def test_at_1_1_fixture_v1_full_breakdown():
    """Every intermediate step of §4, asserted against the §10.2 derivation."""
    result = compute_line(golden_line(), golden_assumptions())

    assert result.price_paid == Decimal("1180.00")
    assert result.ex_gst_unit_price == Decimal("1000.00")
    assert result.net_units == 9
    assert result.gross_revenue == Decimal("10000.00")
    assert result.refunds == Decimal("1000.00")
    assert result.net_revenue == Decimal("9000.00")
    assert result.referral_fee == Decimal("94.40")
    assert result.fees_ex_gst == Decimal("1844.00")
    assert result.fee_gst == Decimal("331.92")
    assert result.product_cost == Decimal("5000.00")
    assert result.ads == Decimal("200.00")
    assert result.other_charges == Decimal("0.00")
    assert result.fee_source == "model"

    # §8 derived metrics. 1624.08 / 9 = 180.4533... -> 180.45
    # 1624.08 / 9000 * 100 = 18.0453... -> 18.05 ; 1624.08 / 5000 * 100 = 32.4816 -> 32.48
    assert result.profit_per_unit == Decimal("180.45")
    assert result.margin_pct == Decimal("18.05")
    assert result.roi_pct == Decimal("32.48")


def test_at_1_2_itc_recoverable_removes_gst_on_fees_giving_1956_00():
    """AT-1.2: only fee_gst is removed, so 9000.00 - 1844.00 - 5000.00 - 200.00."""
    result = compute_line(golden_line(), golden_assumptions(fee_gst_recoverable=True))

    assert result.contribution == Decimal("1956.00")
    assert result.fee_gst == Decimal("331.92")  # still computed and reported
    # 1956.00 / 9 = 217.33... -> 217.33 ; 1956.00/9000*100 = 21.733 -> 21.73
    # 1956.00/5000*100 = 39.12
    assert result.profit_per_unit == Decimal("217.33")
    assert result.margin_pct == Decimal("21.73")
    assert result.roi_pct == Decimal("39.12")


def test_at_1_3_zero_returns_gives_2624_08():
    """AT-1.3 derivation: refunds 0 -> net_revenue 10000.00; fees still on 10 gross units.

    10000.00 - 1844.00 - 331.92 - 5000.00 - 200.00 = 2624.08
    """
    result = compute_line(golden_line(returned_units=0), golden_assumptions())

    assert result.net_units == 10
    assert result.refunds == Decimal("0.00")
    assert result.net_revenue == Decimal("10000.00")
    assert result.fees_ex_gst == Decimal("1844.00")  # unchanged: gross units
    assert result.contribution == Decimal("2624.08")
    # 2624.08 / 10 = 262.408 -> 262.41 ; /10000*100 = 26.2408 -> 26.24
    # /5000*100 = 52.4816 -> 52.48
    assert result.profit_per_unit == Decimal("262.41")
    assert result.margin_pct == Decimal("26.24")
    assert result.roi_pct == Decimal("52.48")


def test_at_1_4_settlement_matching_the_model_is_equivalent_and_never_additive():
    """AT-1.4: settlement 2175.92 splits as 1844.00 ex-GST + 331.92 GST (§6 S2)."""
    result = compute_line(
        golden_line(settlement_fees_total=Decimal("2175.92")), golden_assumptions()
    )

    assert result.fee_source == "settlement"
    assert result.fees_ex_gst == Decimal("1844.00")
    assert result.fee_gst == Decimal("331.92")
    assert result.referral_fee == Decimal("0.00")  # the model is not consulted
    assert result.contribution == Decimal("1624.08")


def test_at_1_5_settlement_bypasses_the_model_not_merely_overrides_it():
    """AT-1.5: a changed referral_rate cannot move a settled row."""
    result = compute_line(
        golden_line(settlement_fees_total=Decimal("2175.92")),
        golden_assumptions(referral_rate=Decimal("0.99")),
    )

    assert result.contribution == Decimal("1624.08")
    assert result.fees_ex_gst == Decimal("1844.00")
    assert result.fee_gst == Decimal("331.92")


# --------------------------------------------------------------------------- #
# AT-2 — rounding and money type
# --------------------------------------------------------------------------- #


def test_at_2_4_rounding_is_per_line_then_summed():
    """AT-2.4: two lines of 0.005 produce 0.02, not 0.01.

    Each line's raw contribution is exactly 0.005 (net revenue 1.00 minus
    other_charges 0.995), so each line rounds to 0.01. Their raw sum is 0.010,
    which would round to 0.01 — the two differ, so this proves the engine rounds
    per line and sums the rounded lines (``BUSINESS_RULES.md`` §4, §9).
    """
    assumptions = golden_assumptions(
        closing_fee=Decimal("0.00"),
        shipping_fee=Decimal("0.00"),
        fulfilment_fee=Decimal("0.00"),
    )
    line = golden_line(
        units_sold=1,
        returned_units=0,
        selling_price=Decimal("1.18"),
        landed_unit_cost=Decimal("0.00"),
        ads_cost=Decimal("0.00"),
        other_charges=Decimal("0.995"),
    )

    first = compute_line(line, assumptions)
    second = compute_line(line, assumptions)

    assert first.contribution == Decimal("0.01")
    assert second.contribution == Decimal("0.01")
    assert first.contribution + second.contribution == Decimal("0.02")
    # the aggregate of the *unrounded* lines would have rounded to 0.01
    raw_sum = Decimal("0.005") + Decimal("0.005")
    assert raw_sum.quantize(Decimal("0.01")) == Decimal("0.01")


def test_at_2_5_every_money_output_is_a_decimal_and_never_a_float():
    result = compute_line(golden_line(), golden_assumptions())

    for field in MONEY_FIELDS:
        value = getattr(result, field)
        assert isinstance(value, Decimal), field
        assert not isinstance(value, float), field
    assert isinstance(result.contribution, Decimal)


def test_at_2_7_decimal_money_survives_a_json_round_trip_exactly():
    """AT-2.7: Decimal("1624.08") in -> "1624.08" out -> Decimal("1624.08")."""
    result = compute_line(golden_line(), golden_assumptions())

    payload = json.dumps({"contribution": str(result.contribution)})
    restored = json.loads(payload)["contribution"]

    assert restored == "1624.08"
    assert Decimal(restored) == Decimal("1624.08")


# --------------------------------------------------------------------------- #
# AT-3 — zero, null and degenerate inputs
# --------------------------------------------------------------------------- #


def test_at_3_1_zero_units_gives_zero_contribution_and_na_ratios():
    result = compute_line(
        golden_line(units_sold=0, returned_units=0, ads_cost=Decimal("0.00")),
        golden_assumptions(),
    )

    assert result.contribution == Decimal("0.00")
    assert result.net_units == 0
    assert result.profit_per_unit == "n/a"
    assert result.margin_pct == "n/a"
    assert result.roi_pct == "n/a"


def test_at_3_2_zero_net_revenue_with_ads_is_negative_and_never_divides_by_zero():
    """One shipped, one returned: net_revenue 0, but ads and fees are still real."""
    result = compute_line(golden_line(units_sold=1, returned_units=1), golden_assumptions())

    assert result.net_revenue == Decimal("0.00")
    assert result.margin_pct == "n/a"
    assert result.contribution < Decimal("0.00")
    # 0.00 - 500.00 - 184.40 - 33.19 - 200.00 = -917.59
    assert result.contribution == Decimal("-917.59")


def test_at_3_3_zero_landed_cost_makes_roi_na():
    result = compute_line(
        golden_line(units_sold=2, returned_units=0, landed_unit_cost=Decimal("0.00")),
        golden_assumptions(),
    )

    assert result.product_cost == Decimal("0.00")
    assert result.roi_pct == "n/a"
    # 2000.00 - 0.00 - 368.80 - 66.38 - 200.00 = 1364.82
    assert result.contribution == Decimal("1364.82")


def test_at_3_4_full_return_has_zero_net_revenue_and_a_negative_finite_contribution():
    """AT-3.4, partially.

    AT-3.4 in ``plans/ACCEPTANCE_TESTS.md`` also states ``product_cost = 0``. That
    contradicts ``plans/BUSINESS_RULES.md`` §4 step 8 — ``product_cost =
    L * units_sold - resale_fraction * L * returned_units``, with ``resale_fraction``
    fixed at 0, i.e. ``L * units_sold`` — which is exactly how the golden fixture
    reaches 5000.00 with units_sold 10. A 100% return of a non-zero units_sold
    therefore cannot have zero product cost. BUSINESS_RULES.md outranks
    ACCEPTANCE_TESTS.md (``plans/CONTEXT.md`` §3), so the product_cost clause is
    deliberately NOT asserted here and is raised for human resolution instead of
    being silently adjusted (``AGENTS.md`` rule 4).
    """
    result = compute_line(golden_line(units_sold=1, returned_units=1), golden_assumptions())

    assert result.net_revenue == Decimal("0.00")
    assert result.fees_ex_gst == Decimal("184.40")  # fees charged on all shipped units
    assert result.contribution < Decimal("0.00")
    assert result.contribution.is_finite()
    # Hand re-derivation: 0.00 - 500.00 - 184.40 - 33.19 - 200.00 = -917.59
    # (net_revenue 0.00; product cost L * units_sold = 500.00; fees on all shipped
    # units 184.40 + 33.19 GST; and the golden line's ads_cost of 200.00).
    # The same scenario is asserted as AT-3.2; both carry the same figure.
    assert result.contribution == Decimal("-917.59")


def test_at_3_5_negative_per_unit_economics_yields_no_imaginary_profit():
    result = compute_line(
        golden_line(
            units_sold=2,
            returned_units=0,
            selling_price=Decimal("120.00"),
            ads_cost=Decimal("0.00"),
        ),
        golden_assumptions(),
    )

    assert result.contribution < Decimal("0.00")
    # 203.38 - 1000.00 - 180.00 - 32.40 - 0.00 = -1009.02
    assert result.contribution == Decimal("-1009.02")


def test_at_3_6_no_nan_infinity_or_null_appears_in_any_money_field():
    cases = [
        (golden_line(), golden_assumptions()),
        (golden_line(returned_units=0), golden_assumptions()),
        (golden_line(settlement_fees_total=Decimal("2175.92")), golden_assumptions()),
        (
            golden_line(units_sold=0, returned_units=0, ads_cost=Decimal("0.00")),
            golden_assumptions(),
        ),
        (golden_line(units_sold=1, returned_units=1), golden_assumptions()),
        (
            golden_line(units_sold=2, returned_units=0, landed_unit_cost=Decimal("0.00")),
            golden_assumptions(),
        ),
    ]

    for line, assumptions in cases:
        result = compute_line(line, assumptions)
        for field in MONEY_FIELDS:
            value = getattr(result, field)
            assert value.is_finite(), f"{field} was {value}"
            assert str(value) not in {"NaN", "Infinity", "-Infinity", "null"}, field
        for field in RATIO_FIELDS:
            value = getattr(result, field)
            assert value == "n/a" or isinstance(value, Decimal), f"{field} was {value}"
            if isinstance(value, Decimal):
                assert value.is_finite(), f"{field} was {value}"


# --------------------------------------------------------------------------- #
# Structural rules
# --------------------------------------------------------------------------- #


def test_profit_module_imports_only_money_and_config():
    """``plans/ARCHITECTURE.md`` §3: profit may import money and config, nothing else."""
    source = (PACKAGE_DIR / "profit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)

    project_local = {name for name in imported if name.split(".")[0] == "arbitrageiq"}
    assert project_local <= {"arbitrageiq.money", "arbitrageiq.config"}

    stdlib_allowed = {"dataclasses", "decimal", "typing"}
    assert imported <= {"arbitrageiq.money", "arbitrageiq.config"} | stdlib_allowed
