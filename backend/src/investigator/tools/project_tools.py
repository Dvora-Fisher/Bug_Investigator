"""General, language-agnostic tools the LLM uses to explore a project.

None of these tools understands any programming language. They read, list and search text;
the LLM supplies the understanding. That is how one set of tools serves Python, C#, Go, Rust...
"""

from __future__ import annotations

import re
from fnmatch import fnmatch

from langchain_core.tools import BaseTool, tool

from ..sandbox.workspace import Workspace, WorkspaceError
from .evidence import EvidenceRecorder

MAX_READ_LINES = 200
MAX_MATCHES = 40

# Text patterns that look like a definition in most mainstream languages. This is a search
# heuristic to help the LLM navigate, not a parser; the LLM decides what the matches mean.
_DEFINITION_TEMPLATES = (
    r"\b(def|class|function|func|fn|interface|struct|enum|record|trait|impl|module|type|sub)\s+{s}\b",
    r"\b{s}\s*[:=]\s*(async\s+)?(function\b|\(|[A-Za-z_]\w*\s*=>)",
    r"^\s*(public|private|protected|internal|static|override|virtual|async|export|\s)*[\w<>\[\],.?]+\s+{s}\s*\(",
)


def build_read_tools(ws: Workspace, recorder: EvidenceRecorder) -> list[BaseTool]:
    """Read-only exploration tools. Every result is recorded as evidence."""

    @tool(parse_docstring=True)
    def list_tree(path: str = "", depth: int = 3) -> str:
        """Show the folder structure of the project or of a sub-folder.

        Args:
            path: Folder relative to the project root ("" for the root).
            depth: How many levels deep to show (1-5).
        """
        return recorder.observe("list_tree", {"path": path, "depth": depth},
                                ws.tree(path, max_depth=max(1, min(depth, 5))))

    @tool(parse_docstring=True)
    def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
        """Read part of a file with line numbers. Read only the lines you need.

        Args:
            path: File path relative to the project root.
            start_line: First line to show (1-based).
            end_line: Last line to show; 0 means start_line + 199.
        """
        lines = ws.read_text(path).splitlines()
        start = max(start_line, 1)
        end = min(end_line or start + MAX_READ_LINES - 1, start + MAX_READ_LINES - 1, len(lines))
        body = "\n".join(f"{n:>5} | {lines[n - 1]}" for n in range(start, end + 1))
        header = f"{path} (lines {start}-{end} of {len(lines)})"
        return recorder.observe("read_file", {"path": path, "start_line": start, "end_line": end},
                                f"{header}\n{body}")

    @tool(parse_docstring=True)
    def search_code(pattern: str, file_glob: str = "*", is_regex: bool = False) -> str:
        """Search all project files for a string or regular expression.

        Args:
            pattern: Text (or regex when is_regex is true) to look for.
            file_glob: Only search files whose path matches this glob, e.g. "*.py" or "src/*".
            is_regex: Treat pattern as a regular expression.
        """
        regex = re.compile(pattern if is_regex else re.escape(pattern), re.IGNORECASE)
        return recorder.observe("search_code", {"pattern": pattern, "file_glob": file_glob},
                                _search(ws, regex, file_glob))

    @tool(parse_docstring=True)
    def find_definitions(symbol: str) -> str:
        """Find where a function, method, class or variable is defined (any language).

        Args:
            symbol: The exact name to look for.
        """
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", symbol):
            raise WorkspaceError("symbol must be a plain identifier")
        s = re.escape(symbol)
        regex = re.compile("|".join(t.format(s=s) for t in _DEFINITION_TEMPLATES), re.MULTILINE)
        return recorder.observe("find_definitions", {"symbol": symbol}, _search(ws, regex, "*"))

    return [list_tree, read_file, search_code, find_definitions]


def _search(ws: Workspace, regex: re.Pattern[str], file_glob: str) -> str:
    matches: list[str] = []
    for rel in ws.iter_files():
        if not (fnmatch(rel, file_glob) or fnmatch(rel.rsplit("/", 1)[-1], file_glob)):
            continue
        try:
            text = ws.read_text(rel)
        except WorkspaceError:
            continue  # binary file
        for n, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{rel}:{n}: {line.strip()[:200]}")
                if len(matches) >= MAX_MATCHES:
                    return "\n".join(matches) + f"\n... (stopped after {MAX_MATCHES} matches)"
    return "\n".join(matches) or "No matches."
