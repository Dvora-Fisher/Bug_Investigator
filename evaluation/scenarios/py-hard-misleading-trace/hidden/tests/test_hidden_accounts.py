from accounts.api import get_user
from accounts.repository import UserRepository, clean
from accounts.service import AccountService


def test_deactivated_user_profile():
    service = AccountService(UserRepository())
    uid = service.register("noa@example.com")
    service.deactivate(uid)
    assert get_user(service, uid) == (200, {"id": 1, "email": "noa@example.com", "name": "noa",
                                            "is_active": False, "login_count": 0})


def test_repository_keeps_false_values():
    repo = UserRepository()
    uid = repo.add({"email": "a@x.io", "is_active": False})
    assert repo.get(uid)["is_active"] is False


def test_clean_drops_only_none():
    assert clean({"a": 0, "b": False, "c": "", "d": None}) == {"a": 0, "b": False, "c": ""}
