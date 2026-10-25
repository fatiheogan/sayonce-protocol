"""Example agents with a mock LLM.

The mock LLM is deterministic and needs no API key, so experiments are
reproducible. It also reports how many characters of prompt it would have
read, which the benchmark later turns into token counts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .messages import DeltaOp, Intent, ReplyStatus
from .session import Request, Response


def render_prompt(ctx: dict) -> str:
    """Render the shared context as the text an LLM would read.

    Segments come in fixed order (sys, tools, hist, vars), so the beginning of
    the prompt stays the same from round to round (spec 5.2, 8.3).
    """
    parts = [
        "## Instructions\n" + ctx["sys"],
        "## Tools\n" + json.dumps(ctx["tools"], sort_keys=True, ensure_ascii=False),
        "## History\n" + "\n".join(json.dumps(t, sort_keys=True, ensure_ascii=False) for t in ctx["hist"]),
        "## State\n" + json.dumps(ctx["vars"], sort_keys=True, ensure_ascii=False),
    ]
    return "\n\n".join(parts)


@dataclass
class MockLLM:
    """Pretends to be an LLM: answer length and content depend only on the input."""

    reply_chars: int = 200
    calls: int = 0
    prompt_chars_total: int = 0

    def complete(self, prompt: str, question: Any) -> str:
        self.calls += 1
        self.prompt_chars_total += len(prompt)
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        text = f"Answer #{self.calls} to {str(question)[:60]!r}. ref={digest[:12]} "
        filler = "lorem ipsum dolor sit amet " * (self.reply_chars // 27 + 1)
        return (text + filler)[: max(self.reply_chars, len(text))]


class WorkerAgent:
    """Server-side agent (Agent B): answers requests with the mock LLM.

    After each request it records a short task status in the shared "vars"
    segment, so every REPLY also carries a small delta.
    """

    def __init__(self, llm: MockLLM | None = None):
        self.llm = llm or MockLLM()

    def __call__(self, req: Request) -> Response:
        if req.intent == Intent.CANCEL:
            return Response(content="cancelled", delta=[[DeltaOp.SET, ["vars", "status"], "cancelled"]])
        if req.intent == Intent.INFORM:
            return Response(content="ack")

        answer = self.llm.complete(render_prompt(req.ctx), req.content)
        delta = [
            [DeltaOp.SET, ["vars", "status"], "done"],
            [DeltaOp.SET, ["vars", "last_task"], req.task_id if req.task_id is not None else -1],
        ]
        return Response(content=answer, status=ReplyStatus.OK, delta=delta)


def sample_context(size_kb: int = 10) -> tuple[dict, list[str]]:
    """A travel-agent style context of roughly size_kb kilobytes, plus a dictionary."""
    n_tools = max(1, size_kb * 2)
    tools = {
        f"tool_{i}": {
            "description": f"Tool number {i}. " + "Looks up data in an external system. " * 10,
            "params": {"query": "string", "limit": "integer", "lang": "string"},
        }
        for i in range(n_tools)
    }
    ctx = {
        "sys": "You are a helpful travel planning agent. Follow the user's constraints. " * 10,
        "tools": tools,
        "hist": [],
        "vars": {"budget": 500, "status": "new"},
    }
    dictionary = ["sys", "tools", "hist", "vars", "budget", "status", "last_task",
                  "description", "params", "query", "limit", "lang", *tools.keys()]
    return ctx, dictionary
