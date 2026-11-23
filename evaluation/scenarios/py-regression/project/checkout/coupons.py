"""Coupon handling. v2.1: coupons became optional to simplify callers (see CHANGELOG.md)."""


def apply_coupons(price: float, new_coupons: list[float] | None = None, coupons: list[float] = []) -> float:
    """Apply percentage coupons (e.g. 10 for 10%) to a price; returns the discounted price."""
    for c in new_coupons or []:
        coupons.append(c)
    for c in coupons:
        price = price * (1 - c / 100)
    return round(price, 2)
