"""Run an investigation from the terminal.

    investigate --path ../evaluation/scenarios/py-off-by-one --bug "..." [--error-file err.txt]
    investigate --github https://github.com/owner/repo --bug "..."
    investigate --zip project.zip --bug "..."

When the graph pauses at human_review, the proposed diff is shown and you approve or reject it here.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import get_settings
from .graph.state import BugReport, ReviewDecision
from .sandbox.sources import GitHubSource, LocalSource, ProjectSource, ZipSource
from .service import InvestigationService


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to a legacy code page

    service = InvestigationService(get_settings())
    thread_id = service.create(_source(args))
    print(f"Investigation {thread_id} started ({args.mode or service.settings.investigation_mode} mode)\n")

    bug = BugReport(description=args.bug,
                    error_output=Path(args.error_file).read_text(encoding="utf-8") if args.error_file else "")
    events = service.start(thread_id, bug, args.mode)
    while True:
        for update in events:
            for node in update:
                if node != "__interrupt__":
                    print(f"  ✓ {node}")
        review = service.pending_review(thread_id)
        if review is None:
            break
        events = service.resume(thread_id, _ask_human(review))

    report = service.snapshot(thread_id).values["report"]
    print("\n" + report.model_dump_json(indent=2))
    print(f"\nCost of this investigation: ${service.cost_usd(thread_id):.4f}")
    return 0


def _source(args: argparse.Namespace) -> ProjectSource:
    if args.github:
        return GitHubSource(args.github, args.ref)
    if args.zip:
        return ZipSource(Path(args.zip))
    return LocalSource(Path(args.path))


def _ask_human(review: dict) -> ReviewDecision:
    print("\n" + "=" * 70)
    print(f"HUMAN REVIEW (attempt {review['attempt']}/{review['max_attempts']})")
    print(f"Root cause: {review['root_cause']}\nWhy this fix: {review['explanation']}")
    print(f"Evidence: {', '.join(review['evidence_ids']) or '(none cited)'}")
    if not review["verified_by_tests"]:
        print("NOTE: tests cannot be run for this project, so this fix will NOT be verified.")
    print("-" * 70 + "\n" + (review["diff"] or "(empty diff)") + "-" * 70)
    if input("Approve this fix? [y/n] ").strip().lower().startswith("y"):
        return ReviewDecision(decision="approve")
    feedback = input("What is wrong with it? ").strip()
    again = input("Revise the fix (f) or re-investigate (i)? [f/i] ").strip().lower()
    return ReviewDecision(decision="reject", feedback=feedback,
                          next_step="reinvestigate" if again.startswith("i") else "revise_fix")


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="investigate", description="Investigate a bug with an LLM agent.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--path", help="Local project folder")
    src.add_argument("--zip", help="Project ZIP file")
    src.add_argument("--github", help="Public GitHub repository URL")
    p.add_argument("--ref", help="Branch or tag (with --github)")
    p.add_argument("--bug", required=True, help="Description of the bug")
    p.add_argument("--error-file", help="File containing an error message / logs")
    p.add_argument("--mode", choices=["baseline", "improved"])
    return p.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
