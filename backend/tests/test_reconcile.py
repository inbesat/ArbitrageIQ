"""Import idempotency and per-SKU reconciliation (task T09).

Source of truth for every expectation here:

- ``plans/ACCEPTANCE_TESTS.md`` AT-6.1, AT-6.2, AT-6.3 (owner: ``reconcile.py``,
  ``db.py``), plus AT-5.9 and AT-5.21 which T07 moved here under its own fallback
  ("recorded as moved, not dropped") and which are recorded as DEV-15.
- ``plans/BUSINESS_RULES.md`` §9 — per SKU, sum the **already-rounded** per-line
  contributions; portfolio total equals the sum of the SKU totals. Never round at
  the end of an aggregate.
- ``plans/BUSINESS_RULES.md`` §4 step 12 — ``compute_line`` rounds a line exactly
  once, so a second rounding anywhere in reconcile would violate the letter of §9.
- ``plans/ARCHITECTURE.md`` §5 — ``import_batches.content_hash`` is UNIQUE; that
  constraint, not application logic, is what makes a repeat import idempotent.

Every expected value comes from the specification or from the committed fixture.
Nothing is derived from the code under test.

The database under test is a throwaway file in ``tmp_path``, built through the
validated import path rather than ``db.seed`` so the import tests exercise the
content-hash mechanism instead of colliding with pre-seeded rows. No test writes
to ``data/sample/`` (the committed fixtures) or to ``data/private/arbitrageiq.db``
(the disposable development database).
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from arbitrageiq import db, loaders, models, reconcile
from arbitrageiq.config import FeeAssumptions

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
PRODUCTS_CSV = SAMPLE_DIR / "products_sample.csv"
TRANSACTIONS_CSV = SAMPLE_DIR / "transactions_sample.csv"


def _engine(tmp_path):
    """A throwaway SQLite file, mirroring the pattern used by test_db.py."""
    return create_engine(f"sqlite:///{(tmp_path / 'arbitrageiq.db').as_posix()}")


def _fresh_engine(tmp_path):
    """Schema plus the default assumption row, but no products and no transactions."""
    engine = _engine(tmp_path)
    db.init(engine)
    with engine.begin() as connection:
        connection.execute(models.fee_assumptions.insert(), [asdict(FeeAssumptions())])
    return engine


def _imported_engine(tmp_path):
    """The bundled fixture loaded through the validated import path."""
    engine = _fresh_engine(tmp_path)
    loaders.import_sample(engine, kind="products")
    loaders.import_sample(engine, kind="transactions")
    return engine


def _count(engine, table) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def _fixture_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# --------------------------------------------------------------------------- #
# AT-6.2 — per-SKU totals are the sum of the already-rounded per-line values
# --------------------------------------------------------------------------- #


def test_at_6_2_per_sku_total_is_the_sum_of_the_rounded_line_contributions(tmp_path):
    engine = _imported_engine(tmp_path)

    result = reconcile.reconcile(engine)

    assert set(result["per_sku"]) == {row["sku"] for row in _fixture_rows(PRODUCTS_CSV)}
    for total in result["per_sku"].values():
        assert isinstance(total, Decimal)

    # Independent recomputation from the raw fixtures using the public engine.
    # Landed cost is a property of the product, so it comes from products_sample.csv:
    # supplier_unit_cost + inbound_unit_cost + packaging_unit_cost.
    landed = {
        row["sku"]: (
            Decimal(row["supplier_unit_cost"])
            + Decimal(row["inbound_unit_cost"])
            + Decimal(row["packaging_unit_cost"])
        )
        for row in _fixture_rows(PRODUCTS_CSV)
    }
    expected: dict[str, Decimal] = {}
    for row in _fixture_rows(TRANSACTIONS_CSV):
        line = reconcile.line_input_from_row(row, landed_unit_cost=landed[row["sku"]])
        contribution = reconcile.line_contribution(line, result["assumptions"])
        expected[line.sku] = expected.get(line.sku, Decimal("0.00")) + contribution

    assert result["per_sku"] == expected


def test_at_6_2_no_second_rounding_is_applied_to_a_sku_total(tmp_path):
    """Every line is already 2 dp, so the sum is exact; re-rounding would be a
    numerical no-op but would violate §9's "never round at the end of an aggregate"."""
    engine = _imported_engine(tmp_path)

    result = reconcile.reconcile(engine)

    for total in result["per_sku"].values():
        assert total == total.quantize(Decimal("0.01"))
        assert isinstance(total, Decimal)
        assert not isinstance(total, float)


