"""FastAPI application: the nine P0 endpoint operations (task T10).

**Base path.** Every P0 endpoint is mounted under ``/api/v1``. FastAPI's
``/docs`` and ``/openapi.json`` stay at the root default. The prefix was chosen
and recorded here as ``plans/ARCHITECTURE.md`` §6 requires ("the prefix is
chosen at T10 and recorded there").

**Errors are uniform:** ``{error, detail, field?}`` — never a bare string, and
never a filesystem path, SQL fragment or traceback (``plans/SECURITY.md`` §6.1;
``plans/ACCEPTANCE_TESTS.md`` AT-5.22 and AT-8.10).

**Money is computed only in the backend.** Every route delegates to
``validation``, ``loaders``, ``reconcile``, ``config`` or ``profit``; no money
arithmetic happens here, and every monetary value leaves as a decimal string
(ADR-024).

``POST /budget/simulate`` wires ``allocator`` to the wire (task T12): the two
greedy heuristics and the conservative scenario, each with its per-SKU lines,
plus the §11.3 honesty statement. A breach of the B1-B10 invariants returns a
500 and never a plausible-looking plan.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, delete, insert, select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from arbitrageiq import (
    __version__,
    allocator,
    config,
    db,
    loaders,
    models,
    profit,
    reconcile,
    schemas,
    simulate,
    validation,
)

API_PREFIX = "/api/v1"


class ApiError(Exception):
    """A typed API failure that renders as the uniform error body."""

    def __init__(
        self,
        status_code: int,
        error: str,
        detail: str,
        field: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail
        self.field = field

    def body(self) -> dict[str, str]:
        payload = {"error": self.error, "detail": self.detail}
        if self.field is not None:
            payload["field"] = self.field
        return payload


app = FastAPI(
    title="ArbitrageIQ API",
    description="Local decision-support API. Illustrative demo assumptions only.",
    version=__version__,
)
router = APIRouter(prefix=API_PREFIX)


def get_engine() -> Engine:
    """Engine dependency. Tests override it via ``app.dependency_overrides``."""
    return db.make_engine()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _assumption_records(engine: Engine) -> list[config.FeeAssumptions]:
    """Read every stored assumption row as a ``FeeAssumptions`` record."""
    with engine.connect() as connection:
        rows = connection.execute(select(models.fee_assumptions)).mappings().all()
    return [
        config.FeeAssumptions(**{key: value for key, value in row.items() if key != "id"})
        for row in rows
    ]


def _active_assumptions(engine: Engine) -> config.FeeAssumptions:
    try:
        return config.active_assumptions(_assumption_records(engine))
    except LookupError as exc:
        raise ApiError(
            404,
            "no_assumptions",
            "No assumption set is configured for the current date.",
        ) from exc


def _known_skus(engine: Engine) -> frozenset[str]:
    """The catalogue's SKUs, used as the referential check for transactions."""
    with engine.connect() as connection:
        return frozenset(connection.execute(select(models.products.c.sku)).scalars().all())


def _rejections(result: Any) -> list[dict[str, Any]]:
    return [schemas.rejection_payload(item) for item in result.rejected]


def _validate_upload(
    data: bytes,
    *,
    kind: str,
    filename: str,
    engine: Engine,
) -> Any:
    """Validate uploaded bytes without persisting anything."""
    if kind == "products":
        return validation.validate_products(data, filename=filename)
    if kind == "transactions":
        # AT-5.14: a transaction whose sku is absent from the catalogue is
        # rejected, so products must be imported before transactions. An empty
        # catalogue therefore rejects every row, which is the honest outcome.
        return validation.validate_transactions(
            data, filename=filename, known_skus=_known_skus(engine)
        )
    raise ApiError(
        422,
        "validation_failed",
        "kind must be 'products' or 'transactions'.",
        "kind",
    )


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------


