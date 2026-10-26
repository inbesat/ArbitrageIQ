"""Per-SKU and portfolio reconciliation (task T09).

``plans/BUSINESS_RULES.md`` §9 is the rule this module implements:

- per SKU, sum the **already-rounded** per-line contributions;
- the portfolio total is the exact sum of the SKU totals.

Nothing is rounded here. ``profit.compute_line`` halves-up once at the end of each
transaction line (§4 step 12), so every value this module adds is already 2 dp and
re-rounding a subtotal would violate the letter of "never round at the end of an
aggregate" (ADR-010, AT-6.2, AT-6.3).

The active assumptions are read from the ``fee_assumptions`` table and selected by
``config.active_assumptions`` — never reconstructed from ``FeeAssumptions()``
defaults, so a dated change to the stored record changes every figure derived from
it. An empty table is allowed to raise ``LookupError`` rather than fall back.

Imports: ``profit``, ``config``, ``models`` and the standard library. Never
``api``, and never ``validation`` (``plans/ARCHITECTURE.md`` §3 — recording is not
this module's job).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, select

from arbitrageiq import config, models, profit

_ZERO = Decimal("0.00")

_MONEY_KEYS = (
    "selling_price",
    "discount_per_unit",
    "refund_per_returned_unit",
    "settlement_fees_total",
    "ads_cost",
    "other_charges",
)


def _money(row: Mapping[str, Any], key: str) -> Decimal | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str) and value.strip() == "":
        return None
    return Decimal(str(value))


def line_input_from_row(row: Mapping[str, Any], *, landed_unit_cost: Decimal) -> profit.LineInput:
    """Build a ``LineInput`` from a transaction row plus the product's landed cost.

    Landed cost (``L`` = supplier + inbound + packaging) belongs to the product, so
    the caller supplies it; every other input is a column of the transaction.
    """
    return profit.LineInput(
        sku=str(row["sku"]),
        transaction_id=None if row.get("transaction_id") is None else str(row["transaction_id"]),
        units_sold=int(row["units_sold"]),
        returned_units=int(row["returned_units"]),
        selling_price=_money(row, "selling_price") or _ZERO,
        landed_unit_cost=landed_unit_cost,
        discount_per_unit=_money(row, "discount_per_unit") or _ZERO,
        refund_per_returned_unit=_money(row, "refund_per_returned_unit"),
        ads_cost=_money(row, "ads_cost") or _ZERO,
        other_charges=_money(row, "other_charges") or _ZERO,
        settlement_fees_total=_money(row, "settlement_fees_total"),
    )


def line_contribution(line: profit.LineInput, assumptions: config.FeeAssumptions) -> Decimal:
    """The already-rounded contribution of one line (§4 step 12)."""
    return profit.compute_line(line, assumptions).contribution


def _assumptions_from_row(row: Mapping[str, Any]) -> config.FeeAssumptions:
    fields = {key: value for key, value in row.items() if key != "id"}
    return config.FeeAssumptions(**fields)


def reconcile(engine: Engine) -> dict[str, Any]:
    """Sum already-rounded line contributions per SKU, then across SKUs.

    Returns ``per_sku`` (``dict[str, Decimal]``), ``portfolio_total`` (``Decimal``),
    ``portfolio_net_revenue`` and ``portfolio_capital_at_cost`` (both ``Decimal``),
    and the ``assumptions`` record that produced them.

    The last two were added by T14 so the Overview can show the figures
    ``plans/PHASES_DETAILED.md`` §T14 asks for. Both are exact sums of values that
    ``profit.compute_line`` already rounded once per line, so nothing here is
    re-rounded (§9, ADR-010) and no existing figure changes.
    """
    with engine.connect() as connection:
        product_rows = connection.execute(select(models.products)).mappings().all()
        transaction_rows = connection.execute(select(models.transactions)).mappings().all()
        assumption_rows = connection.execute(select(models.fee_assumptions)).mappings().all()

    # Raises LookupError when nothing is effective yet: a fallback to the demo
    # defaults would silently attribute real figures to assumptions nobody stored.
    assumptions = config.active_assumptions([_assumptions_from_row(row) for row in assumption_rows])

    landed_cost = {
        str(row["sku"]): (
            row["supplier_unit_cost"] + row["inbound_unit_cost"] + row["packaging_unit_cost"]
        )
        for row in product_rows
    }

    per_sku: dict[str, Decimal] = {}
    net_revenue = _ZERO
    capital_at_cost = _ZERO
    for row in transaction_rows:
        line = line_input_from_row(row, landed_unit_cost=landed_cost[str(row["sku"])])
        breakdown = profit.compute_line(line, assumptions)
        per_sku[line.sku] = per_sku.get(line.sku, _ZERO) + breakdown.contribution
        net_revenue += breakdown.net_revenue
        capital_at_cost += breakdown.product_cost

    return {
        "per_sku": per_sku,
        "portfolio_total": sum(per_sku.values(), _ZERO),
        "portfolio_net_revenue": net_revenue,
        "portfolio_capital_at_cost": capital_at_cost,
        "assumptions": assumptions,
    }
