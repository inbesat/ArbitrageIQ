"""T12 acceptance tests: `POST /budget/simulate` (`plans/ACCEPTANCE_TESTS.md`).

Claims **AT-7.11, AT-7.12 and AT-7.14** (T12's Unit rows) and **AT-8.9** (its
Integration row), plus the E2E steps - Rs 50,000 and Rs 500 exercised through the
API. AT-7.1-7.10, 7.13 and 7.15 are T11's and were proved in `test_allocator.py`;
this file only re-proves the two the endpoint could break on its own (Rs 500 buys
nothing, and no plan claims to be optimal).

The exact figures asserted here (Rs 50,000, base scenario, the sample catalogue at
sell_through 0.80 / salvage 0.50 / cap 0.40) come from T11's measured run, never
from the response under test.

E2E note: the documented live-server check cannot run on this machine (D-1 - the
`uvicorn` accept fails with WinError 10014 on Python 3.14.2), so the E2E steps are
driven through in-process `TestClient`, which exercises routing, validation, status
codes and serialisation but cannot prove that a real socket boots.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from arbitrageiq import allocator, db, loaders, models, schemas
from arbitrageiq.api import app, get_engine
from arbitrageiq.config import FeeAssumptions

BASE = "/api/v1"
SAMPLE_CATALOGUE = Path(__file__).resolve().parents[2] / "data" / "sample" / "products_sample.csv"

BUDGET_50K = "50000.00"
BUDGET_500 = "500.00"

#: `plans/BUSINESS_RULES.md` §11.3, copied here so the assertion is independent of
#: the constant the code ships.
DISCLOSURE = (
    "A uniform downside shock cannot demonstrate the main benefit of diversification. "
    "Because every SKU is stressed equally, a diversified plan can score worse in the "
    "conservative scenario than a concentrated one, even though it is genuinely more "
    "resilient to a product-specific failure such as a supplier default, a stock-out, or "
    "a listing suspension. The scenario is a stress test of price and sell-through, not "
    "proof of diversification."
)

PLANS = ("plan_a", "plan_b")
SCENARIOS = ("base", "conservative")

FORBIDDEN_IN_RESPONSE = ("Traceback", 'File "', "SELECT", "INSERT", "sqlite", "C:\\", "E:\\")

#: §11.4's banned plan claims, plus the "predicted sales" wording of §12.
BANNED_CLAIMS = ("optimal", "best", "maximis", "guaranteed", "predicted sale")


def _fresh_engine(tmp_path: Path):
    """Schema, one default assumptions row and the sample catalogue."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'budget.db').as_posix()}")
    db.init(engine)
    with engine.begin() as connection:
        connection.execute(insert(models.fee_assumptions), [FeeAssumptions().__dict__])
    loaders.import_products(engine, SAMPLE_CATALOGUE.read_bytes(), filename=SAMPLE_CATALOGUE.name)
    return engine


