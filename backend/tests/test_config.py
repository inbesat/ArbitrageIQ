"""Acceptance tests for the dated assumption model (task T03).

Source of truth:

- ``plans/BUSINESS_RULES.md`` §2 — the assumption table (key, type, default,
  unit) and rules R1-R4.
- ``plans/PHASES_DETAILED.md`` §T03 — done condition and Checks row.

Every expected value below is copied from the §2 table, never derived from the
code under test (``AGENTS.md`` rule 3). R2 is transcribed clause by clause so a
missing range check produces a failing test rather than a silent pass.
"""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from arbitrageiq.config import (
    ILLUSTRATIVE_NOTE,
    FeeAssumptions,
    active_assumptions,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "arbitrageiq"

#: ``plans/BUSINESS_RULES.md`` §2, verbatim: key -> (default, exact type).
SECTION_2_DEFAULTS = {
    "referral_rate": (Decimal("0.08"), Decimal),
    "zero_referral_below": (Decimal("1000.00"), Decimal),
    "closing_fee": (Decimal("25.00"), Decimal),
    "shipping_fee": (Decimal("65.00"), Decimal),
    "fulfilment_fee": (Decimal("0.00"), Decimal),
    "product_gst_rate": (Decimal("0.18"), Decimal),
    "gst_on_fees_rate": (Decimal("0.18"), Decimal),
    "fee_gst_recoverable": (False, bool),
    "tcs_rate": (Decimal("0.005"), Decimal),
    "tds_rate": (Decimal("0.001"), Decimal),
    "default_sell_through": (Decimal("0.80"), Decimal),
    "default_salvage": (Decimal("0.50"), Decimal),
    "default_budget": (Decimal("50000.00"), Decimal),
    "default_max_share_per_sku": (Decimal("0.40"), Decimal),
}

#: Every R2 violation, paired with the field name the error must name.
R2_VIOLATIONS = [
    ({"referral_rate": Decimal("1.5")}, "referral_rate"),
    ({"referral_rate": Decimal("-0.01")}, "referral_rate"),
    ({"product_gst_rate": Decimal("1.01")}, "product_gst_rate"),
    ({"gst_on_fees_rate": Decimal("-0.1")}, "gst_on_fees_rate"),
    ({"tcs_rate": Decimal("2")}, "tcs_rate"),
    ({"tds_rate": Decimal("-0.001")}, "tds_rate"),
    ({"default_sell_through": Decimal("1.01")}, "default_sell_through"),
    ({"default_salvage": Decimal("-0.01")}, "default_salvage"),
    ({"closing_fee": Decimal("-1.00")}, "closing_fee"),
    ({"shipping_fee": Decimal("-0.01")}, "shipping_fee"),
    ({"fulfilment_fee": Decimal("-5.00")}, "fulfilment_fee"),
    ({"default_budget": Decimal("-1.00")}, "default_budget"),
    ({"zero_referral_below": Decimal("-1.00")}, "zero_referral_below"),
    ({"default_max_share_per_sku": Decimal("0")}, "default_max_share_per_sku"),
    ({"default_max_share_per_sku": Decimal("1.01")}, "default_max_share_per_sku"),
]

#: Inclusive boundaries R2 permits; each must construct without raising.
R2_ACCEPTED_BOUNDARIES = [
    {"referral_rate": Decimal("0")},
    {"referral_rate": Decimal("1")},
    {"product_gst_rate": Decimal("0")},
    {"gst_on_fees_rate": Decimal("1")},
    {"tcs_rate": Decimal("0")},
    {"tds_rate": Decimal("1")},
    {"default_sell_through": Decimal("1")},
    {"default_salvage": Decimal("0")},
    {"closing_fee": Decimal("0")},
    {"shipping_fee": Decimal("0")},
    {"fulfilment_fee": Decimal("0")},
    {"default_budget": Decimal("0")},
    {"zero_referral_below": Decimal("0")},
    {"default_max_share_per_sku": Decimal("1")},
]


@pytest.mark.parametrize(("key", "expected"), sorted(SECTION_2_DEFAULTS.items()))
def test_section_2_defaults_and_types_match_the_table(key, expected):
    default, exact_type = expected
    value = getattr(FeeAssumptions(), key)
    assert value == default
    assert type(value) is exact_type


def test_effective_from_defaults_to_today_and_the_note_is_the_illustrative_label():
    assumptions = FeeAssumptions()
    assert assumptions.effective_from == date.today()
    assert assumptions.note == ILLUSTRATIVE_NOTE


@pytest.mark.parametrize(("overrides", "field"), R2_VIOLATIONS)
def test_r2_rejects_every_out_of_range_value_naming_the_field(overrides, field):
    with pytest.raises(ValueError, match=field):
        FeeAssumptions(**overrides)


@pytest.mark.parametrize("overrides", R2_ACCEPTED_BOUNDARIES)
def test_r2_inclusive_boundaries_are_accepted(overrides):
    FeeAssumptions(**overrides)


def test_active_assumptions_picks_the_latest_record_effective_on_or_before_the_date():
    january = FeeAssumptions(effective_from=date(2026, 1, 1), referral_rate=Decimal("0.01"))
    june = FeeAssumptions(effective_from=date(2026, 6, 1), referral_rate=Decimal("0.02"))

    assert active_assumptions([june, january], on=date(2026, 8, 1)) is june
    assert active_assumptions([january, june], on=date(2026, 6, 1)) is june
    assert active_assumptions([june, january], on=date(2026, 3, 1)) is january


def test_active_assumptions_raises_when_no_record_is_effective_yet():
    future = FeeAssumptions(effective_from=date(2027, 1, 1))
    with pytest.raises(LookupError, match="effective_from"):
        active_assumptions([future], on=date(2026, 1, 1))


def test_config_module_imports_only_money_and_the_standard_library():
    tree = ast.parse((PACKAGE_DIR / "config.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)

    project_local = {name for name in imported if name.split(".")[0] == "arbitrageiq"}
    assert project_local <= {"arbitrageiq.money"}, project_local
