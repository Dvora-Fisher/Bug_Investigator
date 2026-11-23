"""The supported runtimes, as plain data, plus detection.

To support a new language at the RUN/VERIFY level, add one RuntimeAdapter here and one
Docker image under sandbox-images/. The investigation graph does not change.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Settings
from .base import Capability, RuntimeAdapter

PYTHON = RuntimeAdapter(
    name="python",
    languages=("Python",),
    markers=("pyproject.toml", "requirements*.txt", "setup.py", "pytest.ini", "test_*.py"),
    image="bug-investigator/python:latest",
    install_cmd=("sh", "-c", "if [ -f requirements.txt ]; then pip install -q -r requirements.txt; fi; "
                 "if [ -f pyproject.toml ]; then pip install -q -e . || true; fi"),
    test_cmd=("python", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"),
    allowed_executables=frozenset({"python", "pytest"}),
)

DOTNET = RuntimeAdapter(
    name="dotnet",
    languages=("C#",),
    markers=("*.csproj", "*.sln"),
    image="bug-investigator/dotnet:latest",
    install_cmd=("dotnet", "restore"),
    test_cmd=("dotnet", "test", "--no-restore", "--nologo"),
    build_cmd=("dotnet", "build", "--no-restore", "--nologo"),
    allowed_executables=frozenset({"dotnet"}),
)

NODE = RuntimeAdapter(
    name="node",
    languages=("JavaScript", "TypeScript"),
    markers=("package.json",),
    image="bug-investigator/node:latest",
    install_cmd=("sh", "-c", "if [ -f package-lock.json ]; then npm ci --ignore-scripts; "
                 "else npm install --ignore-scripts; fi"),
    test_cmd=("npm", "test", "--silent"),
    build_cmd=("npm", "run", "build", "--if-present"),
    allowed_executables=frozenset({"node", "npm", "npx"}),
)

ADAPTERS: tuple[RuntimeAdapter, ...] = (DOTNET, NODE, PYTHON)  # most specific markers first


def detect_runtime(root: Path) -> RuntimeAdapter | None:
    return next((a for a in ADAPTERS if a.matches(root)), None)


def get_adapter(name: str | None) -> RuntimeAdapter | None:
    return next((a for a in ADAPTERS if a.name == name), None)


def capability_for(adapter: RuntimeAdapter | None, settings: Settings) -> Capability:
    """Honest support level: running and verifying require both an adapter and an enabled sandbox."""
    if adapter is None or not settings.execution_enabled:
        return Capability.EDIT
    return Capability.VERIFY
