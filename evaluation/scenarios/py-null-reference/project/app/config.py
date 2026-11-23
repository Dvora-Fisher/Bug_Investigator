"""Reads connection settings from a parsed configuration dictionary."""

DEFAULT_TIMEOUT = 30


def get_timeout(config: dict) -> int:
    """Network timeout in seconds; DEFAULT_TIMEOUT when not configured."""
    return int(config.get("network").get("timeout", DEFAULT_TIMEOUT))


def get_retries(config: dict) -> int:
    return int(config.get("retries", 3))
