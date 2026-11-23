import threading


def finishes_within(seconds: float, fn, *args):
    """Run fn in a daemon thread; fail instead of hanging forever if it does not return in time."""
    result = []
    worker = threading.Thread(target=lambda: result.append(fn(*args)), daemon=True)
    worker.start()
    worker.join(seconds)
    assert not worker.is_alive(), f"{fn.__name__}{args} did not finish within {seconds}s (infinite loop?)"
    return result[0]
