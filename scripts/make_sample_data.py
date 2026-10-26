"""Deterministic synthetic fixtures for ArbitrageIQ (task T08).

Every value here is invented. There is no real brand, person, phone number,
address or order ID anywhere in the output (``plans/SECURITY.md`` §4.1), and no
real Amazon or Indian tax figure is claimed (``plans/BUSINESS_RULES.md`` §10).

Determinism (``plans/BUSINESS_RULES.md`` §11.5 rule B7, ``plans/TECH_STACK.md``
§5.5): the same command produces byte-identical output on every run. This module
therefore consults no wall clock and uses no randomness — every value is fixed,
or derived arithmetically from a fixed value. Regression-guarded: a test asserts
that this source file names no wall-clock helper.

Per ``plans/DECISIONS.md`` ADR-020 the portfolio total is **not** a fixed
target: the data is not tuned to any particular sum. What the fixture does
guarantee is that at least one SKU loses money, and that both the return path
and the settlement-override path are exercised.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
PRODUCTS_CSV = SAMPLE_DIR / "products_sample.csv"
TRANSACTIONS_CSV = SAMPLE_DIR / "transactions_sample.csv"

PRODUCT_HEADER = (
    "sku,name,category,supplier_unit_cost,inbound_unit_cost,packaging_unit_cost,"
    "target_price,current_stock,min_order_qty,max_supply,cost_updated_on"
)

TRANSACTION_HEADER = (
    "transaction_id,sku,order_date,units_sold,returned_units,selling_price,"
    "discount_per_unit,refund_per_returned_unit,settlement_fees_total,ads_cost,"
    "other_charges"
)

#: sku, name, category, supplier, inbound, packaging, target price, stock, moq,
#: max supply, cost_updated_on. Landed cost is supplier + inbound + packaging.
PRODUCTS = (
    ("DIYA-SET-12", "Painted Diya Set 12 pcs", "festive", "210.00", "6.00", "6.00",
     "499.00", "30", "6", "200", "2026-10-10"),
    ("RANG-KIT-01", "Rangoli Stencil and Colour Kit", "festive", "120.00", "3.00", "3.00",
     "299.00", "80", "24", "500", "2026-10-08"),
    ("POTLI-SLK-1", "Silk Potli Gift Bag", "gifting", "260.00", "4.00", "3.00",
     "549.00", "15", "10", "150", "2026-09-02"),
    ("TORAN-FLW-1", "Artificial Flower Door Toran", "decor", "250.00", "6.00", "5.00",
     "549.00", "25", "6", "120", "2026-10-12"),
    ("BOTTLE-750", "Steel Bottle 750ml", "kitchen", "440.00", "8.00", "6.00",
     "799.00", "60", "12", "240", "2026-10-01"),
    ("PHONE-STND", "Foldable Phone Stand", "accessories", "85.00", "2.00", "2.00",
     "249.00", "200", "50", "600", "2026-10-11"),
    ("CNDL-GIFT-1", "Scented Candle Gift Box", "gifting", "400.00", "7.00", "8.00",
     "749.00", "10", "8", "100", "2026-10-09"),
    ("KURTA-M-L", "Men Cotton Kurta L", "apparel", "720.00", "12.00", "10.00",
     "1299.00", "12", "6", "60", "2026-08-20"),
    # Deliberately priced below landed cost: this is the loss-making SKU the
    # acceptance suite requires, so the engine is never flattered.
    ("EARBUD-BT-1", "Budget Bluetooth Earbuds", "electronics", "980.00", "10.00", "12.00",
     "1150.00", "8", "5", "50", "2026-10-13"),
    ("TIFFIN-3", "Stainless Steel Tiffin 3 tier", "kitchen", "380.00", "9.00", "7.00",
     "899.00", "40", "10", "180", "2026-10-04"),
)

#: Fixed synthetic order dates, all in 2026. No clock is consulted.
ORDER_DATES = ("2026-09-15", "2026-09-25", "2026-10-05", "2026-10-15")

_UNITS_PATTERN = (1, 2, 1, 3, 1, 2, 4, 1)
_DISCOUNTS = ("0.00", "0.00", "50.00", "0.00")
_ADS_PER_UNIT = Decimal("8.00")
#: GST-inclusive settlement figures; the override path is exercised by these.
_SETTLEMENTS = ("181.63", "216.00", "154.10")


def build_products_csv() -> str:
    """The products fixture, as text."""
    lines = [PRODUCT_HEADER]
    lines.extend(",".join(row) for row in PRODUCTS)
    return "\n".join(lines) + "\n"


def build_transactions_csv() -> str:
    """The transactions fixture, as text. Fully deterministic."""
    lines = [TRANSACTION_HEADER]
    number = 0
    for product_index, product in enumerate(PRODUCTS):
        sku = product[0]
        selling_price = product[6]
        for slot, order_date in enumerate(ORDER_DATES):
            number += 1
            step = product_index + slot
            units_sold = _UNITS_PATTERN[step % len(_UNITS_PATTERN)]
            returned_units = 1 if step % 7 == 0 else 0
            discount = _DISCOUNTS[step % len(_DISCOUNTS)]
            settlement = _SETTLEMENTS[step % len(_SETTLEMENTS)] if step % 13 == 0 else ""
            ads = str(Decimal(units_sold) * _ADS_PER_UNIT)
            lines.append(
                ",".join(
                    (
                        f"T{number:05d}",
                        sku,
                        order_date,
                        str(units_sold),
                        str(returned_units),
                        selling_price,
                        discount,
                        "",
                        settlement,
                        ads,
                        "0.00",
                    )
                )
            )
    return "\n".join(lines) + "\n"


def build_fixtures() -> tuple[str, str]:
    """Return ``(products_csv_text, transactions_csv_text)``."""
    return build_products_csv(), build_transactions_csv()


def write_fixtures() -> tuple[Path, Path]:
    """Write both fixtures under ``data/sample/`` with UTF-8 and LF endings."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    products_text, transactions_text = build_fixtures()
    PRODUCTS_CSV.write_text(products_text, encoding="utf-8", newline="\n")
    TRANSACTIONS_CSV.write_text(transactions_text, encoding="utf-8", newline="\n")
    return PRODUCTS_CSV, TRANSACTIONS_CSV


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] != "write":
        print("usage: python scripts/make_sample_data.py [write]", file=sys.stderr)
        return 2
    products_path, transactions_path = write_fixtures()
    products_text, transactions_text = build_fixtures()
    print(f"wrote {products_path} ({len(products_text.splitlines()) - 1} data rows)")
    print(f"wrote {transactions_path} ({len(transactions_text.splitlines()) - 1} data rows)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
