"""The single-SKU what-if behind ``POST /api/v1/simulate/sku`` (deviation DEV-39).

This module adds no financial rule. It turns the caller's terms into a
``profit.LineInput`` and hands it to ``profit.compute_line``, so a simulated
line and an imported line cannot drift apart: the order of operations, the
rounding, and the treatment of TCS and TDS stay in one place
(``plans/BUSINESS_RULES.md`` §4 and §7).

Only one new rounding exists here, and it is not a money one. A returns *rate*
has to become a whole number of units before the engine can see it; the half-up
rule matches ``money.round_half_up`` so the two agree on ties.

Imports stay inside ``plans/ARCHITECTURE.md`` §3: ``profit`` and the standard
library.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from arbitrageiq import profit

#: Units a what-if covers when the caller does not say.
SIMULATION_UNITS = 100

#: A ceiling that keeps one request cheap. It is a guard rail of our own, not a
#: rule from the plan: nothing in ``plans/BUSINESS_RULES.md`` caps a batch size.
SIMULATION_UNITS_MAX = 100_000


def returned_units(units: int, returns_rate: Decimal) -> int:
    """Turn a returns rate into whole units, rounding half up.

    The route has already checked that the rate is within ``[0, 1]``, so the
    result cannot exceed the batch.
    """
    return int((returns_rate * units).to_integral_value(rounding=ROUND_HALF_UP))


def line_input(
    *,
    sku: str,
    units: int,
    returns_rate: Decimal,
    price: Decimal,
    landed_unit_cost: Decimal,
    ads_per_unit: Decimal,
) -> profit.LineInput:
    """Build the engine input for one simulated batch.

    Ad spend is entered per unit and scaled to the batch here, deliberately
    unrounded: ``BUSINESS_RULES.md`` §4 rounds money once, at the end of the
    line, and ``LineInput.ads_cost`` is a whole-line figure.
    """
    return profit.LineInput(
        sku=sku,
        units_sold=units,
        returned_units=returned_units(units, returns_rate),
        selling_price=price,
        landed_unit_cost=landed_unit_cost,
        ads_cost=ads_per_unit * units,
    )
