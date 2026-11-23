"""What a runtime adapter is, and how much the system can do for a given project.

Adapters describe only *how to run* a project (image, install/test commands, environment).
They never analyse code: understanding code is the LLM's job, for any language.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

SANDBOX_TAG = "2"  # bump when sandbox-images/Dockerfile changes, to force a rebuild
CACHE_MOUNT = "/cache"  # where the shared package cache volume is mounted inside a container


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
    manifests: tuple[str, ...]  # dependency files; when they change, dependencies are reinstalled
    base_image: str
    install_cmd: tuple[str, ...]  # fixed command, runs WITH network (downloads dependencies)
    test_cmd: tuple[str, ...]  # runs WITHOUT network
    test_filter_args: tuple[str, ...] = ()  # e.g. ("-k",): how to run a subset of tests
    image_setup: str = "true"  # extra shell step while building the image
    env: Mapping[str, str] = field(default_factory=dict)
    # Environment that points the package manager at the shared cache (used when the cache is enabled).
    cache_env: Mapping[str, str] = field(default_factory=dict)
    allowed_executables: frozenset[str] = field(default_factory=frozenset)

    @property
    def image(self) -> str:
        return f"bug-investigator/{self.name}:{SANDBOX_TAG}"

    @property
    def cache_volume(self) -> str:
        return f"bug-investigator-cache-{self.name}"

    def matches(self, root: Path) -> bool:
        return any(next(root.rglob(pattern), None) is not None for pattern in self.markers)

    def test_command(self, test_filter: str = "") -> tuple[str, ...]:
        return (*self.test_cmd, *self.test_filter_args, test_filter) if test_filter else self.test_cmd
