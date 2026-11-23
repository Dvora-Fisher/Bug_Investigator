"""Compare two saved experiments and write a Markdown table (for the README).

    python evaluation/compare_results.py results/baseline-xxxx.json results/improved-xxxx.json
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


def main(base_path: str, improved_path: str) -> None:
    base, improved = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (base_path, improved_path))
    lines = ["| Metric | Baseline | Improved | Change |", "|---|---|---|---|"]
    for key, label in LABELS.items():
        b, i = base["summary"].get(key), improved["summary"].get(key)
        if b is None or i is None:
            delta = ""
        else:
            better = (i < b) if key in LOWER_IS_BETTER else (i > b)
            delta = "=" if i == b else ("better" if better else "worse")
        lines.append(f"| {label} | {fmt(b, key)} | {fmt(i, key)} | {delta} |")
    lines.append(f"| Scenarios | {base['scenarios']} | {improved['scenarios']} | |")
    lines.append(f"| Total spend (USD) | ${base['total_spend_usd']:.4f} | ${improved['total_spend_usd']:.4f} | |")
    table = "\n".join(lines)
    header = f"Experiments: `{base['experiment']}` vs `{improved['experiment']}`\n\n"
    out = Path(improved_path).with_name("comparison.md")
    out.write_text(header + table + "\n", encoding="utf-8")
    print(header + table)


if __name__ == "__main__":
    main(*sys.argv[1:3])
