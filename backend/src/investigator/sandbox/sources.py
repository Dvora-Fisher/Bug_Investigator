"""Where a project comes from: a local folder, an uploaded ZIP, or a public GitHub repository.

Each source only knows how to put the project files into a directory. Copying into a workspace,
filtering sensitive files and enforcing size limits happen in one shared place (Workspace.create).
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from ..config import Settings
from .workspace import Workspace, WorkspaceError

GITHUB_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
GIT_REF = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./-]{0,99}$")  # no leading '-' (would look like a git option)


class ProjectSource(Protocol):
    def fetch(self, scratch_dir: Path, settings: Settings) -> Path:
        """Return a directory containing the project. May use scratch_dir for temporary files."""
        ...

    def describe(self) -> str: ...


@dataclass(frozen=True)
class LocalSource:
    path: Path

    def fetch(self, scratch_dir: Path, settings: Settings) -> Path:
        if not self.path.is_dir():
            raise WorkspaceError(f"Folder not found: {self.path}")
        return self.path

    def describe(self) -> str:
        return f"local folder {self.path.name}"


@dataclass(frozen=True)
class ZipSource:
    zip_path: Path

    def fetch(self, scratch_dir: Path, settings: Settings) -> Path:
        dest = scratch_dir / "unzipped"
        max_bytes = settings.max_project_mb * 2**20
        try:
            with zipfile.ZipFile(self.zip_path) as archive:
                members = [m for m in archive.infolist() if not m.is_dir() and not _is_zip_symlink(m)]
                if len(members) > settings.max_files or sum(m.file_size for m in members) > max_bytes:
                    raise WorkspaceError("ZIP is too large")  # also protects against "zip bombs"
                for member in members:
                    _extract_safely(archive, member, dest)
        except zipfile.BadZipFile as exc:
            raise WorkspaceError("The uploaded file is not a valid ZIP archive") from exc
        return _single_top_folder(dest)

    def describe(self) -> str:
        return f"ZIP upload {self.zip_path.name}"


@dataclass(frozen=True)
class GitHubSource:
    url: str
    ref: str | None = None  # branch or tag

    def __post_init__(self) -> None:
        if not GITHUB_URL.match(self.url):
            raise WorkspaceError("Only public repository URLs like https://github.com/owner/repo are supported")
        if self.ref is not None and not GIT_REF.match(self.ref):
            raise WorkspaceError(f"Invalid branch or tag name: {self.ref}")

    def fetch(self, scratch_dir: Path, settings: Settings) -> Path:
        dest = scratch_dir / "clone"
        cmd = [
            "git", "-c", "core.symlinks=false", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
            "clone", "--depth", "1", "--no-tags", "--single-branch",
            *(["--branch", self.ref] if self.ref else []),
            "--", self.url, str(dest),
        ]
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, text=True,
                           timeout=settings.git_clone_timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceError("Cloning took too long; the repository may be too large") from exc
        except subprocess.CalledProcessError as exc:
            raise WorkspaceError(
                f"Could not clone {self.url}. Is it public and does the branch exist? "
                f"({exc.stderr.strip().splitlines()[-1] if exc.stderr.strip() else 'git error'})"
            ) from exc
        return dest

    def describe(self) -> str:
        return f"GitHub {self.url}" + (f" @ {self.ref}" if self.ref else "")


def create_workspace(source: ProjectSource, thread_id: str, settings: Settings) -> Workspace:
    """The one entry point for intake: fetch from any source, then copy into a filtered workspace."""
    settings.workspaces_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.data_dir, ignore_cleanup_errors=True) as scratch:
        project_dir = source.fetch(Path(scratch), settings)
        return Workspace.create(settings.workspaces_dir, thread_id, project_dir,
                                max_files=settings.max_files, max_bytes=settings.max_project_mb * 2**20)


# ---------------------------------------------------------------------- zip helpers


def _is_zip_symlink(member: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(member.external_attr >> 16)


def _extract_safely(archive: zipfile.ZipFile, member: zipfile.ZipInfo, dest: Path) -> None:
    """Refuse 'zip slip': entries like ../../evil or C:\\evil that would land outside dest."""
    name = PurePosixPath(member.filename.replace("\\", "/"))
    if name.is_absolute() or ".." in name.parts or ":" in member.filename:
        raise WorkspaceError(f"Unsafe path inside ZIP: {member.filename}")
    target = dest.joinpath(*name.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as src, open(target, "wb") as out:
        out.write(src.read())


def _single_top_folder(path: Path) -> Path:
    """ZIPs downloaded from GitHub wrap everything in one folder; step into it."""
    entries = list(path.iterdir()) if path.exists() else []
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else path
