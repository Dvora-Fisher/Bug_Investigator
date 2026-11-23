"""User notification preferences.

digest_day uses ISO weekday numbers, the same as the settings page: Monday=1 ... Sunday=7.
"""

from dataclasses import dataclass, field

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class Preferences:
    digest_enabled: bool = True
    digest_day: int = 1
    timezone: str = "UTC"
    muted_topics: set[str] = field(default_factory=set)


def parse_day(name: str) -> int:
    """'Monday' -> 1 ... 'Sunday' -> 7 (as stored by the settings page)."""
    return DAY_NAMES.index(name.strip().lower()) + 1


def from_settings(form: dict) -> Preferences:
    return Preferences(
        digest_enabled=form.get("digest", "on") == "on",
        digest_day=parse_day(form.get("day", "monday")),
        timezone=form.get("tz", "UTC"),
        muted_topics={t.strip() for t in form.get("muted", "").split(",") if t.strip()},
    )
