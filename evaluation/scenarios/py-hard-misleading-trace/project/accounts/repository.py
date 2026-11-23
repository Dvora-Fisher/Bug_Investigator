"""In-memory user store (production wraps the same interface around Postgres)."""

import copy


def clean(record: dict) -> dict:
    """Drop fields that were never set, so we don't store explicit NULLs."""
    return {k: v for k, v in record.items() if v}


class UserRepository:
    def __init__(self):
        self._rows: dict[int, dict] = {}
        self._next_id = 1

    def add(self, record: dict) -> int:
        uid = self._next_id
        self._next_id += 1
        self._rows[uid] = clean({**record, "id": uid})
        return uid

    def update(self, uid: int, **changes) -> None:
        self._rows[uid] = clean({**self._rows[uid], **changes})

    def get(self, uid: int) -> dict:
        if uid not in self._rows:
            raise LookupError(f"user {uid} not found")
        return copy.deepcopy(self._rows[uid])

    def all(self) -> list[dict]:
        return [self.get(uid) for uid in sorted(self._rows)]
