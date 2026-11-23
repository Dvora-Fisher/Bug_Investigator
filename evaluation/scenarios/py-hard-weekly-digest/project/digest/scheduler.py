"""Decides who gets the weekly digest today. run.py calls this once a day from cron."""

from datetime import datetime


def wants_digest(user) -> bool:
    return user.prefs.digest_enabled and not user.unsubscribed and "@" in user.email


def due_users(users, now: datetime) -> list:
    """Users whose chosen digest day is today."""
    today = now.weekday()
    return [u for u in users if wants_digest(u) and u.prefs.digest_day == today]
