from .models import LineItem
from .normalize import to_cents


def line_total_cents(item: LineItem) -> int:
    return to_cents(item.unit_price) * item.quantity


def subtotal_cents(items: list[LineItem]) -> int:
    return sum(line_total_cents(i) for i in items)