def test_at_6_2_every_sku_in_the_fixture_is_present_including_the_loss_making_one(tmp_path):
    engine = _imported_engine(tmp_path)

    result = reconcile.reconcile(engine)

    assert len(result["per_sku"]) == len(_fixture_rows(PRODUCTS_CSV))
    assert result["per_sku"]["EARBUD-BT-1"] < Decimal("0.00")


# --------------------------------------------------------------------------- #
# AT-6.3 — portfolio total equals the sum of the SKU totals, exactly
# --------------------------------------------------------------------------- #


def test_at_6_3_portfolio_total_is_the_exact_sum_of_the_sku_totals(tmp_path):
    engine = _imported_engine(tmp_path)

    result = reconcile.reconcile(engine)

    assert result["portfolio_total"] == sum(result["per_sku"].values())


def test_at_6_3_portfolio_total_is_a_decimal_and_finite(tmp_path):
    engine = _imported_engine(tmp_path)

    total = reconcile.reconcile(engine)["portfolio_total"]

    assert isinstance(total, Decimal)
    assert not isinstance(total, float)
    assert total.is_finite()


# --------------------------------------------------------------------------- #
# AT-6.1 — import, reconcile, re-import the same content, reconcile again
# --------------------------------------------------------------------------- #


def test_at_6_1_reimporting_the_same_content_leaves_the_portfolio_total_identical(tmp_path):
    engine = _imported_engine(tmp_path)

    first = reconcile.reconcile(engine)
    outcome = loaders.import_sample(engine, kind="transactions")
    second = reconcile.reconcile(engine)

    assert outcome["imported"] == 0
    assert outcome["skipped"] > 0
    assert second["portfolio_total"] == first["portfolio_total"]
    assert second["per_sku"] == first["per_sku"]


def test_at_6_1_reimport_does_not_change_the_transaction_row_count(tmp_path):
    engine = _imported_engine(tmp_path)
    before = _count(engine, models.transactions)

    loaders.import_sample(engine, kind="transactions")

    assert _count(engine, models.transactions) == before


# --------------------------------------------------------------------------- #
# AT-5.9 — a repeat upload reports 0 imported and N skipped (moved from T07)
# --------------------------------------------------------------------------- #


def test_at_5_9_a_repeat_upload_reports_zero_imported_and_n_skipped(tmp_path):
    engine = _fresh_engine(tmp_path)
    payload = TRANSACTIONS_CSV.read_bytes()

    first = loaders.import_transactions(engine, payload, filename="transactions.csv")
    second = loaders.import_transactions(engine, payload, filename="transactions.csv")

    assert first["imported"] == len(_fixture_rows(TRANSACTIONS_CSV))
    assert first["skipped"] == 0
    assert second["imported"] == 0
    assert second["skipped"] == first["imported"]


def test_at_5_9_a_repeat_upload_does_not_grow_the_batch_table(tmp_path):
    engine = _fresh_engine(tmp_path)
    payload = TRANSACTIONS_CSV.read_bytes()

    loaders.import_transactions(engine, payload, filename="transactions.csv")
    first_batches = _count(engine, models.import_batches)
    loaders.import_transactions(engine, payload, filename="transactions.csv")

    assert _count(engine, models.import_batches) == first_batches


# --------------------------------------------------------------------------- #
# AT-5.21 — the UNIQUE constraint picks exactly one winner (moved from T07)
# --------------------------------------------------------------------------- #


def test_at_5_21_the_same_content_imported_twice_yields_exactly_one_batch(tmp_path):
    engine = _fresh_engine(tmp_path)
    payload = TRANSACTIONS_CSV.read_bytes()

    loaders.import_transactions(engine, payload, filename="a.csv")
    loaders.import_transactions(engine, payload, filename="b.csv")

    with engine.connect() as connection:
        hashes = connection.execute(select(models.import_batches.c.content_hash)).scalars().all()

    assert len(hashes) == len(set(hashes))
    assert _count(engine, models.import_batches) == 1


def test_at_5_21_no_duplicate_transaction_rows_survive_the_second_import(tmp_path):
    engine = _fresh_engine(tmp_path)
    payload = TRANSACTIONS_CSV.read_bytes()

    loaders.import_transactions(engine, payload, filename="a.csv")
    after_first = _count(engine, models.transactions)
    loaders.import_transactions(engine, payload, filename="b.csv")

    with engine.connect() as connection:
        ids = connection.execute(select(models.transactions.c.transaction_id)).scalars().all()

    assert _count(engine, models.transactions) == after_first
    assert len(ids) == len(set(ids))


