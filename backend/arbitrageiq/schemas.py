"""Request and response schemas for the REST API (tasks T10 and T12).

Every monetary and ratio value crosses the wire as a decimal **string**, never
a JSON number (``plans/DECISIONS.md`` ADR-024; ``plans/ACCEPTANCE_TESTS.md``
AT-8.12). Accepted request bodies keep money as strings too, so a
GET -> PUT round trip is lossless.

This module imports ``pydantic`` and the standard library only
(``plans/ARCHITECTURE.md`` §3): it must never import ``config``, ``db`` or
``api``, which is why the payload builders take plain mappings rather than a
``FeeAssumptions`` instance.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from arbitrageiq.money import round_half_up

#: The 14 configurable assumption keys that hold a Decimal
#: (``plans/BUSINESS_RULES.md`` §2).
ASSUMPTION_MONEY_KEYS = (
    "referral_rate",
    "zero_referral_below",
    "closing_fee",
    "shipping_fee",
    "fulfilment_fee",
    "product_gst_rate",
    "gst_on_fees_rate",
    "tcs_rate",
    "tds_rate",
    "default_sell_through",
    "default_salvage",
    "default_budget",
    "default_max_share_per_sku",
)

#: The four Decimal columns of a product row.
PRODUCT_MONEY_KEYS = (
    "supplier_unit_cost",
    "inbound_unit_cost",
    "packaging_unit_cost",
    "target_price",
)

#: Every monetary or ratio field of a contribution line, including the three
#: derived ratios that render the literal ``"n/a"`` (``BUSINESS_RULES.md`` §8).
BREAKDOWN_MONEY_KEYS = (
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
    "profit_per_unit",
    "margin_pct",
    "roi_pct",
)


def money_text(value: object) -> str | None:
    """Serialise one monetary value as a 2-dp decimal string.

    The three ratio fields carry the literal ``"n/a"`` and pass through. Money is
    normalised to two decimal places so an unrounded per-unit intermediate such
    as ``referral_fee`` (``p * referral_rate``) cannot leak extra scale onto the
    wire. This is a presentation normalisation, never a second rounding of a sum
    (``plans/BUSINESS_RULES.md`` §9): every value that feeds a total was already
    rounded once at its line end.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        return str(round_half_up(value))
    return str(value)


def raw_text(value: object) -> str | None:
    """Serialise a stored assumption value exactly as recorded.

    Rates keep their declared scale (``tcs_rate`` is ``0.005``), so this must not
    quantise (``plans/BUSINESS_RULES.md`` §2).
    """
    return None if value is None else str(value)


class AssumptionUpdate(BaseModel):
    """The writable assumption set: §2's keys plus ``effective_from`` and ``note``.

    Values are strings so the request mirrors the response exactly; the range
    rules in R2 are applied when the record is built, not here.
    """

    model_config = ConfigDict(extra="forbid")

    referral_rate: str
    zero_referral_below: str
    closing_fee: str
    shipping_fee: str
    fulfilment_fee: str
    product_gst_rate: str
    gst_on_fees_rate: str
    fee_gst_recoverable: bool
    tcs_rate: str
    tds_rate: str
    default_sell_through: str
    default_salvage: str
    default_budget: str
    default_max_share_per_sku: str
    effective_from: str
    note: str = ""


class SimulateRequest(BaseModel):
    """Body of ``POST /budget/simulate`` (``plans/ARCHITECTURE.md`` §4.3).

    Every control is optional and falls back to the active assumption's
    ``default_*`` value; ``skus`` selects a subset of the catalogue and ``None``
    means the whole catalogue. Money and ratios are strings, mirroring the
    response. There is no scenario selector: the response always carries both
    base and conservative (``plans/PHASES_DETAILED.md`` §T12).
    """

    model_config = ConfigDict(extra="allow")

    budget: str | None = None
    sell_through: str | None = None
    salvage: str | None = None
    max_share_per_sku: str | None = None
    skus: list[str] | None = None


