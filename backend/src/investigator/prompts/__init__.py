"""Prompt files live next to this module as Markdown, separate from code.

system_prompt("collect_evidence", mode) = base.md + collect_evidence.md
                                          (+ collect_evidence.improved.md in "improved" mode)
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from ..config import InvestigationMode

_DIR = Path(__file__).parent


@cache
def _read(name: str) -> str:
    path = _DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def system_prompt(step: str, mode: InvestigationMode) -> str:
    parts = [_read("base"), _read(step)]
    if mode == "improved":
        parts.append(_read(f"{step}.improved"))
    return "\n\n".join(p for p in parts if p)
