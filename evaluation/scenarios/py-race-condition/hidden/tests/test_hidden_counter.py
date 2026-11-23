import pytest

from metrics.counter import count_concurrently


@pytest.mark.parametrize("threads,hits", [(4, 500), (16, 100), (2, 1000)])
def test_no_lost_updates(threads, hits):
    assert count_concurrently(threads, hits) == threads * hits