class SampleRequest(BaseModel):
    """Body of ``POST /import/sample`` (task T14).

    ``kind`` selects which bundled synthetic fixture to load; the route serves only
    the two keys ``loaders.SAMPLE_FILES`` knows, so anything else is a 422.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str


class SimulateSkuRequest(BaseModel):
    """Body of ``POST /simulate/sku`` (deviation DEV-39).

    A what-if over one SKU: the caller types the terms and the batch size, and
    the response is *the same* calculation an imported line goes through
    (``plans/BUSINESS_RULES.md`` §4), never a second formula.

    ``price`` and ``landed_unit_cost`` are required; the rest fall back — the
    rates and fees to the active assumptions, the returns rate and ad spend to
    zero, the batch to the module default. Whoever sends the body echoes the
    effective values back, so nothing is hidden. Every value is a string or an
    integer; no money crosses as a JSON number.
    """

    model_config = ConfigDict(extra="forbid")

    price: str
    landed_unit_cost: str
    referral_rate: str | None = None
    closing_fee: str | None = None
    returns_rate: str | None = None
    ads_per_unit: str | None = None
    units: int | None = None
    sku: str | None = None


def assumption_payload(values: Mapping[str, Any]) -> dict[str, Any]:
    """Render one assumption record as the wire object."""
    payload: dict[str, Any] = {key: raw_text(values[key]) for key in ASSUMPTION_MONEY_KEYS}
    payload["fee_gst_recoverable"] = bool(values["fee_gst_recoverable"])
    payload["effective_from"] = str(values["effective_from"])
    payload["note"] = str(values.get("note") or "")
    return payload


def product_payload(values: Mapping[str, Any]) -> dict[str, Any]:
    """Render one product row as the wire object."""
    payload: dict[str, Any] = {
        "sku": str(values["sku"]),
        "name": str(values["name"]),
        "category": str(values["category"]),
    }
    for key in PRODUCT_MONEY_KEYS:
        payload[key] = money_text(values[key])
    payload["current_stock"] = int(values["current_stock"])
    payload["min_order_qty"] = int(values["min_order_qty"])
    payload["max_supply"] = int(values["max_supply"])
    updated = values.get("cost_updated_on")
    payload["cost_updated_on"] = None if updated is None else str(updated)
    return payload


def breakdown_payload(breakdown: Any) -> dict[str, Any]:
    """Render one contribution line (``profit.LineBreakdown``) as the wire object."""
    payload: dict[str, Any] = {
        "transaction_id": breakdown.transaction_id,
        "sku": breakdown.sku,
        "net_units": int(breakdown.net_units),
        "fee_source": str(breakdown.fee_source),
    }
    for key in BREAKDOWN_MONEY_KEYS:
        payload[key] = money_text(getattr(breakdown, key))
    return payload


def rejection_payload(rejection: Any) -> dict[str, Any]:
    """Render one rejected CSV row as ``{row, field, value, reason}``."""
    return {
        "row": int(rejection.row),
        "field": str(rejection.field),
        "value": money_text(rejection.value),
        "reason": str(rejection.reason),
    }


#: Every monetary or ratio field of a budget simulation response.
BUDGET_MONEY_KEYS = (
    "budget",
    "sell_through",
    "salvage",
    "max_share_per_sku",
    "capital_used",
    "budget_remaining",
    "expected_contribution",
    "capital",
)

#: The ``plans/BUSINESS_RULES.md`` §11.3 honesty statement, verbatim. A uniform
#: downside shock cannot show diversification's benefit, so this text travels
#: with every simulation (``plans/PHASES_DETAILED.md`` §T12).
UNIFORM_SHOCK_DISCLOSURE = (
    "A uniform downside shock cannot demonstrate the main benefit of diversification. "
    "Because every SKU is stressed equally, a diversified plan can score worse in the "
    "conservative scenario than a concentrated one, even though it is genuinely more "
    "resilient to a product-specific failure such as a supplier default, a stock-out, or "
    "a listing suspension. The scenario is a stress test of price and sell-through, not "
    "proof of diversification."
)


#: The basis note that travels with every ``POST /simulate/sku`` response
#: (deviation DEV-39). The endpoint is arithmetic on the numbers the caller
#: typed, using the same rules as an imported line — it is not a forecast and
#: not advice, and the wording says so on the wire rather than only in the UI.
SIMULATION_BASIS = (
    "This is a what-if over the units and terms entered here, using the same contribution "
    "rules as every imported line: returned units are written off, marketplace fees are "
    "charged on the units shipped, and GST on those fees is treated as a cost. It is "
    "arithmetic on your inputs, not a forecast of sales and not a recommendation."
)


def plan_line_payload(line: Any) -> dict[str, Any]:
    """Render one allocated line as ``allocator.PlanLine`` -> wire object."""
    return {
        "sku": str(line.sku),
        "qty": int(line.qty),
        "capital": money_text(line.capital),
        "expected_contribution": money_text(line.expected_contribution),
        "assumed": bool(line.assumed),
    }


def plan_payload(plan: Any) -> dict[str, Any]:
    """Render one ``allocator.Plan`` as the wire object.

    ``score`` is deliberately withheld: no acceptance row and no `PRD.md` §4.4
    bullet needs it, and the 2-dp money formatter would collapse distinct scores.
    """
    return {
        "strategy": str(plan.strategy),
        "label": str(plan.label),
        "capital_used": money_text(plan.capital_used),
        "budget_remaining": money_text(plan.budget_remaining),
        "expected_contribution": money_text(plan.expected_contribution),
        "lines": [plan_line_payload(line) for line in plan.lines],
    }


def allocation_payload(
    allocation: Any,
    *,
    budget: object,
    sell_through: object,
    salvage: object,
    max_share_per_sku: object,
) -> dict[str, Any]:
    """Render a whole ``POST /budget/simulate`` response.

    ``allocator.allocate`` returns each scenario as ``(Plan A, Plan B)``.
    """
    return {
        "budget": money_text(budget),
        "sell_through": money_text(sell_through),
        "salvage": money_text(salvage),
        "max_share_per_sku": money_text(max_share_per_sku),
        "base": {
            "plan_a": plan_payload(allocation.base[0]),
            "plan_b": plan_payload(allocation.base[1]),
        },
        "conservative": {
            "plan_a": plan_payload(allocation.conservative[0]),
            "plan_b": plan_payload(allocation.conservative[1]),
        },
        "disclosure": UNIFORM_SHOCK_DISCLOSURE,
    }


def simulation_payload(
    breakdown: Any,
    *,
    assumptions_values: Mapping[str, Any],
    inputs: Mapping[str, Any],
    units: int,
) -> dict[str, Any]:
    """Render a whole ``POST /simulate/sku`` response.

    ``inputs`` is echoed so the caller can see every term that was used rather
    than only the two required ones, and ``assumptions`` is echoed so the rates
    that were *not* overridden are visible too. ``returned_units`` is derived
    from the breakdown's ``net_units`` rather than recomputed, so the response
    can never disagree with the line it describes.
    """
    return {
        "units": int(units),
        "returned_units": int(units) - int(breakdown.net_units),
        "inputs": {key: money_text(value) for key, value in inputs.items()},
        "assumptions": assumption_payload(assumptions_values),
        "line": breakdown_payload(breakdown),
        "basis": SIMULATION_BASIS,
    }
