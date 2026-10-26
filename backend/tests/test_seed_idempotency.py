"""Seeding twice is safe (T09; audit F06).

``python -m arbitrageiq.db seed`` loads the synthetic sample from ``data/sample/``.
Running it a second time must not fail, must not duplicate a row, and must not
overwrite a row that is already there: the fixture is a convenience, and anything
the operator has since changed is theirs (``plans/SECURITY.md`` §4.1).

The expected counts are the fixture's own row counts, which
``plans/ACCEPTANCE_TESTS.md`` AT-6.4 fixes at ten products and forty transactions.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, func, insert, select, update

from arbitrageiq import db, models

#: AT-6.4 — the synthetic fixture is ten products and forty transactions.
PRODUCTS = 10
TRANSACTIONS = 40


def _engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'seed.db').as_posix()}")
    db.init(engine)
    return engine


def _count(engine, table) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def _price(engine, sku: str) -> Decimal:
    with engine.connect() as connection:
        return connection.execute(
            select(models.products.c.target_price).where(models.products.c.sku == sku)
        ).scalar_one()


def test_seeding_twice_does_not_fail_and_does_not_duplicate(tmp_path):
    engine = _engine(tmp_path)

    first = db.seed(engine)
    second = db.seed(engine)

    assert first["inserted"] == {
        "products": PRODUCTS,
        "transactions": TRANSACTIONS,
        "fee_assumptions": 1,
    }
    assert second["inserted"] == {
        "products": 0,
        "transactions": 0,
        "fee_assumptions": 0,
    }
    assert second["products"] == PRODUCTS
    assert second["transactions"] == TRANSACTIONS
    assert second["fee_assumptions"] == 1
    assert _count(engine, models.products) == PRODUCTS
    assert _count(engine, models.transactions) == TRANSACTIONS
    assert _count(engine, models.fee_assumptions) == 1


def test_seeding_twice_keeps_an_edited_price(tmp_path):
    engine = _engine(tmp_path)
    db.seed(engine)
    with engine.begin() as connection:
        connection.execute(
            update(models.products)
            .where(models.products.c.sku == "TIFFIN-3")
            .values(target_price=Decimal("999.99"))
        )

    db.seed(engine)

    assert _price(engine, "TIFFIN-3") == Decimal("999.99")


def test_seed_inserts_only_the_rows_that_are_missing(tmp_path):
    """A half-loaded database is topped up, not replaced."""
    engine = _engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            insert(models.products),
            [
                {
                    "sku": "TIFFIN-3",
                    "name": "Already here",
                    "category": "Kitchenware",
                    "supplier_unit_cost": Decimal("1.00"),
                    "inbound_unit_cost": Decimal("0.00"),
                    "packaging_unit_cost": Decimal("0.00"),
                    "target_price": Decimal("5.00"),
                    "current_stock": 1,
                    "min_order_qty": 1,
                    "max_supply": 1,
                    "cost_updated_on": date(2026, 1, 1),
                }
            ],
        )

    summary = db.seed(engine)

    assert summary["inserted"]["products"] == PRODUCTS - 1
    assert summary["products"] == PRODUCTS
    assert _price(engine, "TIFFIN-3") == Decimal("5.00")


def test_seeding_twice_keeps_one_assumptions_row(tmp_path):
    engine = _engine(tmp_path)

    db.seed(engine)
    db.seed(engine)

    assert _count(engine, models.fee_assumptions) == 1
