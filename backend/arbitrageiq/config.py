"""The dated, validated assumption set every financial calculation reads (task T03).

Source of truth: ``plans/BUSINESS_RULES.md`` §2 — the assumption table (key, type,
default, unit) and rules R1-R4. Nothing here is a market rate: every default is an
illustrative fixture (R1) and :data:`ILLUSTRATIVE_NOTE` says so.

Plain ``@dataclass(frozen=True)`` with ``Decimal`` fields, no Pydantic: ``config``
is allowed to import ``money`` plus the standard library only
(``plans/PHASES_DETAILED.md`` §T03, ``plans/ARCHITECTURE.md`` §3). ``money`` is not
needed yet, because validation only compares ``Decimal`` values against literal
bounds and does no monetary arithmetic.

TCS and TDS are withholding credits, never costs (R3). ``fee_gst_recoverable``
defaults to the conservative ``False`` (R4): GST on fees is treated as a cost unless
an input-tax credit is genuinely claimable, which this tool cannot determine.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

#: Required fallback wording when no better source is known (``BUSINESS_RULES.md`` §2, R1).
ILLUSTRATIVE_NOTE = "ILLUSTRATIVE DEMO ASSUMPTION"

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _validate_rate(name: str, value: Decimal) -> None:
    if not _ZERO <= value <= _ONE:
        raise ValueError(f"{name} must be in [0, 1], got {value}")


def _validate_non_negative(name: str, value: Decimal) -> None:
    if value < _ZERO:
        raise ValueError(f"{name} must be >= 0, got {value}")


def _validate_share(name: str, value: Decimal) -> None:
    if not _ZERO < value <= _ONE:
        raise ValueError(f"{name} must be in (0, 1], got {value}")


@dataclass(frozen=True)
class FeeAssumptions:
    """One dated assumption record (``plans/BUSINESS_RULES.md`` §2)."""

    referral_rate: Decimal = Decimal("0.08")
    zero_referral_below: Decimal = Decimal("1000.00")
    closing_fee: Decimal = Decimal("25.00")
    shipping_fee: Decimal = Decimal("65.00")
    fulfilment_fee: Decimal = Decimal("0.00")
    product_gst_rate: Decimal = Decimal("0.18")
    gst_on_fees_rate: Decimal = Decimal("0.18")
    fee_gst_recoverable: bool = False
    tcs_rate: Decimal = Decimal("0.005")
    tds_rate: Decimal = Decimal("0.001")
    default_sell_through: Decimal = Decimal("0.80")
    default_salvage: Decimal = Decimal("0.50")
    default_budget: Decimal = Decimal("50000.00")
    default_max_share_per_sku: Decimal = Decimal("0.40")
    effective_from: date = field(default_factory=date.today)
    note: str = ILLUSTRATIVE_NOTE

    def __post_init__(self) -> None:
        """R2: rates in [0, 1], fees and budget >= 0, the concentration cap in (0, 1]."""
        _validate_rate("referral_rate", self.referral_rate)
        _validate_rate("product_gst_rate", self.product_gst_rate)
        _validate_rate("gst_on_fees_rate", self.gst_on_fees_rate)
        _validate_rate("tcs_rate", self.tcs_rate)
        _validate_rate("tds_rate", self.tds_rate)
        _validate_rate("default_sell_through", self.default_sell_through)
        _validate_rate("default_salvage", self.default_salvage)
        _validate_non_negative("closing_fee", self.closing_fee)
        _validate_non_negative("shipping_fee", self.shipping_fee)
        _validate_non_negative("fulfilment_fee", self.fulfilment_fee)
        _validate_non_negative("default_budget", self.default_budget)
        # R2 does not name this key: it is neither a rate nor a fee nor the budget.
        # It is money, so it follows the "money must be >= 0" half of R2.
        _validate_non_negative("zero_referral_below", self.zero_referral_below)
        _validate_share("default_max_share_per_sku", self.default_max_share_per_sku)


def active_assumptions(records: Sequence[FeeAssumptions], on: date | None = None) -> FeeAssumptions:
    """Return the record effective on ``on`` (default today); the latest start date wins.

    Raises ``LookupError`` when no record has an ``effective_from`` on or before that
    date, because silently falling back to a default would be a wrong assumption.
    """
    as_of = on if on is not None else date.today()
    effective = [record for record in records if record.effective_from <= as_of]
    if not effective:
        raise LookupError(f"no assumptions record has effective_from <= {as_of}")
    return max(effective, key=lambda record: record.effective_from)
