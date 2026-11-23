from dataclasses import dataclass, field

from .preferences import Preferences


@dataclass
class User:
    id: int
    email: str
    prefs: Preferences = field(default_factory=Preferences)
    unsubscribed: bool = False
