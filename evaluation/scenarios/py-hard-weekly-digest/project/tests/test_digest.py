from digest.builder import build_digest
from digest.mailer import Mailer, TransientError
from digest.preferences import Preferences, from_settings, parse_day
from digest.scheduler import wants_digest
from digest.users import User


def test_parse_day_uses_iso_numbers():
    assert parse_day("Monday") == 1
    assert parse_day(" sunday ") == 7


def test_from_settings():
    prefs = from_settings({"digest": "on", "day": "friday", "muted": "sports, ads"})
    assert prefs.digest_day == 5 and prefs.muted_topics == {"sports", "ads"}


def test_build_digest_skips_muted_and_empty():
    user = User(1, "dana@example.com", Preferences(muted_topics={"ads"}))
    assert build_digest(user, [{"topic": "ads", "title": "Sale"}]) is None
    msg = build_digest(user, [{"topic": "news", "title": "Release 2.0"}, {"topic": "ads", "title": "Sale"}])
    assert msg["subject"] == "Your weekly digest (1 updates)" and msg["body"] == "- Release 2.0"


def test_wants_digest():
    assert wants_digest(User(1, "a@x.io"))
    assert not wants_digest(User(2, "b@x.io", unsubscribed=True))
    assert not wants_digest(User(3, "c@x.io", Preferences(digest_enabled=False)))


def test_mailer_retries_transient_errors():
    calls = []

    def flaky(message):
        calls.append(message)
        if len(calls) < 2:
            raise TransientError()

    assert Mailer(flaky).send({"to": "a@x.io"}) is True
    assert len(calls) == 2
