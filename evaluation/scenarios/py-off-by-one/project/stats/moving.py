"""Rolling statistics over a list of numbers."""


def moving_average(values: list[float], window: int) -> list[float]:
    """Average of every consecutive `window`-sized slice of `values`."""
    if window <= 0:
        raise ValueError("window must be positive")
    averages = []
    for start in range(len(values) - window):
        chunk = values[start:start + window]
        averages.append(sum(chunk) / window)
    return averages
