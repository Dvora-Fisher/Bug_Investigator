import threading
import time


class HitCounter:
    """Counts page hits from many request-handler threads."""

    def __init__(self) -> None:
        self.value = 0
        self._lock = threading.Lock()

    def hit(self) -> None:
        current = self.value
        time.sleep(0)  # simulates work between reading and writing (e.g. logging)
        self.value = current + 1


def count_concurrently(threads: int, hits_per_thread: int) -> int:
    counter = HitCounter()

    def worker() -> None:
        for _ in range(hits_per_thread):
            counter.hit()

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    return counter.value
