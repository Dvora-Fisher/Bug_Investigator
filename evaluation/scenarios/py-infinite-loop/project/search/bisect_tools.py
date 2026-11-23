def first_at_least(sorted_values: list[int], target: int) -> int:
    """Index of the first value >= target, or len(sorted_values) if there is none (like bisect_left)."""
    lo, hi = 0, len(sorted_values)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_values[mid] < target:
            lo = mid
        else:
            hi = mid
    return lo
