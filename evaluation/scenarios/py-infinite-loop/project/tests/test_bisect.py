from search.bisect_tools import first_at_least
from tests.helpers import finishes_within


def test_target_at_start():
    assert finishes_within(2, first_at_least, [1, 3, 5, 7], 1) == 0


def test_target_in_the_middle():
    assert finishes_within(2, first_at_least, [1, 3, 5, 7], 5) == 2
