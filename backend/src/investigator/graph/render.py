"""Small helpers that turn parts of the State into compact text for prompts (shared by all nodes)."""

from __future__ import annotations

from collections.abc import Iterable

from ..tools.evidence import truncate
from .state import Evidence, Hypothesis, InvestigationState


def bug_block(state: InvestigationState) -> str:
    bug = state["bug"]
    parts = [f"## Bug report\n{bug.description}"]
    if bug.error_output:
        parts.append(f"## Error output\n```\n{bug.error_output}\n```")
    if summary := state.get("bug_summary"):
        parts.append(f"## Bug summary\n{summary}")
    return "\n\n".join(parts)


def hypotheses_block(hypotheses: Iterable[Hypothesis]) -> str:
    lines = [
        f"- {h.id} [{h.status}, confidence {h.confidence:.1f}] {h.location.file}"
        f"{'::' + h.location.symbol if h.location.symbol else ''}: {h.statement}"
        for h in hypotheses
    ]
    return "\n".join(lines) or "(none)"


def evidence_block(items: Iterable[Evidence], max_chars: int = 6000) -> str:
    text = "\n\n".join(f"[{e.id}] {e.tool}({e.args})\n{e.excerpt}" for e in items)
    return truncate(text, max_chars) if text else "(no evidence)"


def cited_evidence(state: InvestigationState, hypothesis_id: str) -> list[Evidence]:
    """Evidence items that findings cited for a given hypothesis, in order, without duplicates."""
    by_id = {e.id: e for e in state.get("evidence", [])}
    ids = dict.fromkeys(
        eid for f in state.get("findings", []) if f.hypothesis_id == hypothesis_id for eid in f.evidence_ids
    )
    return [by_id[i] for i in ids if i in by_id]
