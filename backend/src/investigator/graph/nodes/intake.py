"""Steps 1-2: read the input and survey the project. No LLM calls here: these are plain facts,
cheap to compute in code, which the LLM receives in the next step."""

from __future__ import annotations

import re
from fnmatch import fnmatch

from ...runtimes.adapters import capability_for, detect_runtime
from ...tools.evidence import truncate
from ..context import Rt
from ..state import BugReport, InvestigationState, ProjectProfile

MAX_ERROR_CHARS = 3000
MAX_REFERENCED_FILES = 5

# Anything that looks like a file path with an extension, as it appears in stack traces of most languages.
_PATH_TOKEN = re.compile(r"[\w$@.\-/\\:]*[\w$@\-]+\.[A-Za-z][A-Za-z0-9]{0,5}\b")

MANIFEST_PATTERNS = (
    "package.json", "tsconfig.json", "pyproject.toml", "requirements*.txt", "setup.py", "*.csproj", "*.sln",
    "pom.xml", "build.gradle*", "go.mod", "Cargo.toml", "composer.json", "Gemfile", "Package.swift",
    "CMakeLists.txt", "Makefile",
)


def analyze_bug(state: InvestigationState, runtime: Rt) -> dict:
    """Normalise the bug report and find project files that the error output mentions."""
    bug = state["bug"]
    error = truncate(bug.error_output.strip(), MAX_ERROR_CHARS)
    project_files = list(runtime.context.workspace.iter_files())
    return {
        "bug": BugReport(description=bug.description.strip(), error_output=error),
        "referenced_files": find_referenced_files(f"{bug.description}\n{error}", project_files),
        "hypothesis_rounds": 0,
        "fix_attempts": 0,
    }


def inspect_project(state: InvestigationState, runtime: Rt) -> dict:
    ws = runtime.context.workspace
    files = list(ws.iter_files())
    adapter = detect_runtime(ws.project)
    return {"profile": ProjectProfile(
        tree=ws.tree(max_depth=3, max_entries=150),
        file_count=len(files),
        extensions=ws.extension_counts(),
        manifests=[f for f in files if any(fnmatch(f.rsplit("/", 1)[-1], p) for p in MANIFEST_PATTERNS)][:20],
        runtime=adapter.name if adapter else None,
        capability=capability_for(adapter, bool(adapter) and runtime.context.sandbox_ready(adapter.image)),
    )}


def find_referenced_files(text: str, project_files: list[str]) -> list[str]:
    """Match path-like tokens (e.g. /home/ci/app/src/calc.py:12) to real project files by their tail."""
    found: list[str] = []
    for token in _PATH_TOKEN.findall(text):
        candidate = token.replace("\\", "/").rstrip(":")
        for f in project_files:
            if f not in found and (candidate.endswith("/" + f) or candidate == f
                                   or (f.endswith("/" + candidate) and "/" in candidate)
                                   or f.rsplit("/", 1)[-1] == candidate):
                found.append(f)
        if len(found) >= MAX_REFERENCED_FILES:
            break
    return found[:MAX_REFERENCED_FILES]
