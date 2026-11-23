from billing.currency import format_cents
from billing.customers import group_by_customer
from billing.discounts import discount_cents
from billing.loader import load_csv
from billing.models import LineItem
from billing.report import customer_total_cents, monthly_report
from billing.tax import tax_cents


def test_format_cents():
    assert format_cents(123456) == "$1,234.56"
    assert format_cents(-5) == "-$0.05"


def test_tax_and_discount():
    assert tax_cents(1000, "NY") == 89
    assert discount_cents(2000, "WELCOME10") == 200
    assert discount_cents(300, "FIVEOFF") == 300


def test_monthly_report():
    customers = {"Avi": [LineItem("A", "Plan", 10.50, 2), LineItem("B", "Seat", 2.25)], "Dana": [LineItem("C", "x", 4.0)]}
    assert monthly_report(customers) == ["Avi: $23.25", "Dana: $4.00"]


def test_total_with_discount_and_tax():
    assert customer_total_cents([LineItem("A", "Plan", 20.0)], region="NY", code="WELCOME10") == 1800 + 160


def test_load_csv_and_group():
    items = load_csv("sku,description,price,qty\nab, Plan ,\"1,299.50\",1\n")
    assert items == [LineItem("AB", "Plan", 1299.5, 1)]
    assert group_by_customer([("dana", items[0])]) == {"Dana": items}
