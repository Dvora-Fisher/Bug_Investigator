from .repository import UserRepository


class AccountService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register(self, email: str, nickname: str | None = None) -> int:
        return self.repo.add({"email": email.strip().lower(), "nickname": nickname, "is_active": True})

    def record_login(self, uid: int) -> None:
        user = self.repo.get(uid)
        self.repo.update(uid, login_count=user.get("login_count", 0) + 1)

    def deactivate(self, uid: int) -> None:
        self.repo.update(uid, is_active=False)
