"""What a runtime adapter is, and how much the system can do for a given project.

Adapters describe only *how to run* a project (image, install/test/build commands).
They never analyse code: understanding code is the LLM's job, for any language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


class Capability(IntEnum):
    """Levels of support, each including the ones below it.

    ANALYZE - the LLM can read and reason about the code (every language).
    EDIT    - we can propose and apply a patch (every text-based language).
    RUN     - we can build / run tests inside the sandbox (languages with an adapter).
    VERIFY  - RUN + we can confirm a fix by re-running tests (languages with an adapter).
    """

    ANALYZE = 1
    EDIT = 2
    RUN = 3
    VERIFY = 4


@dataclass(frozen=True)
class RuntimeAdapter:
    name: str
    languages: tuple[str, ...]
    markers: tuple[str, ...]  # glob patterns; any match means "this adapter applies"
    image: str
    install_cmd: tuple[str, ...]
    test_cmd: tuple[str, ...]
    build_cmd: tuple[str, ...] | None = None
    allowed_executables: frozenset[str] = field(default_factory=frozenset)

    def matches(self, root: Path) -> bool:
        return any(next(root.rglob(pattern), None) is not None for pattern in self.markers)
