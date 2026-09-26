from decimal import Decimal

import pytest

from docduel.datasets.cord import to_schema
from docduel.scoring.normalise import normalise_text, parse_amount, parse_quantity


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("25.000", "25000"),
        ("25,000", "25000"),
        ("1.250.500", "1250500"),
        ("Rp 25.000", "25000"),
        ("12.50", "12.50"),
        ("-5,000", "-5000"),
        ("Rp. 0", "0"),
        ("@28,000", "28000"),
        ("*12500", "12500"),
        ("12500.00", "12500.00"),
        ("9,999,999", "9999999"),
        ("$1,234.56", "1234.56"),
        ("", None),
        ("abc", None),
        (None, None),
    ],
)
def test_parse_amount(raw, expected):
    got = parse_amount(raw)
    assert got == (Decimal(expected) if expected is not None else None)


@pytest.mark.parametrize(("raw", "q"), [("1X", 1), ("x2", 2), ("3 x", 3), ("2Prs", 2), ("", None)])
def test_parse_quantity(raw, q):
    assert parse_quantity(raw) == (Decimal(q) if q is not None else None)


def test_normalise_text():
    assert normalise_text("  Blue-Fig CAFÉ, Pty. ") == "blue fig café pty"


def test_cord_single_menu_with_modifiers():
    gt = {
        "menu": {
            "nm": "M-Caramel Black Tea",
            "unitprice": "@28,000",
            "cnt": "1X",
            "price": "28,000",
            "sub": [{"nm": "70%"}, {"nm": "Less Ice"}],
        },
        "sub_total": {"subtotal_price": "28,000", "tax_price": "0"},
        "total": {"total_price": "28,000", "cashprice": "28,000", "changeprice": "0"},
    }
    r = to_schema(gt)
    assert r.currency == "IDR"
    assert r.vendor_name is None and r.document_date is None
    assert len(r.line_items) == 1  # unpriced modifiers are not line items
    item = r.line_items[0]
    assert (item.quantity, item.unit_price, item.amount) == (1, 28000, 28000)
    assert (r.subtotal, r.tax, r.total, r.payment_method) == (28000, 0, 28000, "cash")


def test_cord_list_menu_priced_sub_discount_card():
    gt = {
        "menu": [
            {"nm": "NASI GORENG", "cnt": "2", "price": "50.000"},
            {
                "nm": "ES TEH",
                "cnt": "1",
                "price": "8.000",
                "sub": {"nm": "Extra", "price": "2.000"},
            },
        ],
        "sub_total": {
            "subtotal_price": "60.000",
            "discount_price": "-5,000",
            "service_price": "3.000",
        },
        "total": {"total_price": "58.000", "creditcardprice": "58.000"},
    }
    r = to_schema(gt)
    assert [i.description for i in r.line_items] == ["NASI GORENG", "ES TEH", "Extra"]
    assert r.discount == 5000 and r.service_charge == 3000
    assert r.payment_method == "card"


def test_cord_conflicting_list_value_is_unknown():
    r = to_schema({"menu": [], "total": {"total_price": ["10.000", "12.000"]}})
    assert r.total is None
