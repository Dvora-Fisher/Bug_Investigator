"""The single gateway between the graph and the language model.

Nodes never talk to the model directly; they ask a Reasoner for one of two things:
  * structured(...)  - one call that returns a validated Pydantic object, or
  * tool_loop(...)   - a bounded loop where the model calls tools, then submits a validated object.

Every call passes through _invoke(), which enforces the budget and records token usage.
Tests swap in a scripted Reasoner, so the graph can be tested without spending money.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Protocol, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from .budget import UsageLedger, Usage
from .config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Validator = Callable[[T], str | None]  # returns an error message, or None when the result is acceptable


class ReasoningFailed(RuntimeError):
    """The model did not produce a valid result within the allowed number of steps."""


class Reasoner(Protocol):
    def structured(self, step: str, system: str, user: str, schema: type[T]) -> T: ...

    def tool_loop(
        self,
        step: str,
        system: str,
        user: str,
        tools: Sequence[BaseTool],
        submit_schema: type[T],
        max_steps: int,
        validate: Validator[T] | None = None,
    ) -> T: ...


def build_chat_model(settings: Settings) -> BaseChatModel:
    return ChatAnthropic(
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        max_retries=2,
        output_config={"effort": settings.llm_effort},
        # Automatic prompt caching: repeated prefixes (system prompt, tool definitions,
        # earlier turns of a tool loop) are billed at a fraction of the normal input price.
        model_kwargs={"cache_control": {"type": "ephemeral"}},
    )


class LLMReasoner:
    def __init__(self, settings: Settings, ledger: UsageLedger, thread_id: str,
                 model: BaseChatModel | None = None):
        self._settings = settings
        self._ledger = ledger
        self._thread_id = thread_id
        self._model = model or build_chat_model(settings)

    # ------------------------------------------------------------------ public API

    def structured(self, step: str, system: str, user: str, schema: type[T]) -> T:
        runnable = self._model.with_structured_output(schema, method="json_schema", include_raw=True)
        out = self._invoke(runnable, [SystemMessage(system), HumanMessage(user)], step)
        if out["parsing_error"] is not None or out["parsed"] is None:
            raise ReasoningFailed(f"{step}: model output did not match {schema.__name__}: {out['parsing_error']}")
        return out["parsed"]

    def tool_loop(self, step, system, user, tools, submit_schema, max_steps, validate=None):
        """Up to max_steps rounds of tool use, then one last round in which only a submission counts.

        The conversation is append-only and the tool list never changes during a loop: current models
        bind their reasoning to the exact earlier context, so editing it would invalidate that reasoning.
        """
        submit_name = submit_schema.__name__
        # strict=True: the API guarantees every tool call matches its JSON schema. Without it the model
        # sometimes dropped required fields or sent a list as a string (found in the LangSmith traces).
        model = self._model.bind_tools([*tools, submit_schema], strict=True)
        by_name = {t.name: t for t in tools}
        messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(user)]

        for i in range(max_steps + 1):
            budget_left = i < max_steps
            ai: AIMessage = self._invoke(model, messages, step)
            messages.append(ai)

            if not ai.tool_calls:
                messages.append(HumanMessage(f"Use the tools, or call {submit_name} to submit your answer."))
                continue

            replies: list[ToolMessage] = []
            for call in ai.tool_calls:
                if call["name"] == submit_name:
                    result, error = self._validate(submit_schema, call["args"], validate)
                    if result is not None:
                        return result
                    log.warning("%s: submission rejected: %s", step, error)
                    reply = f"Rejected: {error}"
                elif not budget_left:
                    reply = "Not run: the tool budget is used up."
                elif (tool := by_name.get(call["name"])) is None:
                    reply = f"Unknown tool {call['name']}"
                else:
                    reply = self._run_tool(tool, call["args"])
                replies.append(ToolMessage(reply, tool_call_id=call["id"]))
            messages.extend(replies)
            if i == max_steps - 1:
                messages.append(HumanMessage(f"Tool budget used up. Call {submit_name} now with your best answer."))

        raise ReasoningFailed(f"{step}: no valid {submit_name} after {max_steps} tool steps")

    # ------------------------------------------------------------------ internals

    def _invoke(self, runnable: Runnable, messages: list[BaseMessage], step: str):
        self._ledger.ensure_within_budget(self._thread_id)
        out = runnable.invoke(messages, config={"run_name": step})
        raw = out["raw"] if isinstance(out, dict) else out
        self._ledger.record(self._thread_id, step, Usage.from_metadata(getattr(raw, "usage_metadata", None)))
        return out

    @staticmethod
    def _validate(schema: type[T], args: dict, validate: Validator[T] | None) -> tuple[T | None, str | None]:
        try:
            result = schema.model_validate(args)
        except ValidationError as exc:
            return None, str(exc)
        error = validate(result) if validate else None
        return (None, error) if error else (result, None)

    @staticmethod
    def _run_tool(tool: BaseTool, args: dict) -> str:
        try:
            return str(tool.invoke(args))
        except Exception as exc:  # a failing tool is information for the model, not a crash
            log.info("tool %s failed: %s", tool.name, exc)
            return f"Error: {exc}"
