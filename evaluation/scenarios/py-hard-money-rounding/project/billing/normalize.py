"""Turns raw invoice rows (CSV export or API) into LineItem objects, and converts amounts to cents."""

from .models import LineItem


def to_cents(amount: float) -> int:
    """Convert an amount such as 19.99 to integer cents (1999)."""
    return int(amount * 100)


def parse_amount(text: str) -> float:
    """'1,299.50' -> 1299.5 ; '$5' -> 5.0 ; '' -> 0.0"""
    cleaned = text.strip().replace("$", "").replace(",", "")
    return float(cleaned) if cleaned else 0.0


def normalize_row(row: dict) -> LineItem:
    return LineItem(
        sku=row["sku"].strip().upper(),
        description=(row.get("description") or "").strip(),
        unit_price=parse_amount(str(row["price"])),
        quantity=int(row.get("qty") or 1),
    )
