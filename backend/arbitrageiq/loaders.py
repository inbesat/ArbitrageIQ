"""The validated import path for CSV payloads (task T09).

``plans/ARCHITECTURE.md`` §2 describes this module as "bundled sample fixture
loading (T09)". It is the route that reads a CSV, validates it through
``validation.py``, and writes the surviving rows atomically — as opposed to
``db.seed``, which loads the bundled fixtures directly with no validation.

Idempotency comes from the database, not from application logic:
``plans/ARCHITECTURE.md`` §5 makes ``import_batches.content_hash`` UNIQUE, so a
repeat import of the same bytes resolves to exactly one winner. The lookup below
is the fast path; the ``IntegrityError`` handler is the backstop that makes the
constraint the arbiter under genuine concurrency (``plans/ACCEPTANCE_TESTS.md``
AT-5.9 and AT-5.21, which T07 moved here under its own fallback — DEV-15).

Imports: ``validation`` (the validator), ``models`` and the standard library.
Never ``api`` (``plans/ARCHITECTURE.md`` §3).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from arbitrageiq import models, validation

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"

SAMPLE_FILES = {
    "products": SAMPLE_DIR / "products_sample.csv",
    "transactions": SAMPLE_DIR / "transactions_sample.csv",
}

_OPTIONAL_MONEY = frozenset({"refund_per_returned_unit", "settlement_fees_total"})


def content_hash(payload: bytes) -> str:
    """The content hash of a payload, as stored on ``import_batches`` (AT-5.21)."""
    return validation.content_hash(payload)


def _existing_row_count(engine: Engine, digest: str) -> int | None:
    with engine.connect() as connection:
        return connection.execute(
            select(models.import_batches.c.row_count).where(
                models.import_batches.c.content_hash == digest
            )
        ).scalar_one_or_none()


def _store(
    engine: Engine,
    *,
    filename: str,
    digest: str,
    kind: str,
    row_count: int,
    rows: list[dict[str, Any]],
    link_batch: bool,
) -> dict[str, Any]:
    """Insert the batch row and its child rows in one transaction.

    The batch row goes first so that a hash collision surfaces as an
    ``IntegrityError`` before any child row is written.

    ``link_batch`` is True for transactions, whose rows carry ``import_batch_id``.
    ``products`` has no such column (``models.py``), so its rows are inserted
    unchanged.
    """
    batch = {
        "filename": filename,
        "content_hash": digest,
        "row_count": row_count,
        "rejected_count": 0,
        "kind": kind,
        "created_at": date.today(),
    }
    try:
        with engine.begin() as connection:
            result = connection.execute(models.import_batches.insert(), [batch])
            batch_id = result.inserted_primary_key[0]
            if rows:
                if link_batch:
                    connection.execute(
                        models.transactions.insert(),
                        [dict(row, import_batch_id=batch_id) for row in rows],
                    )
                else:
                    connection.execute(models.products.insert(), rows)
    except IntegrityError:
        # The UNIQUE content hash (or a duplicate primary key) lost the race: the
        # other writer already stored this content, so nothing is imported here.
        return {"imported": 0, "skipped": row_count}
    return {"imported": len(rows), "skipped": 0}


def _product_record(row: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "sku": str(row["sku"]),
        "name": str(row["name"]),
        "category": str(row["category"]),
        "current_stock": int(row["current_stock"]),
        "min_order_qty": int(row["min_order_qty"]),
        "max_supply": int(row["max_supply"]),
        "cost_updated_on": row.get("cost_updated_on"),
    }
    for key in (
        "supplier_unit_cost",
        "inbound_unit_cost",
        "packaging_unit_cost",
        "target_price",
    ):
        record[key] = Decimal(str(row[key]))
    return record


def _transaction_record(row: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "transaction_id": str(row["transaction_id"]),
        "order_date": row["order_date"],
        "sku": str(row["sku"]),
        "units_sold": int(row["units_sold"]),
        "returned_units": int(row["returned_units"]),
        "import_batch_id": None,
    }
    for key in (
        "selling_price",
        "discount_per_unit",
        "refund_per_returned_unit",
        "settlement_fees_total",
        "ads_cost",
        "other_charges",
    ):
        value = row.get(key)
        record[key] = None if value is None else Decimal(str(value))
    return record


def _known_skus(engine: Engine) -> frozenset[str]:
    with engine.connect() as connection:
        return frozenset(connection.execute(select(models.products.c.sku)).scalars().all())


def import_products(engine: Engine, payload: bytes, *, filename: str) -> dict[str, Any]:
    """Validate and store a products payload. Returns ``imported``/``skipped``."""
    digest = content_hash(payload)
    existing = _existing_row_count(engine, digest)
    if existing is not None:
        return {"imported": 0, "skipped": existing, "rejected_total": 0}

    result = validation.validate_products(payload, filename=filename)
    rows = [_product_record(row) for row in result.valid_rows]
    if not rows:
        return {"imported": 0, "skipped": 0, "rejected_total": result.rejected_total}

    outcome = _store(
        engine,
        filename=filename,
        digest=digest,
        kind="products",
        row_count=len(rows),
        rows=rows,
        link_batch=False,
    )
    return {**outcome, "rejected_total": result.rejected_total}


def import_transactions(
    engine: Engine,
    payload: bytes,
    *,
    filename: str,
    known_skus: Any = None,
) -> dict[str, Any]:
    """Validate and store a transactions payload (AT-5.9, AT-5.21).

    A repeat of the same bytes reports ``imported == 0`` and
    ``skipped == row_count``, because ``import_batches.content_hash`` is UNIQUE.
    """
    digest = content_hash(payload)
    existing = _existing_row_count(engine, digest)
    if existing is not None:
        return {"imported": 0, "skipped": existing, "rejected_total": 0}

    result = validation.validate_transactions(payload, filename=filename, known_skus=known_skus)
    rows = [_transaction_record(row) for row in result.valid_rows]
    if not rows:
        return {"imported": 0, "skipped": 0, "rejected_total": result.rejected_total}

    outcome = _store(
        engine,
        filename=filename,
        digest=digest,
        kind="transactions",
        row_count=len(rows),
        rows=rows,
        link_batch=True,
    )
    return {**outcome, "rejected_total": result.rejected_total}


def import_sample(engine: Engine, *, kind: str) -> dict[str, Any]:
    """Load one of the bundled synthetic fixtures through the validated path."""
    if kind not in SAMPLE_FILES:
        raise ValueError(f"unknown sample kind: {kind!r}")

    payload = SAMPLE_FILES[kind].read_bytes()
    filename = SAMPLE_FILES[kind].name
    if kind == "products":
        return import_products(engine, payload, filename=filename)
    return import_transactions(engine, payload, filename=filename, known_skus=_known_skus(engine))
