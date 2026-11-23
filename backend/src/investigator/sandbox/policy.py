"""Security policy: which files never enter a workspace, and size limits for intake."""

from __future__ import annotations

from fnmatch import fnmatch

# Folders that are generated, huge, or private. They are never copied into a workspace.
SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", ".vs", ".idea", ".vscode",
    "node_modules", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox",
    "bin", "obj", "dist", "build", "target", "out", ".next", "coverage", ".gradle",
})

# Files that may hold credentials. They are never copied, so the LLM can never read them.
SENSITIVE_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "*.keystore", "*.jks",
    "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*", ".npmrc", ".pypirc", ".netrc",
    "credentials", "credentials.*", "secrets.*", "*.secret", "appsettings.*.local.json",
)
SAFE_EXCEPTIONS = ("*.example", "*.sample", "*.template")

MAX_FILE_BYTES = 2 * 1024 * 1024  # bigger files are skipped (logs, data dumps, binaries)


def is_sensitive(filename: str) -> bool:
    name = filename.lower()
    if any(fnmatch(name, p) for p in SAFE_EXCEPTIONS):
        return False
    return any(fnmatch(name, p) for p in SENSITIVE_PATTERNS)
