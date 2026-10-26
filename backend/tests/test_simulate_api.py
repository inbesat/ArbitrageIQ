"""Acceptance coverage for ``POST /api/v1/simulate/sku`` (DEV-39).

The endpoint is a what-if over one SKU at terms the caller types. It is *not*
part of the nine P0 operations, so no ``AT-n`` row names it; what these tests
pin is that it reuses ``profit.compute_line`` unchanged and honours the same
money rules as every imported line:

* ``plans/BUSINESS_RULES.md`` §4 — the per-transaction order of operations.
  The expected values below were worked out by hand from that section, not
  read back from the function under test.
* §7 — TCS and TDS are cash-flow credits, never costs, so they never appear in
  a subtraction.
* ADR-024 / AT-8.12 — every money value crosses the wire as a decimal string.

The live-server E2E step is still unrunnable on this machine (D-1: ``uvicorn``
raises ``OSError: [WinError 10014]`` under Python 3.14.2), so the request is
driven through the in-process ``TestClient``.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from arbitrageiq import db, loaders, models, schemas
from arbitrageiq.api import app, get_engine
from arbitrageiq.config import FeeAssumptions

BASE = "/api/v1"
SAMPLE_CATALOGUE = Path(__file__).resolve().parents[2] / "data" / "sample" / "products_sample.csv"

FORBIDDEN_IN_RESPONSE = ("Traceback", 'File "', "SELECT", "INSERT", "sqlite", "C:\\", "E:\\")
BANNED_CLAIMS = ("optimal", "best", "maximis", "guaranteed", "predicted sale")

#: Every field a money rule governs, so a stray float would be caught here.
MONEY_FIELDS = (
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


def _client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{(tmp_path / 'simulate.db').as_posix()}")
    db.init(engine)
    with engine.begin() as connection:
        connection.execute(insert(models.fee_assumptions), [FeeAssumptions().__dict__])
    loaders.import_products(engine, SAMPLE_CATALOGUE.read_bytes(), filename=SAMPLE_CATALOGUE.name)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _post(client: TestClient, **body):
    return client.post(f"{BASE}/simulate/sku", json=body)


def test_simulation_follows_rules_order_and_returns_decimal_strings(tmp_path: Path):
    """100 units at 500.00, landed 300.00, 10% back, 20.00 ads per unit.

    Hand-computed from ``BUSINESS_RULES.md`` §4 with the shipped defaults
    (referral 0.08, floor 1000.00, closing 25.00, shipping 65.00, GST 0.18 on
    both the product and the fees, fee GST not recoverable):

    ex-GST unit price = 500.00 / 1.18 = 423.73; gross = 42,373.00;
    refunds = 4,237.30; net = 38,135.70; 500.00 is under the 1,000.00 floor so
    referral is nil and fees are (25.00 + 65.00) x 100 = 9,000.00, GST 1,620.00;
    cost 30,000.00; ads 2,000.00; contribution = -4,484.30.
    """
    client = _client(tmp_path)
    response = _post(
        client,
        sku="TIFFIN-3",
        price="500.00",
        landed_unit_cost="300.00",
        referral_rate="0.08",
        closing_fee="25.00",
        returns_rate="0.10",
        ads_per_unit="20.00",
        units=100,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    line = body["line"]

    assert body["units"] == 100
    assert body["returned_units"] == 10
    assert line["sku"] == "TIFFIN-3"
    assert line["net_units"] == 90
    assert line["fee_source"] == "model"

    assert line["price_paid"] == "500.00"
    assert line["ex_gst_unit_price"] == "423.73"
    assert line["gross_revenue"] == "42373.00"
    assert line["refunds"] == "4237.30"
    assert line["net_revenue"] == "38135.70"
    assert line["referral_fee"] == "0.00"
    assert line["fees_ex_gst"] == "9000.00"
    assert line["fee_gst"] == "1620.00"
    assert line["product_cost"] == "30000.00"
    assert line["ads"] == "2000.00"
    assert line["other_charges"] == "0.00"
    assert line["contribution"] == "-4484.30"
    assert line["profit_per_unit"] == "-49.83"
    assert line["margin_pct"] == "-11.76"
    assert line["roi_pct"] == "-14.95"

    for field in MONEY_FIELDS:
        assert isinstance(line[field], str), f"{field} must cross the wire as a string"
    assert "0.005" not in body["line"]["contribution"]


def test_omitted_controls_fall_back_to_the_active_assumptions(tmp_path: Path):
    """Only price, landed cost and units are required.

    Above the referral floor the fee model charges 8%, so the referral branch is
    reachable: 1,500.00 x 0.08 = 120.00, fees (120.00 + 25.00 + 65.00) x 10 =
    2,100.00, GST 378.00, ex-GST 1,271.19, gross 12,711.90, cost 9,000.00,
    contribution 1,233.90.
    """
    client = _client(tmp_path)
    response = _post(
        client, sku="TORAN-FLW-1", price="1500.00", landed_unit_cost="900.00", units=10
    )

    assert response.status_code == 200, response.text
    body = response.json()
    line = body["line"]

    assert body["returned_units"] == 0
    assert line["referral_fee"] == "120.00"
    assert line["ex_gst_unit_price"] == "1271.19"
    assert line["gross_revenue"] == "12711.90"
    assert line["fees_ex_gst"] == "2100.00"
    assert line["fee_gst"] == "378.00"
    assert line["product_cost"] == "9000.00"
    assert line["ads"] == "0.00"
    assert line["contribution"] == "1233.90"
    assert line["profit_per_unit"] == "123.39"
    assert line["margin_pct"] == "9.71"
    assert line["roi_pct"] == "13.71"

    # The rates actually used are echoed back, so nothing is hidden.
    assert body["inputs"]["referral_rate"] == "0.08"
    assert body["inputs"]["closing_fee"] == "25.00"
    assert body["inputs"]["returns_rate"] == "0.00"
    assert body["inputs"]["ads_per_unit"] == "0.00"
    assert body["assumptions"]["closing_fee"] == "25.00"
    assert body["assumptions"]["fee_gst_recoverable"] is False


def test_batch_defaults_and_basis_note(tmp_path: Path):
    """A missing batch size means 100 units, and the response says what it is."""
    client = _client(tmp_path)
    response = _post(client, price="500.00", landed_unit_cost="300.00")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["units"] == 100
    assert body["basis"] == schemas.SIMULATION_BASIS
    assert "not a forecast" in body["basis"]
    assert "not a recommendation" in body["basis"]


@pytest.mark.parametrize(
    "body,field",
    [
        ({"landed_unit_cost": "300.00"}, "price"),
        ({"price": "500.00"}, "landed_unit_cost"),
        ({"price": "banana", "landed_unit_cost": "300.00"}, "price"),
        ({"price": "500.00", "landed_unit_cost": "NaN"}, "landed_unit_cost"),
        ({"price": "-1.00", "landed_unit_cost": "300.00"}, "price"),
        ({"price": "500.00", "landed_unit_cost": "-1.00"}, "landed_unit_cost"),
        ({"price": "500.00", "landed_unit_cost": "300.00", "returns_rate": "1.5"}, "returns_rate"),
        (
            {"price": "500.00", "landed_unit_cost": "300.00", "referral_rate": "-0.1"},
            "referral_rate",
        ),
        ({"price": "500.00", "landed_unit_cost": "300.00", "referral_rate": "2"}, "referral_rate"),
        ({"price": "500.00", "landed_unit_cost": "300.00", "closing_fee": "-25.00"}, "closing_fee"),
        (
            {"price": "500.00", "landed_unit_cost": "300.00", "ads_per_unit": "-1.00"},
            "ads_per_unit",
        ),
        ({"price": "500.00", "landed_unit_cost": "300.00", "units": 0}, "units"),
        ({"price": "500.00", "landed_unit_cost": "300.00", "units": 10_000_000}, "units"),
    ],
)
def test_rejects_unusable_input_on_the_offending_field(tmp_path: Path, body, field):
    """Every rejection names the field and leaks nothing about the internals."""
    client = _client(tmp_path)
    response = _post(client, **body)

    assert response.status_code == 422, response.text
    payload = response.json()
    assert payload["error"] == "validation_failed"
    assert payload["field"] == field
    assert payload["detail"], "a rejection must say, in plain English, what is wrong"

    text = response.text
    for needle in FORBIDDEN_IN_RESPONSE:
        assert needle not in text, f"response leaked {needle!r}"
    lowered = text.lower()
    for claim in BANNED_CLAIMS:
        assert claim not in lowered, f"response made a banned claim: {claim!r}"


def test_unknown_body_keys_are_refused(tmp_path: Path):
    """``extra="forbid"`` keeps a typo from being silently ignored."""
    client = _client(tmp_path)
    response = _post(client, price="500.00", landed_unit_cost="300.00", sell_through="0.8")

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "validation_failed"
