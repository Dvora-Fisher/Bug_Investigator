from .currency import format_cents
from .discounts import discount_cents
from .invoice import subtotal_cents
from .tax import tax_cents


def customer_total_cents(items, region: str = "OR", code: str | None = None) -> int:
    sub = subtotal_cents(items)
    sub -= discount_cents(sub, code)
    return sub + tax_cents(sub, region)


def monthly_report(customers: dict, region: str = "OR") -> list[str]:
    """One line per customer, 'name: $total', sorted by name."""
    return [f"{name}: {format_cents(customer_total_cents(items, region))}" for name, items in sorted(customers.items())]
