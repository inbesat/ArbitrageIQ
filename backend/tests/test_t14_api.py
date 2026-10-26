"""Tests for the three backend surfaces T14 added (PROGRESS.md §8 DEV-30).

T14 owns four frontend files plus one `App.tsx` edit. Its done condition,
however, needs two things the wire did not carry, so this slice made three
additive backend changes and they are asserted here:

1. `reconcile.reconcile` / `GET /profit/reconcile` now also report
   `portfolio_net_revenue` and `portfolio_capital_at_cost` (the Overview needs
   them and the frontend may not compute money).
2. `POST /api/v1/import/sample` exposes the already-tested
   `loaders.import_sample` so the Import view's one-click sample load and
   AT-10.2's action can run.
3. `frontend/vite.config.ts` gained a dev-only `/api` proxy (not testable from
   Python; it is proved by the browser pass instead).

Every expected value is copied from the golden fixture in
`plans/BUSINESS_RULES.md` §10 — never from the implementation under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from arbitrageiq import db, models
from arbitrageiq.api import app, get_engine
from arbitrageiq.config import FeeAssumptions
from arbitrageiq.loaders import SAMPLE_FILES

BASE = "/api/v1"

PRODUCT_HEADER = (
    "sku,name,category,supplier_unit_cost,inbound_unit_cost,packaging_unit_cost,"
    "target_price,current_stock,min_order_qty,max_supply,cost_updated_on"
)
TRANSACTION_HEADER = (
    "transaction_id,sku,order_date,units_sold,returned_units,selling_price,"
    "discount_per_unit,refund_per_returned_unit,settlement_fees_total,ads_cost,other_charges"
)

#: The golden fixture v1 (plans/BUSINESS_RULES.md §10.1): landed 490 + 5 + 5 =
#: 500.00, one line of 10 shipped and 1 returned at 1180.00 with 200.00 of ads.
GOLDEN_PRODUCTS = (
    PRODUCT_HEADER
    + "\n"
    + "GOLDEN-V1,Golden Fixture v1,festive,490.00,5.00,5.00,1180.00,10,1,100,\n"
).encode()
GOLDEN_TRANSACTIONS = (
    TRANSACTION_HEADER + "\n" + "G00001,GOLDEN-V1,2026-09-15,10,1,1180.00,0.00,,,200.00,0.00\n"
).encode()


def _engine(tmp_path: Path):
    return create_engine(f"sqlite:///{(tmp_path / 't14.db').as_posix()}")


def _fresh_engine(tmp_path: Path):
    """Schema plus one default assumptions row; no products, no transactions."""
    engine = _engine(tmp_path)
    db.init(engine)
    with engine.begin() as connection:
        connection.execute(insert(models.fee_assumptions), [FeeAssumptions().__dict__])
    return engine


def _client(tmp_path: Path) -> TestClient:
    engine = _fresh_engine(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app, raise_server_exceptions=False)


def _csv(header: str, *rows: str) -> bytes:
    return ("\n".join((header, *rows)) + "\n").encode()


def _import(client: TestClient, payload: bytes, *, kind: str) -> dict:
    response = client.post(
        f"{BASE}/import",
        files={"file": ("t.csv", payload, "text/csv")},
        data={"kind": kind},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _sample(client: TestClient, kind: str):
    return client.post(f"{BASE}/import/sample", json={"kind": kind})


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# --- the reconcile additions (Overview's net revenue and capital at cost) ----


def test_reconcile_reports_net_revenue_and_capital_at_cost(tmp_path):
    client = _client(tmp_path)
    _import(client, GOLDEN_PRODUCTS, kind="products")
    _import(client, GOLDEN_TRANSACTIONS, kind="transactions")

    body = client.get(f"{BASE}/profit/reconcile").json()

    # AT-8.8's original fields must be untouched by the addition.
    assert body["per_sku"] == {"GOLDEN-V1": "1624.08"}
    assert body["portfolio_total"] == "1624.08"
    # The golden line: net revenue 9000.00, product cost 10 x 500.00 = 5000.00.
    assert body["portfolio_net_revenue"] == "9000.00"
    assert body["portfolio_capital_at_cost"] == "5000.00"
    # Money stays a decimal string, never a JSON number (ADR-024).
    for key in ("portfolio_total", "portfolio_net_revenue", "portfolio_capital_at_cost"):
        assert isinstance(body[key], str), key


def test_reconcile_reports_zeroes_on_an_empty_portfolio(tmp_path):
    body = _client(tmp_path).get(f"{BASE}/profit/reconcile").json()

    assert body["portfolio_net_revenue"] == "0.00"
    assert body["portfolio_capital_at_cost"] == "0.00"


# --- POST /import/sample ----------------------------------------------------


def test_import_sample_serves_both_fixtures_and_is_idempotent(tmp_path):
    client = _client(tmp_path)

    catalogue = _sample(client, "products")
    assert catalogue.status_code == 200, catalogue.text
    first = catalogue.json()
    expected_products = sum(1 for _ in SAMPLE_FILES["products"].read_text().splitlines()) - 1
    assert first["imported"] == expected_products
    assert first["skipped"] == 0

    # The route returns the same shape as POST /import, so one summary renders both.
    assert set(first) == {"imported", "skipped", "rejected_total", "rejected"}
    assert isinstance(first["rejected"], list)

    # Loading it a second time changes nothing (the content hash is the arbiter).
    again = _sample(client, "products").json()
    assert again["imported"] == 0
    assert again["skipped"] == expected_products

    # Only now can transactions land, because an unknown SKU is rejected.
    sold = _sample(client, "transactions").json()
    assert sold["imported"] > 0


def test_import_sample_rejects_an_unknown_kind_with_422(tmp_path):
    response = _sample(_client(tmp_path), "invoices")

    assert response.status_code == 422, response.text
    body = response.json()
    assert set(body) <= {"error", "detail", "field"}
    assert set(body) >= {"error", "detail"}
    assert body["field"] == "kind", body


def test_import_sample_transactions_before_the_catalogue_are_all_rejected(tmp_path):
    """AT-5.14's referential check is unconditional, so ordering matters."""
    body = _sample(_client(tmp_path), "transactions").json()

    assert body["imported"] == 0
    assert body["rejected_total"] > 0
    assert body["rejected"], "each rejected row must be reported"
    assert set(body["rejected"][0]) == {"row", "field", "value", "reason"}
