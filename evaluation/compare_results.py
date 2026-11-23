"""Compare two saved experiments and write a Markdown table (for the README).

    python evaluation/compare_results.py A.json B.json [out.md] [label A] [label B]
    e.g. python evaluation/compare_results.py results/baseline-x.json results/improved-y.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LOWER_IS_BETTER = {"unsupported_claim_rate", "cost_usd"}
LABELS = {
    "file_localization": "File localization",
    "function_localization": "Function localization",
    "root_cause_accuracy": "Root-cause accuracy (LLM judge)",
    "bug_reproduced": "Bug reproduced (runnable scenarios)",
    "tests_pass_after_fix": "Agent's own tests pass after fix",
    "fix_success": "Fix passes hidden tests",
    "unsupported_claim_rate": "Unsupported claim rate",
    "cost_usd": "Cost per investigation (USD)",
}


def fmt(value: float | None, key: str) -> str:
    if value is None:
        return "n/a"
    return f"${value:.4f}" if key == "cost_usd" else f"{value:.0%}"


def table(a: dict, b: dict, label_a: str, label_b: str) -> str:
    lines = [f"| Metric | {label_a} | {label_b} | Change |", "|---|---|---|---|"]
    for key, label in LABELS.items():
        x, y = a["summary"].get(key), b["summary"].get(key)
        if x is None or y is None:
            delta = ""
        else:
            better = (y < x) if key in LOWER_IS_BETTER else (y > x)
            delta = "=" if y == x else ("better" if better else "worse")
        lines.append(f"| {label} | {fmt(x, key)} | {fmt(y, key)} | {delta} |")
    lines.append(f"| Scenarios | {a['scenarios']} | {b['scenarios']} | |")
    lines.append(f"| Total spend (USD) | ${a['total_spend_usd']:.4f} | ${b['total_spend_usd']:.4f} | |")
    return "\n".join(lines)


def main(path_a: str, path_b: str, out: str = "comparison.md", label_a: str = "", label_b: str = "") -> None:
    a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (path_a, path_b))
    text = (f"Experiments: `{a['experiment']}` vs `{b['experiment']}`\n\n"
            f"{table(a, b, label_a or a['mode'].title(), label_b or b['mode'].title())}\n")
    target = Path(path_b).with_name(out)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main(*sys.argv[1:6])
