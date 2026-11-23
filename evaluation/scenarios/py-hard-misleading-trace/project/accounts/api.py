from .serializer import to_api
from .service import AccountService


def get_user(service: AccountService, uid: int) -> tuple[int, dict]:
    try:
        return 200, to_api(service.repo.get(uid))
    except LookupError:
        return 404, {"error": "not found"}
