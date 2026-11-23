def format_cents(cents: int, symbol: str = "$") -> str:
    """1234567 -> '$12,345.67'; negative amounts get a leading minus."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{symbol}{cents // 100:,}.{cents % 100:02d}"
