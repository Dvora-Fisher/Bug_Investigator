from .builder import build_digest
from .scheduler import due_users


def run_daily(users, now, items_for, mailer) -> list[str]:
    """Send today's digests; returns the addresses that were sent to."""
    sent = []
    for user in due_users(users, now):
        message = build_digest(user, items_for(user))
        if message and mailer.send(message):
            sent.append(user.email)
    return sent
