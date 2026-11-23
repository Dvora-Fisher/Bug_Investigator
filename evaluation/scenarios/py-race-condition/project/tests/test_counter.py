from metrics.counter import HitCounter, count_concurrently


def test_single_thread():
    c = HitCounter()
    for _ in range(10):
        c.hit()
    assert c.value == 10


def test_many_threads():
    assert count_concurrently(threads=8, hits_per_thread=250) == 2000
