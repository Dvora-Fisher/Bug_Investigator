from pathlib import Path

import yaml


def load_settings(path: str | Path) -> dict:
    """Load the service settings from a YAML file; an empty file means no settings."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
