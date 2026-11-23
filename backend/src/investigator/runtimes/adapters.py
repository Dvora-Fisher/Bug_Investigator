"""The supported runtimes, as plain data, plus detection.

To support a new language at the RUN/VERIFY level, add one RuntimeAdapter here (base image +
commands) and rebuild the images. The investigation graph does not change.

Everything a run produces (dependencies, caches, build output) lives under /workspace, which is the
investigation's own copy of the project, so containers stay disposable and the image read-only.
"""

from __future__ import annotations

from pathlib import Path

from .base import Capability, RuntimeAdapter

WORK = "/workspace/.investigator"  # our private folder inside the project copy (hidden from the LLM's tools)

PYTHON = RuntimeAdapter(
    name="python",
    languages=("Python",),
    markers=("pyproject.toml", "requirements*.txt", "setup.py", "pytest.ini", "test_*.py"),
    base_image="python:3.12-slim",
    image_setup="pip install --no-cache-dir pytest",
    # Only requirements.txt is installed, and only as pre-built wheels: building a package from
    # source would execute its setup code while the network is open.
    install_cmd=("sh", "-c", f"if [ -f requirements.txt ]; then pip install --no-cache-dir --only-binary=:all: "
                             f"--target {WORK}/deps -r requirements.txt; fi"),
    test_cmd=("python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--ignore=.investigator"),
    test_filter_args=("-k",),
    env={"PYTHONPATH": f"/workspace:/workspace/src:{WORK}/deps"},
    allowed_executables=frozenset({"python", "pytest"}),
)

DOTNET = RuntimeAdapter(
    name="dotnet",
    languages=("C#",),
    markers=("*.csproj", "*.sln", "*.slnx"),
    base_image="mcr.microsoft.com/dotnet/sdk:10.0",
    install_cmd=("dotnet", "restore"),
    test_cmd=("dotnet", "test", "--no-restore", "--nologo"),  # default verbosity keeps assertion messages
    test_filter_args=("--filter",),
    # No background build servers: every container must exit as soon as its command ends.
    env={"NUGET_PACKAGES": f"{WORK}/nuget", "MSBUILDDISABLENODEREUSE": "1", "DOTNET_CLI_USE_MSBUILD_SERVER": "0"},
    allowed_executables=frozenset({"dotnet"}),
)

NODE = RuntimeAdapter(
    name="node",
    languages=("JavaScript", "TypeScript"),
    markers=("package.json",),
    base_image="node:22-slim",
    # --ignore-scripts: package install scripts never run.
    install_cmd=("sh", "-c", "if [ -f package-lock.json ]; then npm ci --ignore-scripts --no-audit --no-fund; "
                             "else npm install --ignore-scripts --no-audit --no-fund; fi"),
    test_cmd=("npm", "test", "--silent"),
    test_filter_args=("--", "-t"),
    env={"npm_config_cache": "/tmp/.npm"},
    allowed_executables=frozenset({"node", "npm", "npx"}),
)

ADAPTERS: tuple[RuntimeAdapter, ...] = (DOTNET, NODE, PYTHON)  # most specific markers first


def detect_runtime(root: Path) -> RuntimeAdapter | None:
    return next((a for a in ADAPTERS if a.matches(root)), None)


def get_adapter(name: str | None) -> RuntimeAdapter | None:
    return next((a for a in ADAPTERS if a.name == name), None)


def capability_for(adapter: RuntimeAdapter | None, sandbox_ready: bool) -> Capability:
    """Honest support level: running and verifying need an adapter AND a working sandbox image."""
    return Capability.VERIFY if adapter is not None and sandbox_ready else Capability.EDIT
