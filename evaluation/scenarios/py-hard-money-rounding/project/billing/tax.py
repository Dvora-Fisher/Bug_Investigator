"""Sales tax. Rates are per region; all amounts are integer cents."""

RATES = {"NY": 0.08875, "CA": 0.0725, "TX": 0.0625, "OR": 0.0}


def tax_cents(subtotal_cents: int, region: str) -> int:
    rate = RATES.get(region.upper(), 0.0)
    # round half up to the cent (subtotals are never negative)
    return int(subtotal_cents * rate + 0.5)
