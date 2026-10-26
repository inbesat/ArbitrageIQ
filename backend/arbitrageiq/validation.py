"""Text-first CSV validation for ArbitrageIQ products and transactions (task T06).

Rules implemented here come from ``plans/BUSINESS_RULES.md`` section 3 (field
semantics) and section 4 (the GROSS/NET trap), ``plans/SECURITY.md`` section 3
(the CSV upload safety table), ``plans/ACCEPTANCE_TESTS.md`` AT-5, and
``plans/DECISIONS.md`` ADR-021/ADR-022 (canonical column names).

Design rules, deliberately structural:

* **Text first.** The file is read as text (``dtype=str``, no NA coercion) and
  every cell is parsed explicitly. There is no float intermediate anywhere, so a
  money cell becomes ``Decimal`` straight from its string form. This is the rule
  in ``plans/TECH_STACK.md`` section 2.1; pandas does I/O and nothing else.
* **Collect, do not raise.** A row that fails validation is collected as a
  rejection and the remaining rows still load (AT-5.19). Only a file that cannot
  be read at all raises ``CsvReadError``.
* **Bounded output.** The rejection list is capped and summarised (AT-5.20) so a
  hostile file cannot produce an unbounded payload.
* **Safe messages.** No path, no SQL, no traceback, no library version, and the
  filename is never used as a path or echoed into a message (AT-5.18, AT-5.22).
* **Imports.** ``plans/ARCHITECTURE.md`` section 3 gives this module stdlib plus
  pandas only. It must never import ``profit``, ``db`` or ``api``, and it
  computes no money.

Nothing here is persisted: validation is pure, so a dry run is the default.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas

#: 5 MB per file, enforced on the raw bytes before parsing (AT-5.15).
MAX_FILE_BYTES = 5 * 1024 * 1024

#: 20,000 data rows per file, excluding the header (AT-5.16).
MAX_DATA_ROWS = 20_000

#: How many rejections are reported before the rest are summarised (AT-5.20).
MAX_REPORTED_REJECTIONS = 100

_BOM = "\ufeff"


class CsvReadError(Exception):
    """The file cannot be read as a products or transactions CSV at all."""


class CsvLimitError(CsvReadError):
    """A documented cap was exceeded (AT-5.15, AT-5.16).

    The API layer maps this subclass to 413 and its parent to 422, so the two
    caps never need a second contract.
    """

    def __init__(self, message: str, *, cap: str, limit: int) -> None:
        super().__init__(message)
        self.cap = cap
        self.limit = limit


@dataclass(frozen=True)
class ColumnSpec:
    """One column declaration: its kind, whether it is required, its bounds."""

    name: str
    kind: str  # "str" | "int" | "decimal" | "date"
    required: bool = False
    minimum: Decimal | None = None
    exclusive_minimum: Decimal | None = None
    description: str = ""


@dataclass(frozen=True)
class Rejection:
    """One rejected row, in the shape fixed by ``plans/ARCHITECTURE.md`` 4.1."""

    row: int
    field: str
    value: str
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    """What a validation run produced. Pure data; nothing is written anywhere."""

    row_count: int
    valid_rows: tuple[Mapping[str, object], ...]
    rejected: tuple[Rejection, ...]
    rejected_total: int
    warnings: tuple[str, ...] = field(default=())


_INT_MIN = Decimal("0")


PRODUCT_SPEC: tuple[ColumnSpec, ...] = (
    ColumnSpec("sku", "str", required=True, description="Unique product code."),
    ColumnSpec("name", "str", required=True, description="Display name."),
    ColumnSpec("category", "str", required=True),
    ColumnSpec(
        "supplier_unit_cost",
        "decimal",
        required=True,
        minimum=_INT_MIN,
        description="GST-inclusive.",
    ),
    ColumnSpec("inbound_unit_cost", "decimal", required=True, minimum=_INT_MIN),
    ColumnSpec("packaging_unit_cost", "decimal", required=True, minimum=_INT_MIN),
    ColumnSpec("target_price", "decimal", required=True, exclusive_minimum=_INT_MIN),
    ColumnSpec("current_stock", "int", required=True, minimum=_INT_MIN),
    ColumnSpec("min_order_qty", "int", required=True, minimum=_INT_MIN),
    ColumnSpec("max_supply", "int", required=True, minimum=_INT_MIN),
    ColumnSpec("cost_updated_on", "date", required=False, description="Optional; unused in P0."),
)

TRANSACTION_SPEC: tuple[ColumnSpec, ...] = (
    ColumnSpec("transaction_id", "str", required=True, description="Unique per file."),
    ColumnSpec("sku", "str", required=True),
    ColumnSpec("order_date", "date", required=True),
    ColumnSpec("units_sold", "int", required=True, minimum=_INT_MIN, description="GROSS shipped."),
    ColumnSpec("returned_units", "int", required=True, minimum=_INT_MIN),
    ColumnSpec("selling_price", "decimal", required=True, exclusive_minimum=_INT_MIN),
    ColumnSpec("discount_per_unit", "decimal", required=False, minimum=_INT_MIN),
    ColumnSpec("refund_per_returned_unit", "decimal", required=False, minimum=_INT_MIN),
    ColumnSpec("settlement_fees_total", "decimal", required=False, minimum=_INT_MIN),
    ColumnSpec("ads_cost", "decimal", required=False, minimum=_INT_MIN),
    ColumnSpec("other_charges", "decimal", required=False, minimum=_INT_MIN),
)

#: The only alias documented anywhere in the specification set (ADR-021/022).
ALIASES: Mapping[str, str] = {
    "refund_inclusive_per_return": "refund_per_returned_unit",
}


def _normalise_header(raw: str) -> str:
    return raw.replace(_BOM, "").strip().lower()


def _read_text(data: bytes) -> str:
    """Decode the raw upload, failing safely on anything that is not text."""
    if not data:
        raise CsvReadError("file is empty: no header row was found")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise CsvReadError("not a readable CSV/text file") from None
    if "\x00" in text:
        raise CsvReadError("not a readable CSV/text file")
    return text.replace(_BOM, "", 1) if text.startswith(_BOM) else text


def _row_count(text: str) -> int:
    """Count data rows without parsing them, so the row cap is enforced first."""
    lines = [line for line in text.splitlines() if line.strip()]
    return max(len(lines) - 1, 0)


def _frame(text: str) -> pandas.DataFrame:
    try:
        return pandas.read_csv(
            io.StringIO(text),
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    except (pandas.errors.ParserError, csv.Error, ValueError) as error:
        raise CsvReadError(
            f"the file could not be parsed as CSV; check the quoting near row {_line_hint(error)}"
        ) from None


def _line_hint(error: Exception) -> str:
    for token in str(error).replace(",", " ").split():
        if token.isdigit():
            return token
    return "the reported line"


def _resolve_columns(
    text: str, spec: Sequence[ColumnSpec], warnings: list[str]
) -> tuple[list[str], dict[str, ColumnSpec]]:
    """Map each header position to its canonical column name.

    A column that is not in the spec is kept under its own cleaned label so the
    value survives as plain text, and a warning records it (AT-5.2).
    """
    reader = csv.reader(io.StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        raise CsvReadError("file is empty: no header row was found") from None
    except csv.Error:
        raise CsvReadError("the header row could not be parsed as CSV") from None

    by_canonical = {spec_.name: spec_ for spec_ in spec}
    labels: list[str] = []
    seen: set[str] = set()
    for cell in raw_header:
        cleaned = _normalise_header(cell)
        canonical = ALIASES.get(cleaned, cleaned)
        if canonical not in by_canonical:
            warnings.append(f"extra column '{cleaned}' was ignored")
            labels.append(cleaned)
            continue
        if canonical in seen:
            warnings.append(f"column '{canonical}' appeared twice; the later copy was ignored")
            labels.append(cleaned)
            continue
        seen.add(canonical)
        labels.append(canonical)

    missing = [spec_.name for spec_ in spec if spec_.required and spec_.name not in seen]
    if missing:
        raise CsvReadError("required column(s) missing: " + ", ".join(missing))
    return labels, by_canonical


def _parse_decimal(spec: ColumnSpec, raw: str) -> Decimal:
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        raise _CellError(f"'{raw}' is not a number") from None
    if not value.is_finite():
        raise _CellError(f"'{raw}' is not a finite number")
    if spec.minimum is not None and value < spec.minimum:
        raise _CellError(f"must be at least {spec.minimum}, got '{raw}'")
    if spec.exclusive_minimum is not None and value <= spec.exclusive_minimum:
        raise _CellError(f"must be greater than {spec.exclusive_minimum}, got '{raw}'")
    return value


def _parse_int(spec: ColumnSpec, raw: str) -> int:
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        raise _CellError(f"'{raw}' is not a whole number") from None
    if spec.minimum is not None and Decimal(value) < spec.minimum:
        raise _CellError(f"must be at least {int(spec.minimum)}, got '{raw}'")
    return value


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        raise _CellError(f"'{raw}' is not a date in YYYY-MM-DD form") from None


class _CellError(Exception):
    """One cell failed to parse. Internal; converted into a Rejection."""


def _parse_cell(spec: ColumnSpec, raw: str) -> object:
    if spec.kind == "str":
        return raw
    if spec.kind == "decimal":
        return _parse_decimal(spec, raw)
    if spec.kind == "int":
        return _parse_int(spec, raw)
    if spec.kind == "date":
        return _parse_date(raw)
    raise _CellError(f"unsupported column kind '{spec.kind}'")


def content_hash(data: bytes) -> str:
    """Return a deterministic content hash of the exact bytes received (AT-5.21).

    SHA-256 in lowercase hex is an implementation choice: the specification says
    only "content hash" and names no algorithm (``plans/SECURITY.md`` §3,
    ``plans/ARCHITECTURE.md`` §5). The function is pure, so reimporting the same
    bytes resolves deterministically; the "exactly one wins" write belongs to the
    ``import_batches.content_hash`` UNIQUE constraint (T09).
    """
    return hashlib.sha256(data).hexdigest()


def _validate(
    data: bytes,
    spec: Sequence[ColumnSpec],
    *,
    filename: str,
    known_skus: Collection[str] | None,
    unique_key: str | None,
) -> ValidationResult:
    del filename  # A display label only; never used as a path or echoed (AT-5.18).
    if len(data) > MAX_FILE_BYTES:
        raise CsvLimitError(
            f"file is larger than the size cap of {MAX_FILE_BYTES} bytes",
            cap="size",
            limit=MAX_FILE_BYTES,
        )

    text = _read_text(data)
    if _row_count(text) > MAX_DATA_ROWS:
        raise CsvLimitError(
            f"file has more than the row cap of {MAX_DATA_ROWS} data rows",
            cap="rows",
            limit=MAX_DATA_ROWS,
        )

    warnings: list[str] = []
    labels, by_canonical = _resolve_columns(text, spec, warnings)
    frame = _frame(text)
    frame.columns = labels

    valid: list[Mapping[str, object]] = []
    rejected: list[Rejection] = []
    rejected_total = 0
    seen_keys: set[str] = set()  # first *valid* occurrence wins (AT-5.8)

    for offset, (_, series) in enumerate(frame.iterrows()):
        line_number = offset + 2  # the header is row 1
        row: dict[str, object] = {}
        failure: tuple[str, str, str] | None = None

        for label, raw in series.items():
            column = str(label)
            cell_spec = by_canonical.get(column)
            if cell_spec is None:
                row[column] = raw  # an unknown column is kept as plain text
                continue
            cell = str(raw)
            if cell == "":
                if cell_spec.required:
                    failure = (column, cell, "value is required")
                    break
                row[column] = None
                continue
            try:
                row[column] = _parse_cell(cell_spec, cell)
            except _CellError as error:
                failure = (column, cell, str(error))
                break

        if failure is None:
            failure = _cross_field_failure(row)
        if failure is None and known_skus is not None:
            sku = row.get("sku")
            if isinstance(sku, str) and sku not in known_skus:
                failure = ("sku", sku, f"sku '{sku}' is not present in products")

        if failure is None and unique_key is not None:
            key_value = row.get(unique_key)
            if isinstance(key_value, str):
                if key_value in seen_keys:
                    failure = (
                        unique_key,
                        key_value,
                        f"duplicate {unique_key} '{key_value}' in this file",
                    )
                else:
                    seen_keys.add(key_value)

        if failure is None:
            valid.append(row)
        else:
            field_name, value, reason = failure
            rejected_total += 1
            if len(rejected) < MAX_REPORTED_REJECTIONS:
                rejected.append(
                    Rejection(row=line_number, field=field_name, value=value, reason=reason)
                )

    if rejected_total > len(rejected):
        warnings.append(
            f"{rejected_total} rows were rejected; the first {len(rejected)} are listed"
        )

    return ValidationResult(
        row_count=len(frame.index),
        valid_rows=tuple(valid),
        rejected=tuple(rejected),
        rejected_total=rejected_total,
        warnings=tuple(warnings),
    )


def _cross_field_failure(row: Mapping[str, object]) -> tuple[str, str, str] | None:
    """Row-level rules that only make sense once a row is parsed (AT-5.10, 5.11)."""
    units = row.get("units_sold")
    returned = row.get("returned_units")
    if isinstance(units, int) and isinstance(returned, int) and returned > units:
        return (
            "returned_units",
            str(returned),
            f"returned_units ({returned}) cannot exceed units_sold ({units})",
        )
    price = row.get("selling_price")
    discount = row.get("discount_per_unit")
    if isinstance(price, Decimal) and isinstance(discount, Decimal) and discount > price:
        return (
            "discount_per_unit",
            str(discount),
            f"discount_per_unit ({discount}) cannot exceed selling_price ({price})",
        )
    return None


def validate_products(data: bytes, *, filename: str = "products.csv") -> ValidationResult:
    """Validate a products CSV. Raises ``CsvReadError`` if the file is unreadable."""
    return _validate(data, PRODUCT_SPEC, filename=filename, known_skus=None, unique_key=None)


def validate_transactions(
    data: bytes,
    *,
    filename: str = "transactions.csv",
    known_skus: Collection[str] | None = None,
) -> ValidationResult:
    """Validate a transactions CSV, optionally against the SKUs already known.

    ``known_skus=None`` skips the referential check; the import task supplies the
    set once products are persisted.
    """
    return _validate(
        data,
        TRANSACTION_SPEC,
        filename=filename,
        known_skus=known_skus,
        unique_key="transaction_id",
    )
