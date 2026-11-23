"""Groups line items per customer for the monthly report."""

from collections import defaultdict


def group_by_customer(rows: list[tuple[str, object]]) -> dict:
    grouped = defaultdict(list)
    for customer, item in rows:
        grouped[customer.strip().title()].append(item)
    return dict(grouped)
