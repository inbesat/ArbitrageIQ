"""Acceptance tests for the Decimal money primitives (task T02).

Every expected value below is copied from ``plans/ACCEPTANCE_TESTS.md`` AT-2.
Nothing here is derived from the implementation under test.

Rounding rule (``plans/BUSINESS_RULES.md`` §4): half-up to 2 decimal places.
Ratio rule (§4): a zero or missing denominator renders the literal ``"n/a"`` —
never ``0``, ``inf`` or ``NaN`` — and must not raise.
"""

import ast
from decimal import Decimal
from pathlib import Path

from arbitrageiq.money import NA, ratio, round_half_up

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "arbitrageiq"


def test_at_2_1_exact_half_rounds_up() -> None:
    assert round_half_up(Decimal("0.005")) == Decimal("0.01")


def test_at_2_2_below_half_rounds_down() -> None:
    assert round_half_up(Decimal("0.004")) == Decimal("0.00")


def test_at_2_3_negative_half_rounds_away_from_zero() -> None:
    assert round_half_up(Decimal("-0.005")) == Decimal("-0.01")


def test_at_2_4_rounding_is_per_line_then_summed() -> None:
    # The primitive half of AT-2.4: rounding each line and then summing yields
    # 0.02, while rounding the aggregate yields 0.01. The per-line aggregation
    # itself belongs to the engine (T04).
    assert round_half_up(Decimal("0.005")) + round_half_up(Decimal("0.005")) == Decimal("0.02")
    assert round_half_up(Decimal("0.005") + Decimal("0.005")) == Decimal("0.01")


def test_at_2_5_no_float_appears_in_any_money_result() -> None:
    for text in ("0.005", "-0.005", "1180.00", "1000.00"):
        result = round_half_up(Decimal(text))
        assert isinstance(result, Decimal)
        assert not isinstance(result, float)

    assert isinstance(ratio(Decimal("100.00"), Decimal("10")), Decimal)
    assert isinstance(round_half_up(Decimal("0.005")), Decimal)


def test_ratio_rule_renders_the_literal_na_and_never_raises() -> None:
    assert ratio(Decimal("1.00"), Decimal("0")) == NA
    assert ratio(Decimal("1.00"), Decimal("0.00")) == NA
    assert ratio(Decimal("1.00"), None) == NA


def test_ratio_rounds_to_two_places_half_up() -> None:
    assert ratio(Decimal("1.00"), Decimal("3.00")) == Decimal("0.33")
    assert ratio(Decimal("-1.00"), Decimal("3000.00")) == Decimal("-0.00")
    assert ratio(Decimal("250.00"), Decimal("1000.00"), percent=True) == Decimal("25.00")


def test_ratio_percent_respects_the_na_rule() -> None:
    assert ratio(Decimal("250.00"), Decimal("0"), percent=True) == NA


def _money_modules() -> list[Path]:
    # AT-2.6 covers money.py, profit.py and the money paths of allocator.py. The
    # last two arrive in T04 and T11; this guard picks them up with no edit.
    names = ("money.py", "profit.py", "allocator.py")
    return [PACKAGE_DIR / name for name in names if (PACKAGE_DIR / name).is_file()]


def test_at_2_6_no_float_literal_in_the_money_modules() -> None:
    offenders: list[str] = []
    for path in _money_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"float literal in a money module: {offenders}"


def test_money_module_imports_nothing_project_local() -> None:
    tree = ast.parse((PACKAGE_DIR / "money.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"decimal", "typing"}, imported
