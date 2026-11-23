import bisect

import pytest

from search.bisect_tools import first_at_least
from tests.helpers import finishes_within

VALUES = [2, 4, 4, 8, 16]


@pytest.mark.parametrize("target", [0, 2, 3, 4, 5, 8, 16, 17])
def test_matches_bisect_left(target):
    assert finishes_within(2, first_at_least, VALUES, target) == bisect.bisect_left(VALUES, target)


def test_empty_list():
    assert finishes_within(2, first_at_least, [], 3) == 0
