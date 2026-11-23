"""A workspace is a private copy of the user's project for one investigation.

    data/workspaces/<thread_id>/original/   pristine copy (never modified)
    data/workspaces/<thread_id>/project/    working copy (fixes are applied here)

The user's real project is never touched. Every path the LLM asks for goes through resolve(),
which refuses anything outside the working copy ("path jail").
"""

from __future__ import annotations

import difflib
import os
import shutil
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

from ..graph.state import FileEdit
from .policy import MAX_FILE_BYTES, SKIP_DIRS, is_sensitive


class WorkspaceError(ValueError):
    """A request the workspace refuses (bad path, too large, invalid edit...)."""


class Workspace:
    def __init__(self, root: Path):
        self.root = root
        self.project = root / "project"
        self.original = root / "original"

    # ------------------------------------------------------------------ lifecycle

    @classmethod
    def create(cls, base_dir: Path, thread_id: str, source_dir: Path, *,
               max_files: int, max_bytes: int) -> Workspace:
        ws = cls(base_dir / thread_id)
        if ws.root.exists():
            raise WorkspaceError(f"Workspace {thread_id} already exists")
        copy_filtered(source_dir, ws.project, max_files=max_files, max_bytes=max_bytes)
        shutil.copytree(ws.project, ws.original)
        return ws

    @classmethod
    def open(cls, base_dir: Path, thread_id: str) -> Workspace:
        ws = cls(base_dir / thread_id)
        if not ws.project.is_dir():
            raise WorkspaceError(f"No workspace for {thread_id}")
        return ws

    # ------------------------------------------------------------------ reading

    def resolve(self, rel_path: str) -> Path:
        """Map a project-relative path to a real path, refusing escapes ('..', absolute paths, symlinks)."""
        candidate = (self.project / rel_path.strip().lstrip("/\\")).resolve()
        if not candidate.is_relative_to(self.project.resolve()):
            raise WorkspaceError(f"Path is outside the project: {rel_path}")
        return candidate

    def read_text(self, rel_path: str) -> str:
        path = self.resolve(rel_path)
        if not path.is_file():
            raise WorkspaceError(f"Not a file: {rel_path}")
        data = path.read_bytes()
        if b"\x00" in data[:8192]:
            raise WorkspaceError(f"Binary file: {rel_path}")
        return data.decode("utf-8", errors="replace")

    def iter_files(self, base: Path | None = None) -> Iterator[str]:
        """All project files as sorted posix paths relative to the project root."""
        base = base or self.project
        for path in sorted(base.rglob("*")):
            if path.is_file():
                yield path.relative_to(base).as_posix()

    def extension_counts(self) -> dict[str, int]:
        return dict(Counter(Path(f).suffix.lower() or Path(f).name for f in self.iter_files()).most_common(15))

    def tree(self, sub_path: str = "", max_depth: int = 3, max_entries: int = 200) -> str:
        start = self.resolve(sub_path) if sub_path else self.project
        lines: list[str] = []
        for path in sorted(start.rglob("*")):
            rel = path.relative_to(start)
            if len(rel.parts) > max_depth:
                continue
            if len(lines) >= max_entries:
                lines.append("... (truncated)")
                break
            lines.append("  " * (len(rel.parts) - 1) + rel.name + ("/" if path.is_dir() else ""))
        return "\n".join(lines) or "(empty)"

    # ------------------------------------------------------------------ editing

    def preview(self, edits: Iterable[FileEdit]) -> dict[str, str]:
        """Apply edits in memory and return {path: new_text}. Raises WorkspaceError if any edit is invalid."""
        new_texts: dict[str, str] = {}
        for edit in edits:
            text = new_texts[edit.path] if edit.path in new_texts else self.read_text(edit.path)
            count = text.count(edit.old) if edit.old else 0
            if count != 1:
                raise WorkspaceError(
                    f"{edit.path}: 'old' text must appear exactly once, found {count} times. "
                    "Copy it exactly from the file, including indentation."
                )
            new_texts[edit.path] = text.replace(edit.old, edit.new, 1)
        return new_texts

    def diff_for(self, edits: Iterable[FileEdit]) -> str:
        return "".join(_unified(path, self.read_text(path), new) for path, new in self.preview(edits).items())

    def apply(self, edits: list[FileEdit]) -> str:
        """Validate every edit first, then write. Returns the resulting diff against the original."""
        for path, text in self.preview(edits).items():
            self.resolve(path).write_text(text, encoding="utf-8", newline="")
        return self.diff()

    def changed_files(self) -> list[str]:
        return [f for f in self.iter_files(self.original)
                if (self.original / f).read_bytes() != _read_or_none(self.project / f)]

    def diff(self) -> str:
        return "".join(
            _unified(f, (self.original / f).read_text("utf-8", errors="replace"),
                     (self.project / f).read_text("utf-8", errors="replace") if (self.project / f).exists() else "")
            for f in self.changed_files()
        )

    def reset(self) -> None:
        """Undo every change to original files (used before trying a different fix)."""
        for f in self.changed_files():
            target = self.project / f
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.original / f, target)


# ---------------------------------------------------------------------- helpers


def _read_or_none(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _unified(path: str, old: str, new: str) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{path}", f"b/{path}"))


def copy_filtered(src: Path, dest: Path, *, max_files: int, max_bytes: int) -> None:
    """Copy a project, skipping generated folders, sensitive files, symlinks and oversized files."""
    total_files = total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))]
        rel_dir = Path(dirpath).relative_to(src)
        for name in filenames:
            source = Path(dirpath) / name
            if source.is_symlink() or is_sensitive(name):
                continue
            size = source.stat().st_size
            if size > MAX_FILE_BYTES:
                continue
            total_files += 1
            total_bytes += size
            if total_files > max_files or total_bytes > max_bytes:
                shutil.rmtree(dest, ignore_errors=True)
                raise WorkspaceError(f"Project is too large (limit: {max_files} files / {max_bytes // 2**20} MB)")
            target = dest / rel_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    if total_files == 0:
        raise WorkspaceError("The project contains no readable files")
