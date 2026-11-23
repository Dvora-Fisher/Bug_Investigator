"""JSON shape of a user in the public API (renamed in 1.4.0, see CHANGELOG)."""


def to_api(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("nickname") or user["email"].split("@")[0],
        "is_active": user["is_active"],
        "login_count": user.get("login_count", 0),
    }
