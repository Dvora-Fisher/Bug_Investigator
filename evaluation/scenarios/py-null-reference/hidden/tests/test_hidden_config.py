from app.config import DEFAULT_TIMEOUT, get_timeout


def test_missing_network_section_uses_default():
    assert get_timeout({}) == DEFAULT_TIMEOUT


def test_network_without_timeout_uses_default():
    assert get_timeout({"network": {}}) == DEFAULT_TIMEOUT


def test_explicit_timeout_still_wins():
    assert get_timeout({"network": {"timeout": "7"}}) == 7
