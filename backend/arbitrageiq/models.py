"""SQLAlchemy table definitions for ArbitrageIQ (task T08).

Source of truth for every column, key and nullability in this module:

- ``plans/ARCHITECTURE.md`` §5 — the ERD (six tables).
- ``plans/DECISIONS.md`` ADR-006 — money is never a binary float, and
  ``plans/BUSINESS_RULES.md`` §9 — every sum happens in Python over already
  rounded ``Decimal`` line values, never in SQL.
- ``plans/DECISIONS.md`` ADR-008 — ``transactions.units_sold`` is GROSS units
  shipped, i.e. it includes returned units.
- ``plans/ACCEPTANCE_TESTS.md`` AT-6.5 — every money column reflects as
  ``NUMERIC`` and never ``REAL``.

Money and rate columns carry separate declared scales, because they are not the
same kind of quantity. A rupee amount is ``NUMERIC(18, 2)``: one paisa is the
smallest unit the plan ever names. A fractional rate is ``NUMERIC(18, 6)``,
because ``plans/BUSINESS_RULES.md`` §2 stores TCS as ``0.005`` and TDS as
``0.001``; at two decimal places those read back as ``0.01`` and ``0.00``, which
is the wrong rate rather than a rounding preference. Both remain declared
``NUMERIC`` and never ``REAL``, which is what AT-6.5 asserts; the physical
storage class and the deliberate no-SQL-aggregate rule are recorded as DEV-13
in ``plans/PROGRESS.md``.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)

#: Every rupee column. Never ``REAL``, never ``FLOAT`` (ADR-006).
MONEY = Numeric(18, 2)

#: Every fractional-rate column — a fraction of a price, not an amount. Never
#: ``REAL``, never ``FLOAT`` (ADR-006). Six places hold TCS 0.005 and TDS 0.001.
RATE = Numeric(18, 6)

_metadata = MetaData()


class Base:
    """Namespace so ``Base.metadata`` holds every table (AT-6.5)."""

    metadata = _metadata


metadata = _metadata


products = Table(
    "products",
    metadata,
    Column("sku", String(64), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("category", String(80), nullable=False),
    Column("supplier_unit_cost", MONEY, nullable=False),
    Column("inbound_unit_cost", MONEY, nullable=False),
    Column("packaging_unit_cost", MONEY, nullable=False),
    Column("target_price", MONEY, nullable=False),
    Column("current_stock", Integer, nullable=False),
    Column("min_order_qty", Integer, nullable=False),
    Column("max_supply", Integer, nullable=False),
    #: Optional; retained per ADR-021, unused in P0.
    Column("cost_updated_on", Date, nullable=True),
)


import_batches = Table(
    "import_batches",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("filename", String(260), nullable=False),
    #: Unique: this is what makes a repeat import idempotent (ARCHITECTURE §5).
    Column("content_hash", String(64), nullable=False, unique=True),
    Column("row_count", Integer, nullable=False),
    Column("rejected_count", Integer, nullable=False),
    Column("kind", String(32), nullable=False),
    Column("created_at", Date, nullable=False),
)


transactions = Table(
    "transactions",
    metadata,
    Column("transaction_id", String(64), primary_key=True),
    Column("order_date", Date, nullable=False),
    Column("sku", String(64), ForeignKey("products.sku"), nullable=False),
    #: GROSS units shipped, including any returned unit (ADR-008).
    Column("units_sold", Integer, nullable=False),
    Column("returned_units", Integer, nullable=False),
    Column("selling_price", MONEY, nullable=False),
    Column("discount_per_unit", MONEY, nullable=False),
    Column("refund_per_returned_unit", MONEY, nullable=True),
    Column("settlement_fees_total", MONEY, nullable=True),
    Column("ads_cost", MONEY, nullable=False),
    Column("other_charges", MONEY, nullable=False),
    Column("import_batch_id", Integer, ForeignKey("import_batches.id"), nullable=True),
)


#: Append-mostly: a change creates a new dated row; exactly one is active per date.
fee_assumptions = Table(
    "fee_assumptions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("effective_from", Date, nullable=False),
    Column("referral_rate", RATE, nullable=False),
    Column("zero_referral_below", MONEY, nullable=False),
    Column("closing_fee", MONEY, nullable=False),
    Column("shipping_fee", MONEY, nullable=False),
    Column("fulfilment_fee", MONEY, nullable=False),
    Column("product_gst_rate", RATE, nullable=False),
    Column("gst_on_fees_rate", RATE, nullable=False),
    Column("fee_gst_recoverable", Boolean, nullable=False),
    Column("tcs_rate", RATE, nullable=False),
    Column("tds_rate", RATE, nullable=False),
    Column("default_sell_through", RATE, nullable=False),
    Column("default_salvage", RATE, nullable=False),
    Column("default_budget", MONEY, nullable=False),
    Column("default_max_share_per_sku", RATE, nullable=False),
    Column("note", Text, nullable=False),
)


#: Written by /budget/simulate only when the caller asks to save (T11, T12).
budget_plan_runs = Table(
    "budget_plan_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", Date, nullable=False),
    Column("budget", MONEY, nullable=False),
    Column("sell_through", RATE, nullable=False),
    Column("salvage", RATE, nullable=False),
    Column("max_share_per_sku", RATE, nullable=False),
    Column("strategy", String(64), nullable=False),
    Column("scenario", String(64), nullable=False),
)


budget_plan_lines = Table(
    "budget_plan_lines",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, ForeignKey("budget_plan_runs.id"), nullable=False),
    Column("sku", String(64), ForeignKey("products.sku"), nullable=False),
    Column("qty", Integer, nullable=False),
    Column("capital", MONEY, nullable=False),
    Column("expected_contribution", MONEY, nullable=False),
)


#: The six ERD tables, in dependency order, for callers that need the list.
TABLES = (
    products,
    import_batches,
    transactions,
    fee_assumptions,
    budget_plan_runs,
    budget_plan_lines,
)
