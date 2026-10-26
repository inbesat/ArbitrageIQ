"""Decimal money primitives: rounding and ratio helpers (task T02).

Source of truth for the rules implemented here:
- ``plans/BUSINESS_RULES.md`` §4 — "Money is ``Decimal``. Round half-up to 2 decimal
  places at the end of each transaction line, then sum the rounded line values."
- ``plans/BUSINESS_RULES.md`` §4 — "Any ratio with a zero or missing denominator
  ... is rendered as the string ``"n/a"``. It is never ``0``, ``inf``, or ``NaN``."
- ``plans/ACCEPTANCE_TESTS.md`` AT-2 — the expected values asserted by
  ``backend/tests/test_money.py``.

This module imports nothing project-local: ``decimal`` only. It performs no
monetary arithmetic beyond rounding and division-on-request; the contribution
model lives in ``profit.py`` (T04).
"""

from decimal import ROUND_HALF_UP, Decimal

#: The literal rendered whenever a ratio has a zero or missing denominator.
NA = "n/a"

_CENTS = Decimal("0.01")
_HUNDRED = Decimal("100")


def round_half_up(value: Decimal) -> Decimal:
    """Round ``value`` to 2 decimal places, half-up, ties away from zero.

    ``decimal.ROUND_HALF_UP`` rounds ties away from zero, which is the documented
    choice for negatives (``plans/ACCEPTANCE_TESTS.md`` AT-2.3).
    """
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def ratio(
    numerator: Decimal, denominator: Decimal | None, *, percent: bool = False
) -> Decimal | str:
    """Return ``numerator / denominator`` rounded half-up to 2 dp.

    Returns :data:`NA` instead of raising when ``denominator`` is ``None`` or zero
    (``plans/BUSINESS_RULES.md`` §4 ratio rule). With ``percent=True`` the result is
    multiplied by 100 first, so a margin of 0.25 renders as ``Decimal("25.00")``.
    """
    if denominator is None or denominator == 0:
        return NA
    result = numerator / denominator
    if percent:
        result *= _HUNDRED
    return round_half_up(result)


def rate_text(value: Decimal) -> str:
    """Render a fractional rate the way ``plans/BUSINESS_RULES.md`` §2 writes it.

    Two decimal places when that is exact, otherwise the fewest places the value
    needs. The stored column carries six places, so ``referral_rate`` reads back as
    ``Decimal("0.080000")`` and must render as ``0.08``, while TCS ``0.005`` must
    keep its third place rather than becoming ``0.01``.

    ``normalize()`` alone would be wrong in both directions: it turns ``0.80`` into
    ``0.8``, and on a whole number it produces exponent form (``1E+3``). Rates are
    validated to ``[0, 1]``, so the fallback here can never reach exponent form.
    """
    two_places = value.quantize(_CENTS, rounding=ROUND_HALF_UP)
    return str(two_places) if two_places == value else str(value.normalize())
