from datetime import datetime

from digest.preferences import Preferences
from digest.run import run_daily
from digest.scheduler import due_users
from digest.users import User

SUNDAY = datetime(2026, 11, 22, 8, 0)
MONDAY = datetime(2026, 11, 23, 8, 0)
TUESDAY = datetime(2026, 11, 24, 8, 0)


def _user(uid, day):
    return User(uid, f"u{uid}@example.com", Preferences(digest_day=day))


def test_sunday_users_get_the_digest_on_sunday():
    assert [u.id for u in due_users([_user(1, 7), _user(2, 1)], SUNDAY)] == [1]


def test_monday_users_get_it_on_monday_only():
    users = [_user(1, 1), _user(2, 2)]
    assert [u.id for u in due_users(users, MONDAY)] == [1]
    assert [u.id for u in due_users(users, TUESDAY)] == [2]


def test_run_daily_sends_to_sunday_users():
    sent = run_daily([_user(7, 7)], SUNDAY, lambda u: [{"topic": "news", "title": "x"}],
                     type("M", (), {"send": lambda self, m: True})())
    assert sent == ["u7@example.com"]
