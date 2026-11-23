"""The tool loop in LLMReasoner, driven by a fake chat model that replays scripted messages."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from pydantic import BaseModel

from investigator.budget import UsageLedger
from investigator.llm import LLMReasoner, ReasoningFailed


class Answer(BaseModel):
    value: int


class ScriptedChat(BaseChatModel):
    replies: list[AIMessage]
    seen: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def call(name: str, args: dict, i: int) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}],
                     usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110})


@tool
def double(x: int) -> str:
    """Double a number."""
    return str(2 * x)


def reasoner(settings, tmp_path, replies) -> tuple[LLMReasoner, ScriptedChat, UsageLedger]:
    model = ScriptedChat(replies=replies, seen=[])
    ledger = UsageLedger(tmp_path / "u.sqlite", settings)
    return LLMReasoner(settings, ledger, "t", model=model), model, ledger


def test_tools_then_submit_records_usage(settings, tmp_path):
    r, model, ledger = reasoner(settings, tmp_path, [call("double", {"x": 4}, 1), call("Answer", {"value": 8}, 2)])
    assert r.tool_loop("step", "sys", "user", [double], Answer, max_steps=3) == Answer(value=8)
    tool_reply = model.seen[1][-1]
    assert isinstance(tool_reply, ToolMessage) and tool_reply.content == "8"
    assert ledger.thread_tokens("t") == 220


def test_rejected_submission_is_sent_back_to_the_model(settings, tmp_path):
    r, model, _ = reasoner(settings, tmp_path, [call("Answer", {"value": 3}, 1), call("Answer", {"value": 4}, 2)])
    result = r.tool_loop("step", "sys", "user", [double], Answer, max_steps=3,
                         validate=lambda a: None if a.value % 2 == 0 else "must be even")
    assert result.value == 4
    assert "Rejected: must be even" in model.seen[1][-1].content


def test_unknown_tool_and_tool_errors_do_not_crash(settings, tmp_path):
    r, model, _ = reasoner(settings, tmp_path, [
        call("nope", {}, 1), call("double", {"x": "not a number"}, 2), call("Answer", {"value": 1}, 3)])
    assert r.tool_loop("step", "sys", "user", [double], Answer, max_steps=5).value == 1
    assert "Unknown tool" in model.seen[1][-1].content
    assert model.seen[2][-1].content.startswith("Error")


def test_gives_up_after_max_steps(settings, tmp_path):
    replies = [call("double", {"x": i}, i) for i in range(3)]
    r, model, _ = reasoner(settings, tmp_path, replies)
    with pytest.raises(ReasoningFailed):
        r.tool_loop("step", "sys", "user", [double], Answer, max_steps=2)
    assert "Tool budget used up" in model.seen[-1][-1].content  # the last turn asks for a submission