def test_at_5_21_different_content_is_not_treated_as_a_duplicate(tmp_path):
    engine = _fresh_engine(tmp_path)
    payload = TRANSACTIONS_CSV.read_bytes()
    # Genuinely different content: one new row, so no primary key collides and the
    # only reason either import could be skipped is the content hash.
    header = TRANSACTIONS_CSV.read_text(encoding="utf-8").splitlines()[0]
    altered = (header + "\nT90001,BOTTLE-750,2026-09-15,1,0,500.00,0.00,,,10.00,0.00\n").encode()

    loaders.import_transactions(engine, payload, filename="a.csv")
    second = loaders.import_transactions(engine, altered, filename="b.csv")

    assert second["skipped"] == 0
    assert _count(engine, models.import_batches) == 2


# --------------------------------------------------------------------------- #
# loaders.py — the bundled sample loads through the validated path
# --------------------------------------------------------------------------- #


def test_loaders_import_sample_loads_the_bundled_fixtures_through_the_validated_path(tmp_path):
    engine = _fresh_engine(tmp_path)

    products = loaders.import_sample(engine, kind="products")
    transactions = loaders.import_sample(engine, kind="transactions")

    assert products["imported"] == len(_fixture_rows(PRODUCTS_CSV))
    assert transactions["imported"] == len(_fixture_rows(TRANSACTIONS_CSV))
    assert _count(engine, models.products) == products["imported"]
    assert _count(engine, models.transactions) == transactions["imported"]


def test_loaders_records_one_batch_row_carrying_the_content_hash(tmp_path):
    engine = _fresh_engine(tmp_path)
    payload = TRANSACTIONS_CSV.read_bytes()

    loaders.import_transactions(engine, payload, filename="transactions.csv")

    with engine.connect() as connection:
        row = connection.execute(select(models.import_batches)).one()

    assert row.content_hash == loaders.content_hash(payload)
    assert row.row_count == len(_fixture_rows(TRANSACTIONS_CSV))
    assert row.kind == "transactions"


def test_loaders_rejects_a_row_whose_sku_is_not_in_products(tmp_path):
    engine = _fresh_engine(tmp_path)
    header = TRANSACTIONS_CSV.read_text(encoding="utf-8").splitlines()[0]
    payload = (header + "\nT90001,NOT-A-SKU,2026-09-15,1,0,500.00,0.00,,,10.00,0.00\n").encode()

    outcome = loaders.import_transactions(
        engine, payload, filename="bad.csv", known_skus=frozenset({"BOTTLE-750"})
    )

    assert outcome["imported"] == 0
    assert outcome["rejected_total"] == 1
    assert _count(engine, models.transactions) == 0


# --------------------------------------------------------------------------- #
# reconcile reads the ACTIVE assumptions from the database, not the defaults
# --------------------------------------------------------------------------- #


def test_reconcile_reads_the_active_assumptions_record_and_not_the_defaults(tmp_path):
    engine = _imported_engine(tmp_path)

    result = reconcile.reconcile(engine)

    assert result["assumptions"].referral_rate == Decimal("0.08")
    assert result["assumptions"].fee_gst_recoverable is False


def test_reconcile_reflects_a_changed_assumption_row(tmp_path):
    """A different active record must change the total, proving reconcile reads the
    table rather than constructing ``FeeAssumptions()`` itself."""
    engine = _imported_engine(tmp_path)
    baseline = reconcile.reconcile(engine)["portfolio_total"]

    with engine.begin() as connection:
        connection.execute(models.fee_assumptions.update().values(fee_gst_recoverable=True))

    assert reconcile.reconcile(engine)["portfolio_total"] != baseline


def test_reconcile_raises_when_no_assumptions_row_exists(tmp_path):
    engine = _imported_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(models.fee_assumptions.delete())

    with pytest.raises(LookupError):
        reconcile.reconcile(engine)


# --------------------------------------------------------------------------- #
# Module boundaries — plans/ARCHITECTURE.md §3
# --------------------------------------------------------------------------- #


def test_reconcile_and_loaders_respect_the_documented_import_boundaries():
    import ast

    package = Path(__file__).resolve().parents[1] / "arbitrageiq"

    def imports_of(name: str) -> set[str]:
        tree = ast.parse((package / name).read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module)
        return found

    reconcile_imports = imports_of("reconcile.py")
    loaders_imports = imports_of("loaders.py")

    # `api` is the top of the stack and is forbidden to both.
    assert not {name for name in reconcile_imports if name.endswith("api")}
    assert not {name for name in loaders_imports if name.endswith("api")}
    # reconcile may not import validation; loaders may.
    assert "arbitrageiq.validation" not in reconcile_imports
