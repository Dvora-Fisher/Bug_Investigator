import zipfile
from pathlib import Path

import pytest

from investigator.sandbox.sources import GitHubSource, ZipSource, create_workspace
from investigator.sandbox.workspace import WorkspaceError


def _zip(path: Path, entries: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return path


def test_zip_with_single_top_folder_is_unwrapped(tmp_path, settings):
    archive = _zip(tmp_path / "p.zip", {"repo-main/app.py": "print(1)", "repo-main/.env": "SECRET=1"})
    ws = create_workspace(ZipSource(archive), "z1", settings)
    assert list(ws.iter_files()) == ["app.py"]  # unwrapped, and .env filtered out


@pytest.mark.parametrize("evil", ["../evil.py", "a/../../evil.py", "/abs/evil.py", "C:/evil.py"])
def test_zip_slip_is_refused(tmp_path, settings, evil):
    archive = _zip(tmp_path / "evil.zip", {"ok.py": "x", evil: "boom"})
    with pytest.raises(WorkspaceError, match="Unsafe path"):
        create_workspace(ZipSource(archive), "z2", settings)


def test_zip_bomb_limit(tmp_path, settings):
    settings.max_project_mb = 1
    archive = _zip(tmp_path / "big.zip", {"big.txt": "0" * (2 * 2**20)})
    with pytest.raises(WorkspaceError, match="too large"):
        create_workspace(ZipSource(archive), "z3", settings)


def test_not_a_zip(tmp_path, settings):
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip")
    with pytest.raises(WorkspaceError, match="not a valid ZIP"):
        create_workspace(ZipSource(bad), "z4", settings)


@pytest.mark.parametrize("url", [
    "https://github.com/owner/repo", "https://github.com/owner/repo.git", "https://github.com/o-1/r.x/",
])
def test_github_urls_accepted(url):
    GitHubSource(url)


@pytest.mark.parametrize("url", [
    "http://github.com/o/r", "https://gitlab.com/o/r", "https://github.com/o", "file:///etc/passwd",
    "https://github.com/o/r/../../x", "git@github.com:o/r.git", "https://github.com/o/r --upload-pack=x",
])
def test_github_urls_rejected(url):
    with pytest.raises(WorkspaceError):
        GitHubSource(url)


def test_github_ref_cannot_look_like_an_option():
    with pytest.raises(WorkspaceError):
        GitHubSource("https://github.com/o/r", ref="--upload-pack=evil")
    GitHubSource("https://github.com/o/r", ref="release/1.2")
