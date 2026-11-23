from billing.loader import load_csv
from billing.models import LineItem
from billing.normalize import to_cents
from billing.report import customer_total_cents, monthly_report


def test_to_cents_is_exact_for_common_prices():
    assert [to_cents(x) for x in (19.99, 0.29, 1.15, 4.35, 5)] == [1999, 29, 115, 435, 500]


def test_single_item_customer():
    assert monthly_report({"Dana": [LineItem("SKU-1", "Annual plan", 19.99)]}) == ["Dana: $19.99"]


def test_csv_prices_are_not_truncated():
    items = load_csv("sku,description,price,qty\nab,Seat,0.29,3\n")
    assert customer_total_cents(items) == 87
