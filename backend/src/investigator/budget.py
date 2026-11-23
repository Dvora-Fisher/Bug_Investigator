"""Usage ledger and budget guard.

Every LLM call is recorded here (tokens + estimated cost). Before each call we check two limits:
  * the monthly USD budget for the whole app, and
  * the token budget of the current investigation (thread).
When a limit is reached a BudgetExceeded error is raised; the graph catches it and stops gracefully.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings


class BudgetExceeded(RuntimeError):
    """Raised before an LLM call that would run over a configured budget."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def cost_usd(self, s: Settings) -> float:
        return (
            self.input_tokens * s.price_input_per_mtok
            + self.output_tokens * s.price_output_per_mtok
            + self.cache_read_tokens * s.price_cache_read_per_mtok
            + self.cache_write_tokens * s.price_cache_write_per_mtok
        ) / 1_000_000

    @classmethod
    def from_metadata(cls, meta: dict | None) -> Usage:
        """Build from LangChain's AIMessage.usage_metadata (input_tokens already includes cached tokens)."""
        if not meta:
            return cls()
        details = meta.get("input_token_details") or {}
        cache_read = int(details.get("cache_read") or 0)
        cache_write = int(details.get("cache_creation") or 0)
        return cls(
            input_tokens=max(int(meta.get("input_tokens", 0)) - cache_read - cache_write, 0),
            output_tokens=int(meta.get("output_tokens", 0)),
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )


class UsageLedger:
    """A tiny SQLite table of LLM calls. Thread-safe enough for a single-process app."""

    def __init__(self, db_path: Path, settings: Settings):
        self._settings = settings
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS usage (
                ts TEXT NOT NULL, thread_id TEXT NOT NULL, step TEXT NOT NULL,
                input_tokens INT, output_tokens INT, cache_read_tokens INT, cache_write_tokens INT,
                total_tokens INT, cost_usd REAL)"""
        )
        self._conn.commit()

    def record(self, thread_id: str, step: str, usage: Usage) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    datetime.now(UTC).isoformat(), thread_id, step,
                    usage.input_tokens, usage.output_tokens, usage.cache_read_tokens,
                    usage.cache_write_tokens, usage.total_tokens, usage.cost_usd(self._settings),
                ),
            )
            self._conn.commit()

    def _scalar(self, sql: str, *args: object) -> float:
        with self._lock:
            (value,) = self._conn.execute(sql, args).fetchone()
        return value or 0

    def month_spend_usd(self) -> float:
        month_prefix = datetime.now(UTC).strftime("%Y-%m")
        return self._scalar("SELECT SUM(cost_usd) FROM usage WHERE ts LIKE ?", f"{month_prefix}%")

    def thread_tokens(self, thread_id: str) -> int:
        return int(self._scalar("SELECT SUM(total_tokens) FROM usage WHERE thread_id = ?", thread_id))

    def thread_cost_usd(self, thread_id: str) -> float:
        return self._scalar("SELECT SUM(cost_usd) FROM usage WHERE thread_id = ?", thread_id)

    def ensure_within_budget(self, thread_id: str) -> None:
        spent = self.month_spend_usd()
        if spent >= self._settings.monthly_budget_usd:
            raise BudgetExceeded(
                f"Monthly budget reached (${spent:.2f} of ${self._settings.monthly_budget_usd:.2f})."
            )
        used = self.thread_tokens(thread_id)
        if used >= self._settings.investigation_token_budget:
            raise BudgetExceeded(
                f"Investigation token budget reached ({used:,} of "
                f"{self._settings.investigation_token_budget:,} tokens)."
            )
