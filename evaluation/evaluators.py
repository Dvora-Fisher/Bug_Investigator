"""The six metrics, as LangSmith evaluators. Five are computed in code (free, deterministic);
only root-cause accuracy needs judgement, done by a cheap LLM with an explicit rubric.

A score of None means "not applicable" (e.g. reproduction for a language we cannot execute).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from investigator.budget import UsageLedger
from investigator.config import get_settings
from investigator.llm import LLMReasoner


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./").lower()


def _leaf(symbol: str) -> str:
    return symbol.rsplit(".", 1)[-1].rsplit("::", 1)[-1].lower()


def file_localization(outputs: dict, reference_outputs: dict) -> dict:
    """Share of the buggy files the agent pointed at (in its fix, or in its leading hypothesis)."""
    expected = reference_outputs["file"]
    expected = {_norm(f) for f in (expected if isinstance(expected, list) else [expected])}
    found = {_norm(f) for f in outputs.get("files", [])} | {_norm(outputs.get("leading_file", ""))}
    return {"key": "file_localization", "score": len(expected & found) / len(expected)}


def function_localization(outputs: dict, reference_outputs: dict) -> dict:
    """Did the agent name the right function? (N/A when the bug is not inside a function, e.g. a manifest.)"""
    symbol = _leaf(reference_outputs.get("symbol") or "")
    if not symbol:
        return {"key": "function_localization", "score": None}
    named = _leaf(outputs.get("leading_symbol", "")) == symbol
    in_fix = symbol in (outputs.get("fix_diff") or "").lower()
    return {"key": "function_localization", "score": float(named or in_fix)}


def bug_reproduced(outputs: dict, reference_outputs: dict) -> dict:
    if not reference_outputs["runnable"]:
        return {"key": "bug_reproduced", "score": None}
    return {"key": "bug_reproduced", "score": float(bool(outputs.get("reproduced")))}


def fix_success(outputs: dict, reference_outputs: dict) -> dict:
    """The fix passes the HIDDEN tests the agent never saw (the strictest check of a fix)."""
    if not reference_outputs["runnable"]:
        return {"key": "fix_success", "score": None}
    return {"key": "fix_success", "score": float(outputs.get("hidden_tests_passed") is True)}


def tests_pass_after_fix(outputs: dict, reference_outputs: dict) -> dict:
    """The agent's own verification (visible tests / its reproduction) passed after the fix."""
    if not reference_outputs["runnable"]:
        return {"key": "tests_pass_after_fix", "score": None}
    return {"key": "tests_pass_after_fix", "score": float(outputs.get("verified") is True)}


def unsupported_claim_rate(outputs: dict) -> dict:
    """Share of the agent's claims that are not backed by relevant evidence (lower is better)."""
    claims = outputs.get("claims", [])
    unsupported = [c for c in claims if not c["supported"]]
    return {"key": "unsupported_claim_rate", "score": len(unsupported) / len(claims) if claims else 0.0,
            "comment": "; ".join(f"{c['claim'][:80]} -> {c['reason']}" for c in unsupported)[:1000]}


def cost_usd(outputs: dict) -> dict:
    return {"key": "cost_usd", "score": round(outputs.get("cost_usd", 0.0), 5)}


# ----------------------------------------------------------------------------- LLM judge


class Grade(BaseModel):
    score: Literal[0.0, 0.5, 1.0]
    reason: str


JUDGE_PROMPT = """You grade the root-cause statement of an automated bug investigation against a reference.
Score 1.0: it identifies the same mechanism at the same place (wording may differ).
Score 0.5: the place is right but the mechanism is vague, incomplete or partly wrong.
Score 0.0: wrong place or wrong mechanism, or no root cause given.
Judge only the root cause, not the quality of the writing."""


def root_cause_accuracy(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    settings = get_settings()
    judge = LLMReasoner(settings, UsageLedger(settings.usage_db, settings), thread_id="eval-judge")
    grade = judge.structured(
        "judge_root_cause", JUDGE_PROMPT,
        f"Bug report:\n{inputs['description']}\n\nReference root cause:\n{reference_outputs['root_cause']}\n\n"
        f"Agent's root cause:\n{outputs.get('root_cause') or '(none)'}",
        Grade,
    )
    return {"key": "root_cause_accuracy", "score": grade.score, "comment": grade.reason}


EVALUATORS = [file_localization, function_localization, root_cause_accuracy, bug_reproduced,
              fix_success, tests_pass_after_fix, unsupported_claim_rate, cost_usd]