def _client(tmp_path: Path) -> TestClient:
    engine = _fresh_engine(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _post(client: TestClient, payload: dict):
    return client.post(f"{BASE}/budget/simulate", json=payload)


def _decimal(value: str) -> Decimal:
    return Decimal(value)


def _order(plan: dict) -> tuple[str, ...]:
    """The SKUs a plan reports, in the order it reports them (zeros included)."""
    return tuple(line["sku"] for line in plan["lines"])


def _walk(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, (*path, index))
    else:
        yield path, node


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


# --- AT-8.9 happy path (and the Rs 50,000 E2E step) --------------------------


def test_at_8_9_returns_both_plans_and_the_conservative_scenario(tmp_path):
    response = _post(_client(tmp_path), {"budget": BUDGET_50K})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["budget"] == "50000.00"
    assert body["sell_through"] == "0.80"
    assert body["salvage"] == "0.50"
    assert body["max_share_per_sku"] == "0.40"
    assert body["disclosure"] == DISCLOSURE

    for scenario in SCENARIOS:
        for plan_name in PLANS:
            plan = body[scenario][plan_name]
            assert plan["strategy"]
            assert plan["label"]
            assert isinstance(plan["capital_used"], str)
            assert isinstance(plan["budget_remaining"], str)
            assert isinstance(plan["expected_contribution"], str)
            assert isinstance(plan["lines"], list)
            for line in plan["lines"]:
                assert set(line) == {
                    "sku",
                    "qty",
                    "capital",
                    "expected_contribution",
                    "assumed",
                }
                assert isinstance(line["qty"], int)
                assert line["assumed"] is True
    _assert_no_leak(response)


def test_at_8_9_plan_a_concentrates_and_plan_b_spreads_the_cap(tmp_path):
    """The measured T11 outcome for the sample catalogue at Rs 50,000."""
    body = _post(_client(tmp_path), {"budget": BUDGET_50K}).json()

    plan_a = body["base"]["plan_a"]
    assert plan_a["capital_used"] == "49896.00"
    assert plan_a["budget_remaining"] == "104.00"
    assert plan_a["expected_contribution"] == "21184.13"
    assert [(line["sku"], line["qty"]) for line in plan_a["lines"] if line["qty"] > 0] == [
        ("TIFFIN-3", 126)
    ]
    # Zeros are reported, not hidden.
    assert len(plan_a["lines"]) > 1

    plan_b = body["base"]["plan_b"]
    assert plan_b["capital_used"] == "49959.00"
    assert plan_b["budget_remaining"] == "41.00"
    assert {line["sku"]: line["qty"] for line in plan_b["lines"] if line["qty"] > 0} == {
        "TIFFIN-3": 50,
        "DIYA-SET-12": 90,
        "TORAN-FLW-1": 39,
    }


# --- AT-8.9 failure cases ---------------------------------------------------


@pytest.mark.parametrize("payload", [{"budget": "0.00"}, {"budget": "-5.00"}])
def test_at_8_9_rejects_a_budget_of_zero_or_less(tmp_path, payload):
    body = _assert_uniform_error(_post(_client(tmp_path), payload), 422)

    assert body["field"] == "budget"


@pytest.mark.parametrize("payload", [{"max_share_per_sku": "0.00"}, {"max_share_per_sku": "1.50"}])
def test_at_8_9_rejects_a_cap_outside_the_unit_interval(tmp_path, payload):
    body = _assert_uniform_error(_post(_client(tmp_path), payload), 422)

    assert body["field"] == "max_share_per_sku"


def test_at_8_9_rejects_an_unknown_sku_in_the_candidate_list(tmp_path):
    response = _post(_client(tmp_path), {"budget": BUDGET_50K, "skus": ["TIFFIN-3", "NOPE-1"]})

    body = _assert_uniform_error(response, 422)
    assert body["field"] == "skus"
    assert "NOPE-1" in body["detail"]


def test_at_8_9_a_non_finite_control_is_a_422_not_a_500(tmp_path):
    body = _assert_uniform_error(_post(_client(tmp_path), {"budget": "NaN"}), 422)

    assert body["field"] == "budget"


def test_a_breach_from_the_allocator_is_a_500_and_never_a_plan(tmp_path, monkeypatch):
    client = _client(tmp_path)

    def _breach(*args, **kwargs):
        raise ValueError("B10: spend exceeds the budget")

    monkeypatch.setattr(allocator, "allocate", _breach)
    response = _post(client, {"budget": BUDGET_50K})

    body = _assert_uniform_error(response, 500)
    assert body["error"] == "invariant_violation"
    # The labelled internal message must not travel to the caller.
    assert "B10" not in response.text


# --- AT-7.11, AT-7.12, AT-7.14 ----------------------------------------------


def test_at_7_11_a_lower_sell_through_lowers_every_expected_profit(tmp_path):
    client = _client(tmp_path)
    high = _post(client, {"budget": BUDGET_50K, "sell_through": "0.80"}).json()
    low = _post(client, {"budget": BUDGET_50K, "sell_through": "0.40"}).json()

    for scenario in SCENARIOS:
        for plan_name in PLANS:
            assert _decimal(low[scenario][plan_name]["expected_contribution"]) < _decimal(
                high[scenario][plan_name]["expected_contribution"]
            ), f"{scenario}/{plan_name} did not fall when sell_through dropped"
    # Ordering is stable: the reported ranking is identical even though every score
    # falls, so no SKU stays fundable at 0.40 and both plans come back empty. The
    # ranking is the observable, not the funded subset.
    for scenario in SCENARIOS:
        for plan_name in PLANS:
            assert _order(low[scenario][plan_name]) == _order(high[scenario][plan_name])


def test_at_7_12_zero_salvage_recovers_nothing_and_stays_finite(tmp_path):
    client = _client(tmp_path)
    half = _post(client, {"budget": BUDGET_50K, "salvage": "0.50"}).json()
    none = _post(client, {"budget": BUDGET_50K, "salvage": "0.00"}).json()

    assert none["salvage"] == "0.00"
    for scenario in SCENARIOS:
        for plan_name in PLANS:
            low = _decimal(none[scenario][plan_name]["expected_contribution"])
            high = _decimal(half[scenario][plan_name]["expected_contribution"])
            assert low.is_finite() and high.is_finite()
            assert low <= high, "unsold units must not recover value when salvage is zero"
    for path, value in _walk(none):
        if path and path[-1] in schemas.BUDGET_MONEY_KEYS:
            assert _decimal(value).is_finite(), f"{path} is not finite"


def test_at_7_14_the_conservative_scenario_is_worse_for_every_plan(tmp_path):
    client = _client(tmp_path)
    body = _post(client, {"budget": BUDGET_50K}).json()

    for plan_name in PLANS:
        base = _decimal(body["base"][plan_name]["expected_contribution"])
        down = _decimal(body["conservative"][plan_name]["expected_contribution"])
        assert down < base, f"{plan_name}: conservative {down} is not worse than base {base}"

    # At Rs 500 both plans are empty in both scenarios, so there the comparison is
    # equality rather than a strict fall; that is why the strict form above uses a
    # funded budget (DEV-24).
    small = _post(client, {"budget": BUDGET_500}).json()
    for plan_name in PLANS:
        assert _decimal(small["conservative"][plan_name]["expected_contribution"]) <= _decimal(
            small["base"][plan_name]["expected_contribution"]
        )


# --- Rs 500 E2E step, and the invariants the endpoint could break -----------


def test_at_7_2_a_budget_of_500_buys_nothing(tmp_path):
    response = _post(_client(tmp_path), {"budget": BUDGET_500})

    assert response.status_code == 200, response.text
    body = response.json()
    for scenario in SCENARIOS:
        for plan_name in PLANS:
            plan = body[scenario][plan_name]
            assert plan["capital_used"] == "0.00"
            assert plan["expected_contribution"] == "0.00"
            assert all(line["qty"] == 0 for line in plan["lines"])


def test_at_7_15_no_plan_claims_to_be_optimal(tmp_path):
    body = _post(_client(tmp_path), {"budget": BUDGET_50K}).json()
    text = json.dumps(body, default=str, sort_keys=True).lower()

    for claim in BANNED_CLAIMS:
        assert claim not in text, f"the budget payload claims {claim!r}"


def test_every_budget_money_field_is_a_json_string_never_a_float(tmp_path):
    body = _post(_client(tmp_path), {"budget": BUDGET_50K}).json()

    seen = 0
    for path, value in _walk(body):
        if path and path[-1] in schemas.BUDGET_MONEY_KEYS:
            assert isinstance(value, str), f"{path} is {type(value).__name__}, not str"
            seen += 1
    assert seen > 0, "no budget money field was inspected"


def test_no_response_leaks_a_path_sql_or_traceback(tmp_path, monkeypatch):
    client = _client(tmp_path)
    responses = [
        _post(client, {"budget": BUDGET_50K}),
        _post(client, {"budget": "0.00"}),
        _post(client, {"max_share_per_sku": "9.00"}),
        _post(client, {"budget": BUDGET_50K, "skus": ["NOPE-1"]}),
    ]

    def _breach(*args, **kwargs):
        raise ValueError("B10: spend exceeds the budget")

    monkeypatch.setattr(allocator, "allocate", _breach)
    responses.append(_post(client, {"budget": BUDGET_50K}))

    for response in responses:
        _assert_no_leak(response)
