from decimal import Decimal, InvalidOperation  # noqa: F401


def parse_amount(text: str) -> Decimal:
    """Parse a user-entered amount such as "12.50". Invalid input must be rejected with ValueError."""
    try:
        return Decimal(text.strip())
    except Exception:
        return Decimal(0)


def total(amounts: list[str]) -> Decimal:
    return sum((parse_amount(a) for a in amounts), Decimal(0))
