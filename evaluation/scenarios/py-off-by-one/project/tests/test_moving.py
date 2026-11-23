from stats import moving_average


def test_window_of_two():
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]


def test_window_equal_to_length():
    assert moving_average([2, 4, 6], 3) == [4.0]
