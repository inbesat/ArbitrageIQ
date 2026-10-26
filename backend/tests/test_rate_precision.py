"""Persisted fractional rates keep their declared precision (T08; audit F01).

``plans/BUSINESS_RULES.md`` §2 stores fractional rates well below one — TCS is
``0.005`` and TDS is ``0.001`` — and ``plans/ACCEPTANCE_TESTS.md`` AT-6.5 requires
the value read back from SQLite to be a bit-identical ``Decimal`` with a declared
``NUMERIC`` column. A column declared with two decimal places cannot hold either
of those: it reads back as ``0.01`` and ``0.00``.

Every expected value here is copied from ``plans/BUSINESS_RULES.md`` §2, never
derived from the code under test (``AGENTS.md`` rule 3).
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from arbitrageiq import db, models
from arbitrageiq.api import app, get_engine
from arbitrageiq.config import FeeAssumptions

BASE = "/api/v1"

#: ``BUSINESS_RULES.md`` §2 — each fractional rate and the exact text it must survive as.
RATES = {
    "referral_rate": "0.08",
    "product_gst_rate": "0.18",
    "gst_on_fees_rate": "0.18",
    "tcs_rate": "0.005",
    "tds_rate": "0.001",
    "default_sell_through": "0.80",
    "default_salvage": "0.50",
    "default_max_share_per_sku": "0.40",
}

#: ``BUSINESS_RULES.md`` §2 — rupee columns keep two places, unchanged by this fix.
MONEY = {
    "zero_referral_below": "1000.00",
    "closing_fee": "25.00",
    "shipping_fee": "65.00",
    "default_budget": "50000.00",
}


def _db_path(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'rates.db').as_posix()}"


def _seeded(tmp_path: Path, *, effective_from: date | None = None):
    """A fresh SQLite file with one assumptions row, as ``db seed`` would write it."""
    engine = create_engine(_db_path(tmp_path))
    db.init(engine)
    values = FeeAssumptions().__dict__
    if effective_from is not None:
        values = values | {"effective_from": effective_from}
    with engine.begin() as connection:
        connection.execute(insert(models.fee_assumptions), [values])
    return engine


def _client(tmp_path: Path) -> TestClient:
    engine = _seeded(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_rates_survive_the_database_read(tmp_path):
    engine = _seeded(tmp_path)

    with engine.connect() as connection:
        row = connection.execute(select(models.fee_assumptions)).mappings().one()

    for column, expected in RATES.items():
        assert row[column] == Decimal(expected), column


def test_rates_survive_a_restart_with_a_new_engine(tmp_path):
    _seeded(tmp_path).dispose()

    reopened = create_engine(_db_path(tmp_path))
    with reopened.connect() as connection:
        row = connection.execute(select(models.fee_assumptions)).mappings().one()

    for column, expected in RATES.items():
        assert row[column] == Decimal(expected), column


def test_the_stored_text_keeps_three_decimal_places(tmp_path):
    """The value is stored, not merely re-rounded on the way out."""
    _seeded(tmp_path).dispose()

    connection = sqlite3.connect(tmp_path / "rates.db")
    try:
        row = connection.execute("SELECT tcs_rate, tds_rate FROM fee_assumptions").fetchone()
    finally:
        connection.close()

    assert str(row[0]) == "0.005"
    assert str(row[1]) == "0.001"


def test_money_columns_still_round_trip_at_two_places(tmp_path):
    engine = _seeded(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            insert(models.products),
            [
                {
                    "sku": "RATE-TEST",
                    "name": "Rate test",
                    "category": "Test",
                    "supplier_unit_cost": Decimal("10.01"),
                    "inbound_unit_cost": Decimal("1234.56"),
                    "packaging_unit_cost": Decimal("0.00"),
                    "target_price": Decimal("20.00"),
                    "current_stock": 1,
                    "min_order_qty": 1,
                    "max_supply": 1,
                }
            ],
        )

    with engine.connect() as connection:
        row = (
            connection.execute(select(models.products).where(models.products.c.sku == "RATE-TEST"))
            .mappings()
            .one()
        )

    assert str(row["supplier_unit_cost"]) == "10.01"
    assert str(row["inbound_unit_cost"]) == "1234.56"


def test_at_8_2_get_assumptions_returns_every_rate_exactly(tmp_path):
    body = _client(tmp_path).get(f"{BASE}/assumptions").json()

    for column, expected in RATES.items():
        assert body[column] == expected, column
    for column, expected in MONEY.items():
        assert body[column] == expected, column


def test_at_8_3_put_then_get_keeps_a_sub_cent_rate(tmp_path):
    """A rate finer than a cent survives the write and the read that follows it."""
    old = _seeded(tmp_path, effective_from=date(2026, 1, 1))
    app.dependency_overrides[get_engine] = lambda: old
    client = TestClient(app, raise_server_exceptions=False)

    payload = client.get(f"{BASE}/assumptions").json()
    payload["tcs_rate"] = "0.0025"
    payload["tds_rate"] = "0.0015"
    payload["effective_from"] = date.today().isoformat()

    response = client.put(f"{BASE}/assumptions", json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["tcs_rate"] == "0.0025"
    assert response.json()["tds_rate"] == "0.0015"
    active = client.get(f"{BASE}/assumptions").json()
    assert active["tcs_rate"] == "0.0025"
    assert active["tds_rate"] == "0.0015"
