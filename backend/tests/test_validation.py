"""T06 acceptance tests: CSV validation (text-first reading, rejects, caps).

Expectations come from ``plans/ACCEPTANCE_TESTS.md`` AT-5 (rows 5.1-5.7,
5.10-5.16, 5.19, 5.20, 5.22) and from ``plans/SECURITY.md`` section 3, never from
the implementation under test (``plans/BUSINESS_RULES.md`` section 10.4.2).

Scope note. AT-5 names HTTP statuses (422 / 413 / 200). Those belong to the API,
which is ``backend/arbitrageiq/api.py`` - task T10's file, not T06's. T06 owns
``validation.py`` only, so these tests assert the *typed error* and the *reason
text* and leave the status codes to T10. The reading-specific rows AT-5.8, 5.9,
5.17, 5.18 and 5.21 belong to T07 and are not claimed here.

Inputs are passed as ``bytes`` rather than file paths on purpose: a filename is
only ever a display label (AT-5.18, ``plans/SECURITY.md`` section 2 rule T4), and
this module performs no I/O of its own.
"""

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from arbitrageiq.validation import (
    MAX_DATA_ROWS,
    MAX_FILE_BYTES,
    MAX_REPORTED_REJECTIONS,
    PRODUCT_SPEC,
    TRANSACTION_SPEC,
    CsvLimitError,
    CsvReadError,
    validate_products,
    validate_transactions,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "arbitrageiq"


# --- fixture builders -------------------------------------------------------

PRODUCT_HEADER = (
    "sku,name,category,supplier_unit_cost,inbound_unit_cost,"
    "packaging_unit_cost,target_price,current_stock,min_order_qty,max_supply"
)
PRODUCT_ROW = "BOTTLE-750,Steel Bottle,kitchen,440.00,8.00,6.00,799.00,60,12,240"

TRANSACTION_HEADER = (
    "transaction_id,sku,order_date,units_sold,returned_units,selling_price,"
    "discount_per_unit,refund_per_returned_unit,settlement_fees_total,"
    "ads_cost,other_charges"
)
TRANSACTION_ROW = "T00001,BOTTLE-750,2026-09-15,10,1,1180.00,0.00,,,200.00,0.00"

#: The SKU the golden-style transaction row refers to.
KNOWN_SKUS = frozenset({"BOTTLE-750"})


def products_csv(*rows: str, header: str = PRODUCT_HEADER) -> bytes:
    body = "\n".join((header, *rows))
    return (body + "\n").encode("utf-8")


def transactions_csv(*rows: str, header: str = TRANSACTION_HEADER) -> bytes:
    body = "\n".join((header, *rows))
    return (body + "\n").encode("utf-8")


def rejects_text(result) -> str:
    """Every reason and value a caller could ever display, joined."""
    return " | ".join(f"{r.field}={r.value} {r.reason}" for r in result.rejected)


def _csv_field(value: str) -> str:
    """Encode one field the way a real CSV file would.

    A money value such as ``₹1,180`` contains a comma, so an unquoted
    interpolation would split into two cells and the file under test would
    not be the file the case describes.
    """
    if "," in value or '"' in value:
        return '"' + value.replace('"', '""') + '"'
    return value


# --- AT-5.1 to AT-5.7: file-level outcomes ----------------------------------


def test_at_5_1_missing_required_column_lists_every_missing_name():
    # 'sku' and 'target_price' are both absent, so both must be named.
    header = PRODUCT_HEADER.replace("sku,", "").replace(",target_price", "")
    with pytest.raises(CsvReadError) as excinfo:
        validate_products(products_csv(PRODUCT_ROW, header=header), filename="products.csv")
    message = str(excinfo.value)
    assert "sku" in message
    assert "target_price" in message


def test_at_5_2_extra_column_is_accepted_and_reported_as_a_warning():
    header = f"{PRODUCT_HEADER},supplier_notes"
    data = products_csv(f"{PRODUCT_ROW},ignore me", header=header)
    result = validate_products(data, filename="products.csv")
    assert len(result.valid_rows) == 1
    assert result.rejected_total == 0
    assert any("supplier_notes" in warning for warning in result.warnings)


def test_at_5_3_empty_file_is_rejected_as_empty():
    with pytest.raises(CsvReadError, match="file is empty"):
        validate_products(b"", filename="products.csv")


def test_at_5_4_header_only_file_has_zero_valid_and_zero_rejected():
    result = validate_products(products_csv(), filename="products.csv")
    assert result.valid_rows == ()
    assert result.rejected == ()
    assert result.rejected_total == 0
    assert result.row_count == 0


def test_at_5_5_binary_content_is_not_a_readable_text_file():
    binary = b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff\xfe\x00binary"
    with pytest.raises(CsvReadError, match="not a readable CSV/text file"):
        validate_products(binary, filename="products.csv")


def test_at_5_6_malformed_quoted_csv_reports_a_row_number():
    malformed = products_csv(
        'BROKEN-1,"unterminated,kitchen,1.00,1.00,1.00,2.00,1,1,1',
    )
    with pytest.raises(CsvReadError) as excinfo:
        validate_products(malformed, filename="products.csv")
    # Best-effort line fidelity: the message must carry a row number, not an
    # exact offset (the underlying parser's line reporting is approximate).
    assert "row" in str(excinfo.value).lower()


def test_at_5_7_utf8_bom_prefix_is_accepted_and_headers_normalised():
    data = b"\xef\xbb\xbf" + products_csv(PRODUCT_ROW)
    result = validate_products(data, filename="products.csv")
    assert len(result.valid_rows) == 1
    assert result.valid_rows[0]["sku"] == "BOTTLE-750"


# --- header normalisation and text preservation -----------------------------


def test_header_case_and_surrounding_whitespace_are_normalised():
    header = ",".join(f"  {name.upper()}  " for name in PRODUCT_HEADER.split(","))
    result = validate_products(products_csv(PRODUCT_ROW, header=header))
    assert len(result.valid_rows) == 1


def test_text_is_read_as_text_so_001_stays_001_and_blank_stays_blank():
    # dtype=str with NA filtering off: '001' must not become 1, and an absent
    # optional value must not become NaN (plans/TECH_STACK.md section 2.1).
    header = f"{TRANSACTION_HEADER},legacy_ref"
    row = f"{TRANSACTION_ROW},001"
    result = validate_transactions(transactions_csv(row, header=header), known_skus=KNOWN_SKUS)
    assert len(result.valid_rows) == 1
    row_out = result.valid_rows[0]
    assert row_out["legacy_ref"] == "001"
    assert row_out["refund_per_returned_unit"] is None
    assert row_out["settlement_fees_total"] is None
    assert isinstance(row_out["legacy_ref"], str)


def test_the_one_documented_alias_refund_inclusive_per_return_is_accepted():
    # plans/DECISIONS.md ADR-021/ADR-022: only this alias is documented.
    header = TRANSACTION_HEADER.replace("refund_per_returned_unit", "refund_inclusive_per_return")
    result = validate_transactions(
        transactions_csv(TRANSACTION_ROW, header=header), known_skus=KNOWN_SKUS
    )
    assert len(result.valid_rows) == 1


# --- AT-5.10 to AT-5.14: row-level rejects ----------------------------------


def test_at_5_10_returned_units_greater_than_units_sold_is_rejected():
    row = "T00001,BOTTLE-750,2026-09-15,1,2,1180.00,0.00,,,0.00,0.00"
    result = validate_transactions(transactions_csv(row), known_skus=KNOWN_SKUS)
    assert result.valid_rows == ()
    assert result.rejected_total == 1
    assert "returned_units" in rejects_text(result)


def test_at_5_11_discount_greater_than_selling_price_is_rejected():
    row = "T00001,BOTTLE-750,2026-09-15,1,0,100.00,150.00,,,0.00,0.00"
    result = validate_transactions(transactions_csv(row), known_skus=KNOWN_SKUS)
    assert result.valid_rows == ()
    assert "discount_per_unit" in rejects_text(result)


@pytest.mark.parametrize("bad_value", ["abc", "\u20b91,180", "1180.00.00"])
def test_at_5_12_non_numeric_money_quotes_the_offending_value(bad_value):
    row = f"T00001,BOTTLE-750,2026-09-15,1,0,{_csv_field(bad_value)},0.00,,,0.00,0.00"
    result = validate_transactions(transactions_csv(row), known_skus=KNOWN_SKUS)
    assert result.valid_rows == ()
    assert result.rejected_total == 1
    assert result.rejected[0].value == bad_value
    assert "selling_price" in result.rejected[0].field


def test_at_5_13_negative_value_in_a_non_negative_field_is_rejected():
    result = validate_products(
        products_csv("BOTTLE-750,Steel Bottle,kitchen,-440.00,8,6,799,60,12,240")
    )
    assert result.valid_rows == ()
    assert "supplier_unit_cost" in rejects_text(result)


def test_at_5_14_unknown_sku_is_rejected_citing_the_sku():
    row = "T00001,GHOST-SKU,2026-09-15,1,0,1180.00,0.00,,,0.00,0.00"
    result = validate_transactions(transactions_csv(row), known_skus=KNOWN_SKUS)
    assert result.valid_rows == ()
    assert result.rejected_total == 1
    assert "GHOST-SKU" in rejects_text(result)


# --- AT-5.15 and AT-5.16: caps, enforced before parsing ---------------------


def test_at_5_15_file_over_the_size_cap_raises_the_size_cap_error():
    oversized = b"a" * (MAX_FILE_BYTES + 1)
    with pytest.raises(CsvLimitError) as excinfo:
        validate_products(oversized, filename="products.csv")
    assert excinfo.value.cap == "size"
    assert excinfo.value.limit == MAX_FILE_BYTES
    assert "size" in str(excinfo.value).lower()


def test_at_5_16_more_than_the_row_cap_raises_the_row_cap_error():
    rows = [PRODUCT_ROW.replace("BOTTLE-750", f"SKU-{i}") for i in range(MAX_DATA_ROWS + 1)]
    with pytest.raises(CsvLimitError) as excinfo:
        validate_products(products_csv(*rows), filename="products.csv")
    assert excinfo.value.cap == "rows"
    assert excinfo.value.limit == MAX_DATA_ROWS
    assert "row" in str(excinfo.value).lower()


def test_the_cap_error_is_a_subclass_of_the_read_error():
    # T10 maps one subclass to 413 and the parent to 422 without a new contract.
    assert issubclass(CsvLimitError, CsvReadError)


# --- AT-5.19, AT-5.20, AT-5.22 ---------------------------------------------


def test_at_5_19_mixed_rows_keep_the_valid_ones_and_report_every_reject():
    rows = [
        PRODUCT_ROW,
        "BROKEN-1,No cost,decor,-1.00,1,1,2,1,1,1",
        "BROKEN-2,No price,decor,1.00,1,1,not-a-price,1,1,1",
        PRODUCT_ROW.replace("BOTTLE-750", "TORAN-FLW-1"),
    ]
    result = validate_products(products_csv(*rows))
    assert len(result.valid_rows) == 2
    assert result.rejected_total == 2
    assert [r.row for r in result.rejected] == [3, 4]
    assert all(r.reason for r in result.rejected)
    assert all(isinstance(r.field, str) and r.field for r in result.rejected)


def test_at_5_20_the_rejection_report_is_capped_and_summarised():
    bad_rows = [f"BAD-{i},No cost,decor,-1.00,1,1,2,1,1,1" for i in range(19_000)]
    result = validate_products(products_csv(*bad_rows))
    assert result.valid_rows == ()
    assert result.rejected_total == 19_000
    assert len(result.rejected) == MAX_REPORTED_REJECTIONS
    assert MAX_REPORTED_REJECTIONS < 19_000


def test_at_5_22_no_message_contains_a_path_sql_or_traceback():
    cases = [
        products_csv(PRODUCT_ROW),
        products_csv("BROKEN-1,No cost,decor,-1.00,1,1,2,1,1,1"),
        b"",
        b"\x89PNG\x00\xffbinary",
    ]
    texts = []
    for data in cases:
        try:
            result = validate_products(data, filename="../../etc/passwd.csv")
        except CsvReadError as error:
            texts.append(str(error))
        else:
            texts.append(repr(result))
    joined = " | ".join(texts)
    for forbidden in ("Traceback", 'File "', "SELECT", "INSERT", "sqlite", "C:\\", "E:\\"):
        assert forbidden not in joined


def test_the_display_filename_is_never_used_as_a_path():
    # AT-5.18's rule is T07's to assert end-to-end, but the label must not leak
    # into a message here either.
    result = validate_products(products_csv(PRODUCT_ROW), filename="../private/leak.csv")
    assert "private" not in repr(result)


# --- import boundary --------------------------------------------------------


def test_validation_module_may_import_pandas_and_stdlib_only():
    source = (PACKAGE_DIR / "validation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    # plans/ARCHITECTURE.md section 3: validation must not import profit, db or api.
    assert modules.isdisjoint({"arbitrageiq.profit", "arbitrageiq.db", "arbitrageiq.api"})
    assert "pandas" in modules


def test_the_two_specs_declare_the_canonical_columns():
    # plans/BUSINESS_RULES.md section 3 / plans/DECISIONS.md ADR-021.
    product_names = [spec.name for spec in PRODUCT_SPEC]
    transaction_names = [spec.name for spec in TRANSACTION_SPEC]
    assert product_names[:1] == ["sku"] and "cost_updated_on" in product_names
    assert set(product_names) >= {
        "sku",
        "name",
        "category",
        "supplier_unit_cost",
        "inbound_unit_cost",
        "packaging_unit_cost",
        "target_price",
        "current_stock",
        "min_order_qty",
        "max_supply",
    }
    assert set(transaction_names) >= {
        "transaction_id",
        "sku",
        "order_date",
        "units_sold",
        "returned_units",
        "selling_price",
        "discount_per_unit",
        "refund_per_returned_unit",
        "settlement_fees_total",
        "ads_cost",
        "other_charges",
    }


def test_money_cells_are_parsed_to_decimal_never_float():
    result = validate_products(products_csv(PRODUCT_ROW))
    row = result.valid_rows[0]
    assert row["supplier_unit_cost"] == Decimal("440.00")
    assert isinstance(row["supplier_unit_cost"], Decimal)
    assert not isinstance(row["supplier_unit_cost"], float)
    assert isinstance(row["current_stock"], int)
    assert not isinstance(row["current_stock"], bool)
