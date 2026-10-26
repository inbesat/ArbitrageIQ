"""T07 — the CSV attack and edge matrix.

Source of truth for the expectations asserted here:

- ``plans/ACCEPTANCE_TESTS.md`` **AT-5.8** (duplicate ``transaction_id`` within one
  file: the later row is rejected with a reason, the first is kept), **AT-5.17**
  (a spreadsheet formula payload in a text cell is stored as literal text at P0),
  **AT-5.18** (a filename containing ``../`` or a path is a display label only) and
  **AT-5.20** (the rejection report stays bounded).
- ``plans/SECURITY.md`` §3 (duplicate handling; repeat imports are skipped via a
  content hash on ``import_batch``) and §6.2 (the formula-injection table, which
  applies **at export time only, and only if the P1 export feature exists**).
- ``plans/ARCHITECTURE.md`` §4.1 (the rejection row is ``{row, field, value, reason}``).

Two AT-5 rows that T07 owns on paper are **moved, not dropped**, under T07's own
fallback (``plans/PHASES_DETAILED.md`` §T07):

- **AT-5.9** ("``0 imported, N skipped (duplicate)``, row count unchanged") and
  **AT-5.21** ("exactly one wins on content hash") are both properties of the
  ``import_batches.content_hash`` UNIQUE write, which does not exist until T09.
  T07 builds only the pure *detection* primitives — an in-file duplicate detector
  and a deterministic content hash — and T09 asserts the outcomes.
- A threaded concurrency test here would be a fake: ``validation.py`` is stateless,
  so two simultaneous calls prove nothing about a database race. Only hash
  determinism is asserted.

Every expected value below comes from the specification or from the fixture on
disk, never from the code under test.
"""

import ast
import hashlib
from datetime import date
from pathlib import Path

import pytest

