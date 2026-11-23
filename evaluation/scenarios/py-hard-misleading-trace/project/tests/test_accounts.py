from accounts.api import get_user
from accounts.repository import UserRepository
from accounts.serializer import to_api
from accounts.service import AccountService


def test_serializer_uses_is_active():
    user = {"id": 1, "email": "dana@example.com", "nickname": "Dee", "is_active": True, "login_count": 3}
    assert to_api(user) == {"id": 1, "email": "dana@example.com", "name": "Dee", "is_active": True, "login_count": 3}


def test_get_active_user():
    service = AccountService(UserRepository())
    uid = service.register("Avi@Example.com")
    service.record_login(uid)
    assert get_user(service, uid) == (200, {"id": 1, "email": "avi@example.com", "name": "avi",
                                            "is_active": True, "login_count": 1})


def test_unknown_user_is_404():
    assert get_user(AccountService(UserRepository()), 42) == (404, {"error": "not found"})


def test_unset_fields_are_not_stored():
    repo = UserRepository()
    uid = repo.add({"email": "a@x.io", "nickname": None, "is_active": True})
    assert "nickname" not in repo.get(uid)