@router.get("/health")
def health(engine: Annotated[Engine, Depends(get_engine)]) -> dict[str, str]:
    """Liveness plus database reachability (AT-8.1)."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ApiError(
            503,
            "database_unreachable",
            "The local database is not reachable.",
        ) from exc
    # `db` is a status word, never a path: a path would leak the filesystem.
    return {"status": "ok", "version": __version__, "db": "reachable"}


@router.get("/assumptions")
def read_assumptions(engine: Annotated[Engine, Depends(get_engine)]) -> dict[str, Any]:
    """The active assumption set (AT-8.2)."""
    return schemas.assumption_payload(dataclasses.asdict(_active_assumptions(engine)))


@router.put("/assumptions")
def update_assumptions(
    body: schemas.AssumptionUpdate,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict[str, Any]:
    """Validate and store a dated assumption set (AT-8.3).

    ``fee_assumptions`` is append-mostly with exactly one active row per date,
    so a change replaces the row carrying the same ``effective_from``
    (``plans/ARCHITECTURE.md`` §5).
    """
    values = body.model_dump()
    try:
        record = config.FeeAssumptions(
            **{key: Decimal(values[key]) for key in schemas.ASSUMPTION_MONEY_KEYS},
            fee_gst_recoverable=values["fee_gst_recoverable"],
            effective_from=date.fromisoformat(str(values["effective_from"])),
            note=str(values["note"]),
        )
    except (ValueError, InvalidOperation) as exc:
        message = str(exc) or "invalid assumption value"
        field = message.split(" ", 1)[0] if message.split(" ", 1)[0] else None
        raise ApiError(422, "validation_failed", message, field) from exc

    row = dataclasses.asdict(record)
    with engine.begin() as connection:
        connection.execute(
            delete(models.fee_assumptions).where(
                models.fee_assumptions.c.effective_from == record.effective_from
            )
        )
        connection.execute(insert(models.fee_assumptions), [row])
    return schemas.assumption_payload(row)


@router.get("/products")
def list_products(engine: Annotated[Engine, Depends(get_engine)]) -> list[dict[str, Any]]:
    """The catalogue; an empty catalogue is an empty list, never 404 (AT-8.4)."""
    with engine.connect() as connection:
        rows = connection.execute(select(models.products)).mappings().all()
    return [schemas.product_payload(row) for row in rows]


@router.post("/import/validate")
async def validate_import(
    file: Annotated[UploadFile, File()],
    engine: Annotated[Engine, Depends(get_engine)],
    kind: Annotated[str, Form()] = "transactions",
) -> dict[str, Any]:
    """Dry run: validate the upload and persist nothing (AT-8.5)."""
    data = await file.read()
    result = _validate_upload(
        data, kind=kind, filename=file.filename or "upload.csv", engine=engine
    )
    return {
        "dry_run": True,
        "imported": len(result.valid_rows),
        "rejected_total": result.rejected_total,
        "rejected": _rejections(result),
        "warnings": list(result.warnings),
    }


@router.post("/import")
async def import_file(
    file: Annotated[UploadFile, File()],
    engine: Annotated[Engine, Depends(get_engine)],
    kind: Annotated[str, Form()] = "transactions",
) -> dict[str, Any]:
    """Validate and persist an upload; a repeat upload is a no-op (AT-8.6)."""
    data = await file.read()
    filename = file.filename or "upload.csv"
    result = _validate_upload(data, kind=kind, filename=filename, engine=engine)
    if kind == "products":
        outcome = loaders.import_products(engine, data, filename=filename)
    else:
        outcome = loaders.import_transactions(
            engine, data, filename=filename, known_skus=_known_skus(engine)
        )
    return {
        "imported": outcome["imported"],
        "skipped": outcome["skipped"],
        "rejected_total": result.rejected_total,
        "rejected": _rejections(result),
    }


@router.post("/import/sample")
def import_sample(
    body: schemas.SampleRequest,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict[str, Any]:
    """Load a bundled synthetic fixture through the validated path (task T14).

    The same shape as ``POST /import`` so the Import view renders one summary for
    both. Loading the catalogue first is still required: the transactions fixture
    would be rejected wholesale against an empty catalogue (AT-5.14).
    """
    if body.kind not in loaders.SAMPLE_FILES:
        raise ApiError(
            422,
            "validation_failed",
            "kind must be 'products' or 'transactions'.",
            "kind",
        )
    source = loaders.SAMPLE_FILES[body.kind]
    payload = source.read_bytes()
    result = _validate_upload(payload, kind=body.kind, filename=source.name, engine=engine)
    outcome = loaders.import_sample(engine, kind=body.kind)
    return {
        "imported": outcome["imported"],
        "skipped": outcome["skipped"],
        "rejected_total": result.rejected_total,
        "rejected": _rejections(result),
    }


@router.get("/profit/sku/{sku}")
def profit_for_sku(sku: str, engine: Annotated[Engine, Depends(get_engine)]) -> dict[str, Any]:
    """One SKU: totals plus the per-line breakdown (AT-8.7)."""
    with engine.connect() as connection:
        product = (
            connection.execute(select(models.products).where(models.products.c.sku == sku))
            .mappings()
            .first()
        )
        rows = (
            connection.execute(select(models.transactions).where(models.transactions.c.sku == sku))
            .mappings()
            .all()
        )
    if product is None and not rows:
        raise ApiError(404, "unknown_sku", f"No data exists for sku '{sku}'.")

    assumptions = _active_assumptions(engine)
    landed = Decimal("0.00")
    if product is not None:
        landed = (
            Decimal(str(product["supplier_unit_cost"]))
            + Decimal(str(product["inbound_unit_cost"]))
            + Decimal(str(product["packaging_unit_cost"]))
        )

    lines: list[dict[str, Any]] = []
    total = Decimal("0.00")
    for row in rows:
        line = reconcile.line_input_from_row(row, landed_unit_cost=landed)
        breakdown = profit.compute_line(line, assumptions)
        total += breakdown.contribution
        lines.append(schemas.breakdown_payload(breakdown))

    return {
        "sku": sku,
        "totals": {"contribution": str(total), "line_count": len(lines)},
        "assumptions": schemas.assumption_payload(dataclasses.asdict(assumptions)),
        "lines": lines,
    }


@router.get("/profit/reconcile")
def profit_reconcile(engine: Annotated[Engine, Depends(get_engine)]) -> dict[str, Any]:
    """Per-SKU and portfolio totals (AT-8.8). Empty is a valid 200 state."""
    try:
        result = reconcile.reconcile(engine)
    except LookupError as exc:
        raise ApiError(
            404,
            "no_assumptions",
            "No assumption set is configured for the current date.",
        ) from exc
    return {
        "per_sku": {sku: str(value) for sku, value in result["per_sku"].items()},
        "portfolio_total": str(result["portfolio_total"]),
        # Added by T14 for the Overview; both are additive, so a client that only
        # reads the two keys above is unaffected (AT-8.8).
        "portfolio_net_revenue": str(result["portfolio_net_revenue"]),
        "portfolio_capital_at_cost": str(result["portfolio_capital_at_cost"]),
    }


def _decimal_control(raw: str | None, default: Decimal, *, field: str) -> Decimal:
    """Parse one optional control, falling back to its assumption default.

    A control is untrusted input, so it is parsed and checked for finiteness at
    this boundary (``plans/SECURITY.md`` §5): ``NaN`` and ``Infinity`` become
    422s rather than values that reach the allocator's arithmetic.
    """
    if raw is None:
        return default
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ApiError(
            422, "validation_failed", f"{field} must be a decimal number.", field
        ) from exc
    if not value.is_finite():
        raise ApiError(422, "validation_failed", f"{field} must be a finite number.", field)
    return value


def _candidates(engine: Engine) -> list[allocator.Candidate]:
    """Build the allocator's candidates from the catalogue (``ARCHITECTURE.md`` §4.3)."""
    with engine.connect() as connection:
        rows = connection.execute(select(models.products)).mappings().all()
    return [
        allocator.Candidate(
            sku=row["sku"],
            price=Decimal(str(row["target_price"])),
            landed_unit_cost=(
                Decimal(str(row["supplier_unit_cost"]))
                + Decimal(str(row["inbound_unit_cost"]))
                + Decimal(str(row["packaging_unit_cost"]))
            ),
            min_order_qty=int(row["min_order_qty"]),
            max_supply=int(row["max_supply"]),
        )
        for row in rows
    ]