from arbitrageiq.validation import (
    MAX_REPORTED_REJECTIONS,
    ValidationResult,
    content_hash,
    validate_transactions,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FORMULA_FIXTURE = FIXTURES_DIR / "malicious_formula_cells.csv"
DUPLICATE_FIXTURE = FIXTURES_DIR / "malicious_duplicate_transaction_ids.csv"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / "arbitrageiq"

TRANSACTION_HEADER = (
    "transaction_id,sku,order_date,units_sold,returned_units,selling_price,"
    "discount_per_unit,refund_per_returned_unit,settlement_fees_total,ads_cost,"
    "other_charges"
)
KNOWN_SKUS = frozenset({"BOTTLE-750"})

FORMULA_PAYLOADS = (
    "=cmd|'/c calc'!A0",
    "+1+1",
    "-2-2",
    "@SUM(1)",
)

HOSTILE_FILENAMES = (
    "../../etc/passwd.csv",
    "..\\..\\windows\\win.ini",
    "C:\\Users\\someone\\products.csv",
    "a\x00b.csv",
    "x" * 400 + ".csv",
    "",
    ".",
    "..",
)


def _row(
    transaction_id: str,
    *,
    order_date: str = "2026-09-15",
    units_sold: str = "1",
    returned_units: str = "0",
    selling_price: str = "1180.00",
    discount_per_unit: str = "0.00",
) -> str:
    return (
        f"{transaction_id},BOTTLE-750,{order_date},{units_sold},{returned_units},"
        f"{selling_price},{discount_per_unit},,,0.00,0.00"
    )


def _csv(*rows: str) -> bytes:
    return ("\n".join((TRANSACTION_HEADER, *rows)) + "\n").encode("utf-8")


def _rejects_text(result: ValidationResult) -> str:
    return " | ".join(
        f"{item.row}/{item.field}/{item.value}/{item.reason}" for item in result.rejected
    )


def _payloads(result: ValidationResult) -> list[str]:
    return [row["transaction_id"] for row in result.valid_rows]


# --------------------------------------------------------------------------- #
# AT-5.8 — duplicate transaction_id within one file
# --------------------------------------------------------------------------- #


def test_at_5_8_duplicate_transaction_id_keeps_the_first_and_rejects_the_later_rows():
    data = DUPLICATE_FIXTURE.read_bytes()

    result = validate_transactions(data, filename="duplicates.csv", known_skus=KNOWN_SKUS)

    assert result.valid_rows != []
    assert result.valid_rows[0]["transaction_id"] == "T99901"
    assert result.valid_rows[1]["transaction_id"] == "T99902"
    assert len(result.valid_rows) == 2
    assert result.rejected_total == 2
    assert [item.row for item in result.rejected] == [4, 5]


def test_at_5_8_duplicate_rejection_names_the_field_the_value_and_a_reason():
    result = validate_transactions(
        DUPLICATE_FIXTURE.read_bytes(), filename="duplicates.csv", known_skus=KNOWN_SKUS
    )

    for item in result.rejected:
        assert item.field == "transaction_id"
        assert item.value in {"T99901", "T99902"}
        assert item.reason
        assert "T999" in item.reason or "duplicate" in item.reason.lower()


def test_at_5_8_an_invalid_row_does_not_claim_the_key_so_the_first_valid_row_wins():
    data = _csv(
        # Row 2 is invalid for a different reason and must NOT consume the key.
        _row("Tx", units_sold="1", returned_units="9"),
        # Row 3 is the first VALID occurrence of "Tx" and must be kept.
        _row("Tx", order_date="2026-09-16"),
    )

    result = validate_transactions(data, filename="claim.csv", known_skus=KNOWN_SKUS)

    assert len(result.valid_rows) == 1
    assert result.valid_rows[0]["transaction_id"] == "Tx"
    assert [item.row for item in result.rejected] == [2]
    assert result.valid_rows[0]["order_date"] == date(2026, 9, 16)


def test_at_5_8_duplicate_rows_do_not_consume_the_rejection_report_cap():
    rows = [_row(f"T{n:05d}") for n in range(1, 61)]
    rows += [_row("T00001", order_date="2026-10-01")] * 40

    result = validate_transactions(_csv(*rows), filename="cap.csv", known_skus=KNOWN_SKUS)

    assert len(result.valid_rows) == 60
    assert result.rejected_total == 40
    assert len(result.rejected) == 40
    assert len(result.rejected) <= MAX_REPORTED_REJECTIONS


def test_at_5_8_unique_rows_are_unaffected_by_duplicate_detection():
    data = _csv(*[_row(f"U{n:05d}", order_date="2026-09-15") for n in range(1, 21)])

    result = validate_transactions(data, filename="clean.csv", known_skus=KNOWN_SKUS)

    assert len(result.valid_rows) == 20
    assert result.rejected_total == 0
    assert result.rejected == ()


# --------------------------------------------------------------------------- #
# AT-5.17 — a formula payload in a text cell is stored as literal text
# --------------------------------------------------------------------------- #


def test_at_5_17_formula_payload_is_stored_verbatim_in_the_valid_rows():
    result = validate_transactions(
        FORMULA_FIXTURE.read_bytes(), filename="formula.csv", known_skus=KNOWN_SKUS
    )

    assert _payloads(result) == list(FORMULA_PAYLOADS)


def test_at_5_17_formula_payload_does_not_change_any_row_outcome():
    result = validate_transactions(
        FORMULA_FIXTURE.read_bytes(), filename="formula.csv", known_skus=KNOWN_SKUS
    )

    assert len(result.valid_rows) == len(FORMULA_PAYLOADS)
    assert result.rejected_total == 0


@pytest.mark.parametrize("payload", FORMULA_PAYLOADS)
def test_at_5_17_no_field_or_message_marks_the_payload_as_executable(payload):
    result = validate_transactions(
        FORMULA_FIXTURE.read_bytes(), filename="formula.csv", known_skus=KNOWN_SKUS
    )

    haystack = (repr(result) + _rejects_text(result)).lower()

    # P0 storage is verbatim: no prefix, no strip, no neutralisation of the cell.
    assert payload in _payloads(result)
    assert haystack.count("neutralis") == haystack.count("export")
    for word in ("executable", "executed", "would run", "dangerous cell"):
        assert word not in haystack


# --------------------------------------------------------------------------- #
# AT-5.18 — a filename is a display label only, never a path
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("filename", HOSTILE_FILENAMES)
def test_at_5_18_a_hostile_filename_neither_raises_nor_changes_row_outcomes(filename):
    data = DUPLICATE_FIXTURE.read_bytes()

    result = validate_transactions(data, filename=filename, known_skus=KNOWN_SKUS)

    assert len(result.valid_rows) == 2
    assert result.rejected_total == 2


@pytest.mark.parametrize("filename", HOSTILE_FILENAMES)
def test_at_5_18_a_hostile_filename_is_never_echoed_in_a_rejection_or_warning(filename):
    result = validate_transactions(
        DUPLICATE_FIXTURE.read_bytes(), filename=filename, known_skus=KNOWN_SKUS
    )
    baseline = validate_transactions(
        DUPLICATE_FIXTURE.read_bytes(), filename="clean.csv", known_skus=KNOWN_SKUS
    )

    haystack = _rejects_text(result) + " | ".join(str(item) for item in result.warnings)
    baseline_haystack = _rejects_text(baseline) + " | ".join(
        str(item) for item in baseline.warnings
    )

    # The label must not reach any message: a hostile label and a benign label
    # produce byte-identical text. This holds for the empty label too, so the
    # case is asserted rather than skipped.
    assert haystack == baseline_haystack
    assert filename not in haystack or not filename


def test_at_5_18_the_label_is_not_resolved_or_opened_as_a_path():
    result = validate_transactions(
        _csv(_row("T1")), filename="../../etc/passwd.csv", known_skus=KNOWN_SKUS
    )

    assert len(result.valid_rows) == 1
    assert "passwd" not in _rejects_text(result)


# --------------------------------------------------------------------------- #
# AT-5.9 / AT-5.21 — the detection primitives only (outcomes are T09's)
# --------------------------------------------------------------------------- #


def test_content_hash_is_a_lowercase_sha256_hex_digest_of_the_exact_bytes():
    data = b"a,b\n1,2\n"

    digest = content_hash(data)

    assert digest == hashlib.sha256(data).hexdigest()
    assert len(digest) == 64
    assert digest == digest.lower()


def test_content_hash_is_deterministic_for_identical_bytes():
    data = b"transaction_id,sku\nT1,BOTTLE-750\n"

    assert content_hash(data) == content_hash(bytes(data))


def test_content_hash_changes_when_a_single_byte_changes():
    assert content_hash(b"1180.00") != content_hash(b"1180.01")


def test_content_hash_does_not_depend_on_the_display_label():
    data = b"transaction_id,sku\nT1,BOTTLE-750\n"

    # ``content_hash`` accepts bytes only, so no display label can reach it.
    assert content_hash(data) == content_hash(bytes(data))
    assert content_hash(data) == hashlib.sha256(data).hexdigest()


def test_content_hash_does_not_touch_a_database_or_the_filesystem():
    source = (PACKAGE_DIR / "validation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    assert imported.isdisjoint(
        {"sqlalchemy", "sqlite3", "requests", "httpx", "urllib", "os", "pathlib", "subprocess"}
    )
    assert imported <= {
        "__future__",
        "collections",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "io",
        "pandas",
    }
