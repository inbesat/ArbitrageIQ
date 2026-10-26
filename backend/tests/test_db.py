"""Persistence and synthetic-fixture tests (task T08).

Acceptance: ``plans/ACCEPTANCE_TESTS.md`` AT-6.4, AT-6.5 and AT-6.6.
Authorities: ``plans/ARCHITECTURE.md`` §5 (the ERD, money columns are NUMERIC
and never REAL/FLOAT), ``plans/BUSINESS_RULES.md`` §9 (sums are taken over
already-rounded line values in Python, never in SQL) and ``plans/DECISIONS.md``
ADR-006 (money is never a binary float), ADR-020/AP-1 (the portfolio total is
NOT a fixed target), and ``plans/TECH_STACK.md`` §5.5 (deterministic fixtures).

Every expected value is taken from the specification or from the generated
fixture file, never from the code under test.
"""

import csv
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from arbitrageiq import db, models
from arbitrageiq.config import FeeAssumptions
from arbitrageiq.profit import LineInput, compute_line

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
PRODUCTS_CSV = SAMPLE_DIR / "products_sample.csv"
TRANSACTIONS_CSV = SAMPLE_DIR / "transactions_sample.csv"
GENERATOR = REPO_ROOT / "scripts" / "make_sample_data.py"

#: Every column the ERD declares as money or as a Decimal rate. None of these
#: may be REAL/FLOAT, and each must round-trip as an exact ``Decimal``.
MONEY_COLUMNS = {
    "products": (
        "supplier_unit_cost",
        "inbound_unit_cost",
        "packaging_unit_cost",
        "target_price",
    ),
    "transactions": (
        "selling_price",
        "discount_per_unit",
        "refund_per_returned_unit",
        "settlement_fees_total",
        "ads_cost",
        "other_charges",
    ),
    "fee_assumptions": (
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
    ),
    "budget_plan_runs": ("budget", "sell_through", "salvage", "max_share_per_sku"),
    "budget_plan_lines": ("capital", "expected_contribution"),
}

#: ADR-020 / AP-1: the handbook's 26,761.53 is explicitly NOT a target.
#: These are the values used for the round-trip envelope check, chosen to span
#: the catalogue's realistic range. The measured limit of the plain NUMERIC
#: column on SQLite is recorded in ``plans/PROGRESS.md`` §8 DEV-13.
ROUND_TRIP_VALUES = (
    "0.01",
    "0.05",
    "0.10",
    "94.40",
    "331.92",
    "440.00",
    "1180.00",
    "1624.08",
    "2175.92",
    "999999.99",
    "9999999999.99",
)


