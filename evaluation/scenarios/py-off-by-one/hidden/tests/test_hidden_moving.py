from stats import moving_average


def test_window_of_one_returns_every_value():
    assert moving_average([3, 1, 2], 1) == [3.0, 1.0, 2.0]


def test_window_longer_than_values():
    assert moving_average([1, 2], 3) == []
