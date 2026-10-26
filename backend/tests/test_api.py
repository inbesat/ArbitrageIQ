"""T10 acceptance tests: the REST API contract (`plans/ACCEPTANCE_TESTS.md` AT-8).

Every expected value below is copied from `plans/ACCEPTANCE_TESTS.md` AT-8 or
from the golden fixture in `plans/BUSINESS_RULES.md` §10 — never from the
implementation under test (§10.4.2).

Scope notes, stated so nothing is over-claimed:

- **AT-8.9 is NOT claimed here.** `POST /budget/simulate` was a 501 stub while
  T10 ran (`plans/PHASES_DETAILED.md` §T10 permits that here and only here; T12
  removes it), so the budget happy path and its three 422 cases are asserted in
  `test_budget_api.py` instead (T12, DEV-23).
- **AT-8.12 is claimed over the payloads that exist**: `/health`,
  `/assumptions`, `/products`, `/import`, `/profit/sku/{sku}` and
  `/profit/reconcile`. The budget payload carries its own string-not-float
  assertion in `test_budget_api.py`, over its own keys.
- **AT-5.22** (no filesystem path, SQL text or traceback in any response) is
  asserted across every response this file produces.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, insert, select

from arbitrageiq import db, models
from arbitrageiq.api import app, get_engine
from arbitrageiq.config import FeeAssumptions

BASE = "/api/v1"

PRODUCT_HEADER = (
    "sku,name,category,supplier_unit_cost,inbound_unit_cost,packaging_unit_cost,"
    "target_price,current_stock,min_order_qty,max_supply,cost_updated_on"
)
TRANSACTION_HEADER = (
    "transaction_id,sku,order_date,units_sold,returned_units,selling_price,"
    "discount_per_unit,refund_per_returned_unit,settlement_fees_total,ads_cost,other_charges"
)

PRODUCT_ROW = "BOTTLE-750,Steel Bottle 750ml,kitchen,440.00,8.00,6.00,799.00,60,12,240,2026-10-01"
TRANSACTION_ROW = "T00001,BOTTLE-750,2026-09-15,10,1,1180.00,0.00,,,200.00,0.00"

#: The golden fixture v1 line, expressed as CSV (plans/BUSINESS_RULES.md §10.1).
#: Landed cost is 490 + 5 + 5 = 500.00 and the assumptions are the §2 defaults,
#: so the single line must reconcile to Decimal("1624.08").
GOLDEN_PRODUCTS = (
    PRODUCT_HEADER
    + "\n"
    + "GOLDEN-V1,Golden Fixture v1,festive,490.00,5.00,5.00,1180.00,10,1,100,\n"
).encode()
GOLDEN_TRANSACTIONS = (
    TRANSACTION_HEADER + "\n" + "G00001,GOLDEN-V1,2026-09-15,10,1,1180.00,0.00,,,200.00,0.00\n"
).encode()

UNKNOWN_SKU = "NO-SUCH-SKU"

#: Tokens that must never appear in a response (AT-5.22).
FORBIDDEN_IN_RESPONSE = (
    "Traceback",
    'File "',
    "SELECT",
    "INSERT",
    "sqlite",
    "C:\\",
    "E:\\",
    "Traceback (most recent call last)",
)


def _csv(header: str, *rows: str) -> bytes:
    return ("\n".join((header, *rows)) + "\n").encode()


def _engine(tmp_path: Path):
    return create_engine(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")


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


def _count(engine, table) -> int:
    with engine.begin() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def _import(client: TestClient, payload: bytes, *, kind: str = "transactions", name: str = "t.csv"):
    return client.post(
        f"{BASE}/import",
        files={"file": (name, payload, "text/csv")},
        data={"kind": kind},
    )


def _assert_no_leak(response) -> None:
    haystack = response.text
    for token in FORBIDDEN_IN_RESPONSE:
        assert token not in haystack, f"response leaked {token!r}: {haystack[:400]}"


def _assert_uniform_error(response, status: int) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert isinstance(body, dict), "an error body must be an object, never a bare string"
    assert set(body) <= {"error", "detail", "field"}, body
    assert set(body) >= {"error", "detail"}, body
    assert isinstance(body["error"], str) and body["error"]
    assert isinstance(body["detail"], str) and body["detail"]
    _assert_no_leak(response)
    return body


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# --- AT-8.1 -----------------------------------------------------------------


def test_at_8_1_health_returns_200_with_status_version_and_db(tmp_path):
    response = _client(tmp_path).get(f"{BASE}/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"status", "version", "db"}
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]
    # The db value is a status word, never a path (AT-5.22).
    assert body["db"] == "reachable"
    _assert_no_leak(response)


def test_at_8_1_health_returns_503_when_the_database_is_unreachable(tmp_path):
    broken = create_engine("sqlite:///Z:/no/such/directory/arbitrageiq.db")
    app.dependency_overrides[get_engine] = lambda: broken

    response = TestClient(app, raise_server_exceptions=False).get(f"{BASE}/health")

    _assert_uniform_error(response, 503)


# --- AT-8.2 / AT-8.3 --------------------------------------------------------


def test_at_8_2_get_assumptions_returns_the_full_object_with_string_money(tmp_path):
    response = _client(tmp_path).get(f"{BASE}/assumptions")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["referral_rate"] == "0.08"
    assert body["zero_referral_below"] == "1000.00"
    assert body["closing_fee"] == "25.00"
    assert body["shipping_fee"] == "65.00"
    assert body["product_gst_rate"] == "0.18"
    assert body["gst_on_fees_rate"] == "0.18"
    assert body["fee_gst_recoverable"] is False
    assert body["tcs_rate"] == "0.005"
    assert body["tds_rate"] == "0.001"
    assert body["default_sell_through"] == "0.80"
    assert body["default_salvage"] == "0.50"
    assert body["default_budget"] == "50000.00"
    assert body["default_max_share_per_sku"] == "0.40"
    assert isinstance(body["effective_from"], str)
    assert body["note"]
    _assert_no_leak(response)


def test_at_8_3_put_assumptions_echoes_the_validated_object(tmp_path):
    client = _client(tmp_path)
    payload = client.get(f"{BASE}/assumptions").json()
    payload["closing_fee"] = "30.00"
    # Keep the date the API served, which is today: that makes this the latest
    # row, and a PUT replaces the row carrying the same effective_from rather
    # than appending a second one (api.py, put_assumptions).
    # DEV-44: this line used to hardcode a date, so once that date passed the
    # PUT wrote a superseded row and the assertion below failed on a correct
    # backend.

    response = client.put(f"{BASE}/assumptions", json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["closing_fee"] == "30.00"
    # And it is now the active row.
    assert client.get(f"{BASE}/assumptions").json()["closing_fee"] == "30.00"
    _assert_no_leak(response)


def test_at_8_3_put_assumptions_rejects_an_out_of_range_rate_with_422(tmp_path):
    client = _client(tmp_path)
    payload = client.get(f"{BASE}/assumptions").json()
    payload["referral_rate"] = "1.50"

    body = _assert_uniform_error(client.put(f"{BASE}/assumptions", json=payload), 422)
    assert "referral_rate" in f"{body.get('field', '')}{body['detail']}"


def test_at_8_3_put_assumptions_rejects_a_negative_fee_with_422(tmp_path):
    client = _client(tmp_path)
    payload = client.get(f"{BASE}/assumptions").json()
    payload["closing_fee"] = "-1.00"

    body = _assert_uniform_error(client.put(f"{BASE}/assumptions", json=payload), 422)
    assert "closing_fee" in f"{body.get('field', '')}{body['detail']}"


# --- AT-8.4 -----------------------------------------------------------------


def test_at_8_4_products_returns_an_empty_list_not_404(tmp_path):
    response = _client(tmp_path).get(f"{BASE}/products")

    assert response.status_code == 200, response.text
    assert response.json() == []
    _assert_no_leak(response)


def test_at_8_4_products_returns_the_catalogue_with_string_money(tmp_path):
    client = _client(tmp_path)
    _import(client, _csv(PRODUCT_HEADER, PRODUCT_ROW), kind="products")

    body = client.get(f"{BASE}/products").json()

    assert len(body) == 1
    assert body[0]["sku"] == "BOTTLE-750"
    assert body[0]["supplier_unit_cost"] == "440.00"
    assert body[0]["target_price"] == "799.00"
    assert isinstance(body[0]["current_stock"], int)


# --- AT-8.5 -----------------------------------------------------------------


def test_at_8_5_validate_is_a_dry_run_that_persists_nothing(tmp_path):
    engine = _fresh_engine(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    client = TestClient(app, raise_server_exceptions=False)
    # AT-5.14 needs the catalogue in place before a transaction can be valid.
    _import(client, _csv(PRODUCT_HEADER, PRODUCT_ROW), kind="products")

    before = (
        _count(engine, models.transactions),
        _count(engine, models.import_batches),
    )
    response = client.post(
        f"{BASE}/import/validate",
        files={"file": ("t.csv", _csv(TRANSACTION_HEADER, TRANSACTION_ROW), "text/csv")},
        data={"kind": "transactions"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 1
    after = (
        _count(engine, models.transactions),
        _count(engine, models.import_batches),
    )
    assert after == before, "the dry run must persist nothing"


def test_at_8_5_validate_rejects_an_oversize_file_with_413(tmp_path):
    payload = b"x" * (5 * 1024 * 1024 + 1)
    response = _client(tmp_path).post(
        f"{BASE}/import/validate",
        files={"file": ("big.csv", payload, "text/csv")},
        data={"kind": "transactions"},
    )

    body = _assert_uniform_error(response, 413)
    assert "size" in body["detail"].lower()


def test_at_8_5_validate_rejects_an_unreadable_file_with_422(tmp_path):
    response = _client(tmp_path).post(
        f"{BASE}/import/validate",
        files={"file": ("bin.csv", b"\x00\x01\x02\xff\xfe", "text/csv")},
        data={"kind": "transactions"},
    )

    _assert_uniform_error(response, 422)


def test_at_8_5_validate_rejects_a_missing_column_with_422_naming_every_one(tmp_path):
    payload = _csv("transaction_id,sku", "T1,BOTTLE-750")
    response = _client(tmp_path).post(
        f"{BASE}/import/validate",
        files={"file": ("t.csv", payload, "text/csv")},
        data={"kind": "transactions"},
    )

    body = _assert_uniform_error(response, 422)
    for missing in ("order_date", "units_sold", "returned_units", "selling_price"):
        assert missing in body["detail"], body["detail"]


# --- AT-8.6 -----------------------------------------------------------------


def test_at_8_6_import_persists_and_reports_imported_skipped_and_rejected(tmp_path):
    client = _client(tmp_path)
    _import(client, _csv(PRODUCT_HEADER, PRODUCT_ROW), kind="products")
    payload = _csv(
        TRANSACTION_HEADER,
        TRANSACTION_ROW,
        "T00002,BOTTLE-750,2026-09-16,2,3,1180.00,0.00,,,0.00,0.00",
    )

    response = _import(client, payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 0
    assert [item["row"] for item in body["rejected"]] == [3]
    assert set(body["rejected"][0]) == {"row", "field", "value", "reason"}
    _assert_no_leak(response)


def test_at_8_6_reimporting_the_same_content_is_idempotent(tmp_path):
    client = _client(tmp_path)
    _import(client, _csv(PRODUCT_HEADER, PRODUCT_ROW), kind="products")
    payload = _csv(TRANSACTION_HEADER, TRANSACTION_ROW)

    first = _import(client, payload)
    second = _import(client, payload)

    assert first.json()["imported"] == 1
    total_after_first = client.get(f"{BASE}/profit/reconcile").json()["portfolio_total"]

    body = second.json()
    assert body["imported"] == 0
    assert body["skipped"] == 1
    assert client.get(f"{BASE}/profit/reconcile").json()["portfolio_total"] == total_after_first


# --- AT-8.7 -----------------------------------------------------------------


def test_at_8_7_profit_for_one_sku_returns_the_golden_breakdown(tmp_path):
    client = _client(tmp_path)
    _import(client, GOLDEN_PRODUCTS, kind="products")
    _import(client, GOLDEN_TRANSACTIONS, kind="transactions")

    response = client.get(f"{BASE}/profit/sku/GOLDEN-V1")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sku"] == "GOLDEN-V1"
    # The anchor, reached through the API rather than through compute_line.
    assert body["totals"]["contribution"] == "1624.08"
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["price_paid"] == "1180.00"
    assert line["ex_gst_unit_price"] == "1000.00"
    assert line["gross_revenue"] == "10000.00"
    assert line["refunds"] == "1000.00"
    assert line["net_revenue"] == "9000.00"
    assert line["referral_fee"] == "94.40"
    assert line["fees_ex_gst"] == "1844.00"
    assert line["fee_gst"] == "331.92"
    assert line["product_cost"] == "5000.00"
    assert line["ads"] == "200.00"
    assert line["contribution"] == "1624.08"
    assert line["profit_per_unit"] == "180.45"
    _assert_no_leak(response)


def test_at_8_7_profit_for_an_unknown_sku_is_404_with_a_clean_body(tmp_path):
    response = _client(tmp_path).get(f"{BASE}/profit/sku/{UNKNOWN_SKU}")

    body = _assert_uniform_error(response, 404)
    assert "Traceback" not in response.text
    assert body["detail"]


# --- AT-8.8 -----------------------------------------------------------------


def test_at_8_8_reconcile_returns_an_empty_state_when_there_are_no_transactions(tmp_path):
    response = _client(tmp_path).get(f"{BASE}/profit/reconcile")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["per_sku"] == {}
    assert body["portfolio_total"] == "0.00"
    _assert_no_leak(response)


def test_at_8_8_reconcile_returns_per_sku_and_portfolio_totals(tmp_path):
    client = _client(tmp_path)
    _import(client, GOLDEN_PRODUCTS, kind="products")
    _import(client, GOLDEN_TRANSACTIONS, kind="transactions")

    body = client.get(f"{BASE}/profit/reconcile").json()

    assert body["per_sku"] == {"GOLDEN-V1": "1624.08"}
    assert body["portfolio_total"] == "1624.08"


# --- AT-8.9 moved to test_budget_api.py (T12) -------------------------------
#
# T10 asserted only that the permitted 501 stub existed. T12 removed the stub, so
# asserting 501 now would contradict the contract; AT-8.9's real outcome is proved
# against the live endpoint in `test_budget_api.py`.


# --- AT-8.10 ----------------------------------------------------------------


def test_at_8_10_every_error_body_is_typed_and_never_a_bare_string(tmp_path):
    client = _client(tmp_path)

    cases = (
        ("get", f"{BASE}/profit/sku/{UNKNOWN_SKU}", None),
        ("put", f"{BASE}/assumptions", {"referral_rate": "9.99"}),
        (
            "post",
            f"{BASE}/import/validate",
            None,
        ),
    )
    for method, url, body in cases:
        if method == "get":
            response = client.get(url)
        elif method == "put":
            response = client.put(url, json=body)
        else:
            response = client.post(
                url,
                files={"file": ("t.csv", b"", "text/csv")},
                data={"kind": "transactions"},
            )
        assert response.status_code >= 400, response.text
        assert isinstance(response.json(), dict), response.text
        assert "error" in response.json(), response.text


# --- AT-8.11 ----------------------------------------------------------------


def test_at_8_11_docs_is_served(tmp_path):
    response = _client(tmp_path).get("/docs")

    assert response.status_code == 200, response.text


def test_at_8_11_the_openapi_schema_lists_every_p0_operation(tmp_path):
    schema = _client(tmp_path).get("/openapi.json").json()
    paths = schema["paths"]

    assert f"{BASE}/health" in paths
    assert f"{BASE}/assumptions" in paths
    assert f"{BASE}/products" in paths
    assert f"{BASE}/import/validate" in paths
    assert f"{BASE}/import" in paths
    assert f"{BASE}/profit/sku/{{sku}}" in paths
    assert f"{BASE}/profit/reconcile" in paths
    assert f"{BASE}/budget/simulate" in paths
    # DELETE /import/{batch_id} is P1 and must not appear.
    assert f"{BASE}/import/{{batch_id}}" not in paths


# --- AT-8.12 ----------------------------------------------------------------

MONEY_KEYS = {
    "supplier_unit_cost",
    "inbound_unit_cost",
    "packaging_unit_cost",
    "target_price",
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
}


def _walk(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, (*path, index))
    else:
        yield path, node


def test_at_8_12_every_money_field_is_a_json_string_never_a_float(tmp_path):
    client = _client(tmp_path)
    _import(client, GOLDEN_PRODUCTS, kind="products")
    _import(client, GOLDEN_TRANSACTIONS, kind="transactions")

    payloads = [
        client.get(f"{BASE}/assumptions").json(),
        client.get(f"{BASE}/products").json(),
        client.get(f"{BASE}/profit/sku/GOLDEN-V1").json(),
        client.get(f"{BASE}/profit/reconcile").json(),
    ]

    seen = 0
    for payload in payloads:
        for path, value in _walk(payload):
            if path and path[-1] in MONEY_KEYS:
                assert isinstance(value, str), f"{path} is {type(value).__name__}, not str"
                assert not isinstance(value, float)
                seen += 1
    assert seen > 0, "no money field was inspected"