def _selected_candidates(
    candidates: list[allocator.Candidate], skus: list[str] | None
) -> list[allocator.Candidate]:
    """Restrict the catalogue to the requested SKUs; an unknown SKU is a 422."""
    if skus is None:
        return candidates
    by_sku = {candidate.sku: candidate for candidate in candidates}
    missing = sorted(sku for sku in skus if sku not in by_sku)
    if missing:
        raise ApiError(
            422,
            "validation_failed",
            f"Unknown sku: {', '.join(missing)}.",
            "skus",
        )
    return [by_sku[sku] for sku in skus]


@router.post("/budget/simulate")
def budget_simulate(
    body: schemas.SimulateRequest,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict[str, Any]:
    """Two greedy plans plus the conservative scenario (AT-8.9; task T12).

    The controls are validated here, before ``allocator.allocate`` runs, so any
    ``ValueError`` that escapes it is an invariant breach (B1-B10) and returns a
    500 rather than a plan that quietly overspends.
    """
    assumptions = _active_assumptions(engine)
    budget = _decimal_control(body.budget, assumptions.default_budget, field="budget")
    sell_through = _decimal_control(
        body.sell_through, assumptions.default_sell_through, field="sell_through"
    )
    salvage = _decimal_control(body.salvage, assumptions.default_salvage, field="salvage")
    max_share_per_sku = _decimal_control(
        body.max_share_per_sku,
        assumptions.default_max_share_per_sku,
        field="max_share_per_sku",
    )

    if budget <= 0:
        raise ApiError(422, "validation_failed", "budget must be greater than zero.", "budget")
    if not 0 < max_share_per_sku <= 1:
        raise ApiError(
            422,
            "validation_failed",
            "max_share_per_sku must be within (0, 1].",
            "max_share_per_sku",
        )
    # Request-level bounds are spec-silent; R2 bounds the assumption record to
    # [0, 1], so a request override is held to the same range (DEV-22).
    for name, value in (("sell_through", sell_through), ("salvage", salvage)):
        if not 0 <= value <= 1:
            raise ApiError(422, "validation_failed", f"{name} must be within [0, 1].", name)

    candidates = _selected_candidates(_candidates(engine), body.skus)
    try:
        allocation = allocator.allocate(
            candidates,
            assumptions,
            budget=budget,
            sell_through=sell_through,
            salvage=salvage,
            max_share_per_sku=max_share_per_sku,
        )
    except ValueError as exc:
        # check_invariants already ran over all four plans inside allocate; a
        # labelled B1-B10 breach must never reach the caller as a plausible plan.
        raise ApiError(
            500,
            "invariant_violation",
            "The allocation failed an internal consistency check and was not returned.",
        ) from exc

    return schemas.allocation_payload(
        allocation,
        budget=budget,
        sell_through=sell_through,
        salvage=salvage,
        max_share_per_sku=max_share_per_sku,
    )


def _required_control(raw: str | None, *, field: str) -> Decimal:
    """Parse a decimal control that has no safe fallback."""
    if raw is None:
        raise ApiError(422, "validation_failed", f"{field} is required.", field)
    return _decimal_control(raw, Decimal(0), field=field)


@router.post("/simulate/sku")
def simulate_sku(
    body: schemas.SimulateSkuRequest,
    engine: Annotated[Engine, Depends(get_engine)],
) -> dict[str, Any]:
    """A what-if contribution line over one batch of units (deviation DEV-39).

    ``profit.compute_line`` is reused exactly as an imported line uses it, so
    the simulated figure and the imported figures agree on the order of
    operations and on the rounding (``plans/BUSINESS_RULES.md`` §4). The two
    controls the engine reads from an assumption — the referral rate and the
    closing fee — are overridden through ``dataclasses.replace``, which runs
    the same range checks the config declares (``config.FeeAssumptions``).
    """
    assumptions = _active_assumptions(engine)

    price = _required_control(body.price, field="price")
    landed_unit_cost = _required_control(body.landed_unit_cost, field="landed_unit_cost")
    referral_rate = _decimal_control(
        body.referral_rate, assumptions.referral_rate, field="referral_rate"
    )
    closing_fee = _decimal_control(body.closing_fee, assumptions.closing_fee, field="closing_fee")
    returns_rate = _decimal_control(body.returns_rate, Decimal(0), field="returns_rate")
    ads_per_unit = _decimal_control(body.ads_per_unit, Decimal(0), field="ads_per_unit")
    units = simulate.SIMULATION_UNITS if body.units is None else body.units

    for name, value in (
        ("price", price),
        ("landed_unit_cost", landed_unit_cost),
        ("closing_fee", closing_fee),
        ("ads_per_unit", ads_per_unit),
    ):
        if value < 0:
            raise ApiError(422, "validation_failed", f"{name} must be zero or greater.", name)

    for name, value in (("referral_rate", referral_rate), ("returns_rate", returns_rate)):
        if not Decimal(0) <= value <= Decimal(1):
            raise ApiError(422, "validation_failed", f"{name} must be within [0, 1].", name)

    if not 1 <= units <= simulate.SIMULATION_UNITS_MAX:
        raise ApiError(
            422,
            "validation_failed",
            f"units must be between 1 and {simulate.SIMULATION_UNITS_MAX}.",
            "units",
        )

    tuned = dataclasses.replace(assumptions, referral_rate=referral_rate, closing_fee=closing_fee)
    breakdown = profit.compute_line(
        simulate.line_input(
            sku=body.sku or "",
            units=units,
            returns_rate=returns_rate,
            price=price,
            landed_unit_cost=landed_unit_cost,
            ads_per_unit=ads_per_unit,
        ),
        tuned,
    )

    return schemas.simulation_payload(
        breakdown,
        assumptions_values=dataclasses.asdict(tuned),
        inputs={
            "price": price,
            "landed_unit_cost": landed_unit_cost,
            "referral_rate": referral_rate,
            "closing_fee": closing_fee,
            "returns_rate": returns_rate,
            "ads_per_unit": ads_per_unit,
        },
        units=units,
    )


app.include_router(router)


# --------------------------------------------------------------------------
# uniform error boundaries
# --------------------------------------------------------------------------


def _error_response(status_code: int, error: str, detail: str, field: str | None = None):
    payload = {"error": error, "detail": detail}
    if field is not None:
        payload["field"] = field
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(ApiError)
async def _handle_api_error(_request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(validation.CsvLimitError)
async def _handle_limit(_request, exc: validation.CsvLimitError) -> JSONResponse:
    """A cap was exceeded: 413 for size, 413 for rows, with the cap named."""
    return _error_response(
        413,
        "file_too_large",
        f"The upload exceeds the {exc.cap} limit of {exc.limit}.",
    )


@app.exception_handler(validation.CsvReadError)
async def _handle_unreadable(_request, exc: validation.CsvReadError) -> JSONResponse:
    """The file itself could not be read or is missing columns: 422."""
    return _error_response(422, "validation_failed", str(exc))


@app.exception_handler(RequestValidationError)
async def _handle_request_validation(_request, exc: RequestValidationError) -> JSONResponse:
    """Malformed request body: 422 in the uniform shape."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    location = [str(part) for part in first.get("loc", ()) if part != "body"]
    field = location[0] if location else None
    detail = str(first.get("msg") or "The request body is invalid.")
    return _error_response(422, "validation_failed", detail, field)


@app.exception_handler(StarletteHTTPException)
async def _handle_http_exception(_request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(SQLAlchemyError)
async def _handle_database_error(_request, exc: SQLAlchemyError) -> JSONResponse:
    """A database failure is a 500 with a safe message; the cause stays in the log."""
    return _error_response(500, "database_error", "The local database rejected the request.")


@app.exception_handler(Exception)
async def _handle_unexpected(_request, exc: Exception) -> JSONResponse:
    """Last resort: a uniform 500. The traceback goes to the server log only."""
    return _error_response(500, "internal_error", "An unexpected error occurred.")
