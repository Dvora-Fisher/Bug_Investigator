from app.config import get_retries, get_timeout


def test_timeout_from_config():
    assert get_timeout({"network": {"timeout": 5}}) == 5


def test_retries_default():
    assert get_retries({}) == 3
