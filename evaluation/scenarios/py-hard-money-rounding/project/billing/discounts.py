"""Discount codes. A discount never makes a subtotal negative."""

CODES = {"WELCOME10": ("percent", 10), "FIVEOFF": ("fixed", 500)}


def discount_cents(subtotal_cents: int, code: str | None) -> int:
    if not code:
        return 0
    kind, value = CODES.get(code.upper(), (None, 0))
    if kind == "percent":
        return subtotal_cents * value // 100  # rounds the discount down, in our favour
    if kind == "fixed":
        return min(value, subtotal_cents)
    return 0
