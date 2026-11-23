"""Turns every tool result into a numbered piece of evidence.

The model sees each result prefixed with its id (e.g. "[E7]") and must cite those ids in its
conclusions. Because evidence is created by our code from real tool output, the model can cite
evidence but never fabricate it. This is what lets the final report separate facts from guesses.
"""

from __future__ import annotations

from ..graph.state import Evidence


class EvidenceRecorder:
    def __init__(self, start_index: int, max_chars: int):
        self._next = start_index + 1
        self._max_chars = max_chars
        self.items: list[Evidence] = []

    def observe(self, tool: str, args: dict, output: str) -> str:
        text = truncate(output, self._max_chars)
        evidence = Evidence(id=f"E{self._next}", tool=tool, args=args, excerpt=text)
        self._next += 1
        self.items.append(evidence)
        return f"[{evidence.id}]\n{text}"


def truncate(text: str, max_chars: int) -> str:
    """Keep the head and the tail: errors and summaries usually sit at the end of long outputs."""
    if len(text) <= max_chars:
        return text
    head = max_chars // 3
    tail = max_chars - head
    return f"{text[:head]}\n... [{len(text) - max_chars} chars omitted] ...\n{text[-tail:]}"