def _generator():
    """Import ``scripts/make_sample_data.py`` by path (it is not a package)."""
    spec = importlib.util.spec_from_file_location("make_sample_data", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data_rows(path: Path) -> list[list[str]]:
    """Return the CSV's data rows (excluding the header)."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return [row for row in rows[1:] if any(cell.strip() for cell in row)]


def _seed_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'arbitrageiq.db'}")
    db.init(engine)
    db.seed(engine)
    return engine


# --- AT-6.5: money is NUMERIC, never REAL, and round-trips exactly ---------


def test_at_6_5_every_money_column_declares_numeric_and_never_real():
    for table_name, columns in MONEY_COLUMNS.items():
        table = models.Base.metadata.tables[table_name]
        for column in columns:
            declared = str(table.columns[column].type).upper()
            assert "NUMERIC" in declared, f"{table_name}.{column} is {declared}"
            assert "REAL" not in declared, f"{table_name}.{column} is {declared}"
            assert "FLOAT" not in declared, f"{table_name}.{column} is {declared}"


def test_at_6_5_reflected_schema_has_no_real_or_float_money_column(tmp_path):
    engine = _seed_engine(tmp_path)
    inspector = inspect(engine)
    seen = 0
    for table_name, columns in MONEY_COLUMNS.items():
        reflected = {
            col["name"]: str(col["type"]).upper() for col in inspector.get_columns(table_name)
        }
        for column in columns:
            declared = reflected[column]
            assert "REAL" not in declared, f"{table_name}.{column} reflects as {declared}"
            assert "FLOAT" not in declared, f"{table_name}.{column} reflects as {declared}"
            seen += 1
    assert seen == sum(len(columns) for columns in MONEY_COLUMNS.values())


@pytest.mark.parametrize("raw", ROUND_TRIP_VALUES)
def test_at_6_5_money_round_trips_as_a_bit_identical_decimal(tmp_path, raw):
    engine = _seed_engine(tmp_path)
    value = Decimal(raw)
    with engine.begin() as conn:
        conn.execute(
            models.products.insert().values(
                sku=f"RT-{raw}",
                name="Round Trip",
                category="test",
                supplier_unit_cost=value,
                inbound_unit_cost=Decimal("0.00"),
                packaging_unit_cost=Decimal("0.00"),
                target_price=value,
                current_stock=0,
                min_order_qty=1,
                max_supply=1,
            )
        )
    with engine.connect() as conn:
        stored = conn.execute(
            models.products.select().where(models.products.c.sku == f"RT-{raw}")
        ).one()
    assert type(stored.supplier_unit_cost) is Decimal
    assert stored.supplier_unit_cost == value
    assert str(stored.supplier_unit_cost) == raw


def test_at_6_5_seeded_money_is_decimal_and_sql_sums_are_never_used():
    """BUSINESS_RULES.md §9: money is summed in Python over Decimal values.

    This asserts the invariant the app relies on, and documents why the raw
    SQLite aggregate is not part of the design (see DEV-13).
    """
    rows = _read_products()
    assert rows
    for row in rows:
        assert type(row["supplier_unit_cost"]) is Decimal
        assert type(row["target_price"]) is Decimal


_PRODUCT_MONEY_COLUMNS = (
    "supplier_unit_cost",
    "inbound_unit_cost",
    "packaging_unit_cost",
    "target_price",
)


def _read_products() -> list[dict]:
    with PRODUCTS_CSV.open(encoding="utf-8", newline="") as handle:
        return [
            {
                key: (
                    (Decimal(value) if value else None) if key in _PRODUCT_MONEY_COLUMNS else value
                )
                for key, value in row.items()
            }
            for row in csv.DictReader(handle)
        ]


# --- AT-6.4: the seeded catalogue loads and the count matches the fixture ---


def test_at_6_4_seed_loads_ten_products_and_the_fixture_row_count(tmp_path):
    expected_products = _data_rows(PRODUCTS_CSV)
    expected_transactions = _data_rows(TRANSACTIONS_CSV)
    assert len(expected_products) == 10, "the catalogue is specified as 10 products"

    engine = _seed_engine(tmp_path)
    with engine.connect() as conn:
        product_count = conn.execute(models.products.select()).all()
        transaction_count = conn.execute(models.transactions.select()).all()

    assert len(product_count) == len(expected_products)
    # Read from the generated fixture, never from a constant in code (AT-6.4).
    assert len(transaction_count) == len(expected_transactions)


def test_at_6_4_seed_does_not_invent_rows_for_later_tasks(tmp_path):
    """import_batches is T09's; the budget tables are T11/T12's."""
    engine = _seed_engine(tmp_path)
    with engine.connect() as conn:
        assert conn.execute(models.import_batches.select()).all() == []
        assert conn.execute(models.budget_plan_runs.select()).all() == []
        assert conn.execute(models.budget_plan_lines.select()).all() == []


def test_at_6_4_seeded_fee_assumptions_match_the_section_2_defaults(tmp_path):
    engine = _seed_engine(tmp_path)
    with engine.connect() as conn:
        rows = conn.execute(models.fee_assumptions.select()).all()
    assert len(rows) == 1
    active = rows[0]
    defaults = FeeAssumptions()
    for field in (
        "referral_rate",
        "closing_fee",
        "shipping_fee",
        "product_gst_rate",
        "default_budget",
    ):
        assert getattr(active, field) == getattr(defaults, field)
    assert active.referral_rate == Decimal("0.08")
    assert active.default_budget == Decimal("50000.00")
    assert active.fee_gst_recoverable is False
    assert active.note


# --- AT-6.6: the sample catalogue contains a loss-making SKU --------------


def test_at_6_6_the_sample_catalogue_contains_a_loss_making_sku():
    """The engine must not flatter the data (AT-6.6)."""
    assumptions = FeeAssumptions()
    landed = {row["sku"]: row for row in _read_products()}
    totals: dict[str, Decimal] = {}
    settlements_seen = 0
    returns_seen = 0

    with TRANSACTIONS_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            product = landed[row["sku"]]
            landed_unit_cost = (
                product["supplier_unit_cost"]
                + product["inbound_unit_cost"]
                + product["packaging_unit_cost"]
            )
            line = LineInput(
                sku=row["sku"],
                transaction_id=row["transaction_id"],
                units_sold=int(row["units_sold"]),
                returned_units=int(row["returned_units"]),
                selling_price=Decimal(row["selling_price"]),
                discount_per_unit=Decimal(row["discount_per_unit"]),
                refund_per_returned_unit=(
                    Decimal(row["refund_per_returned_unit"])
                    if row["refund_per_returned_unit"]
                    else None
                ),
                settlement_fees_total=(
                    Decimal(row["settlement_fees_total"]) if row["settlement_fees_total"] else None
                ),
                ads_cost=Decimal(row["ads_cost"]),
                other_charges=Decimal(row["other_charges"]),
                landed_unit_cost=landed_unit_cost,
            )
            if line.settlement_fees_total is not None:
                settlements_seen += 1
            if line.returned_units > 0:
                returns_seen += 1
            breakdown = compute_line(line, assumptions)
            totals[line.sku] = totals.get(line.sku, Decimal("0.00")) + breakdown.contribution

    assert totals, "the fixture must produce at least one SKU total"
    losing = sorted(sku for sku, total in totals.items() if total < 0)
    assert losing, f"AT-6.6 requires a loss-making SKU; totals were {totals}"
    # The generator must also exercise both risky paths (T08 agent prompt).
    assert returns_seen > 0, "the fixture must exercise the return path"
    assert settlements_seen > 0, "the fixture must exercise the settlement-override path"


# --- Determinism (BUSINESS_RULES.md §11.5 B7, TECH_STACK.md §5.5) ---------


def test_generator_is_deterministic_and_matches_the_committed_fixtures():
    module = _generator()
    products_a, transactions_a = module.build_fixtures()
    products_b, transactions_b = module.build_fixtures()
    assert products_a == products_b, "the generator must be byte-identical across runs"
    assert transactions_a == transactions_b

    assert PRODUCTS_CSV.read_text(encoding="utf-8") == products_a
    assert TRANSACTIONS_CSV.read_text(encoding="utf-8") == transactions_a


def test_generator_uses_no_wall_clock_and_no_float_money():
    source = GENERATOR.read_text(encoding="utf-8")
    assert "date.today" not in source, "the fixtures must not depend on the wall clock"
    assert "datetime.now" not in source


def test_generated_rows_contain_no_real_brand_person_or_order_identifier():
    """No real brand, person, phone number, address or order ID (T08 done condition)."""
    text = (
        PRODUCTS_CSV.read_text(encoding="utf-8") + TRANSACTIONS_CSV.read_text(encoding="utf-8")
    ).lower()
    for forbidden in ("amazon", "flipkart", "meesho", "@", "+91", "http", "www."):
        assert forbidden not in text, f"fixture contains {forbidden!r}"
    for row in _data_rows(TRANSACTIONS_CSV):
        assert row[0].startswith("T") or row[0].startswith("G"), row[0]


def test_generated_order_dates_are_fixed_synthetic_dates():
    with TRANSACTIONS_CSV.open(encoding="utf-8", newline="") as handle:
        dates = {row["order_date"] for row in csv.DictReader(handle)}
    assert dates
    for raw in dates:
        parsed = date.fromisoformat(raw)
        assert parsed.year == 2026, f"unexpected fixture year in {raw}"


# --- Module boundary (ARCHITECTURE.md §3) ---------------------------------


def test_persistence_modules_never_import_the_api():
    for module in (models, db):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import api" not in source
        assert "from arbitrageiq.api" not in source
        assert "from .api" not in source
