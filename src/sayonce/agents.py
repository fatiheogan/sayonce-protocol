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
        import random

        body = _text(random.Random(digest), self.reply_chars // 6 + 1)  # varied, not repetitive filler
        return (text + body)[: max(self.reply_chars, len(text))]


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


_WORDS = """
able access account action active address adjust agent airline airport allow amount analysis answer
apply approve arrival assign attach available average balance batch before benefit booking border
budget buffer cabin calendar cancel capacity carrier category change charge check choose city class
client code collect column combine compare confirm connect constraint contact context convert copy
cost count country create credit currency customer daily data date deadline default delay deliver
departure deposit describe destination detail device direct discount distance document domestic draft
duration early economy edit email enable end entry error estimate event exact exchange exclude expense
export external extra factor fallback fare fetch field file filter final first fixed flight follow
format forward frequency fuel full gate generate given global group guest handle history hotel hour
identify ignore import include index input insert inspect insurance internal invoice item journey key
label language latest layover leg length level limit link list load local location lock lodging lookup
loyalty luggage manage manual map match maximum meal member merge message method minimum mode modify
month name nearest network night notice number object offer option order origin output overnight owner
package page parameter partner passenger passport path pattern payment pending period permit person
pickup place plan policy port prefer premium price primary priority process profile provider purchase
query queue quota range rate reason receipt record reduce refund region reject release remove rental
repeat report request require reserve resource response result return review room route rule schedule
score search season seat section select send sequence service session share shift single size skip
source split standard start state status step stop store string summary supplier support surcharge
table target task tax terminal ticket time timezone token total track traffic transfer transit trip
type update upgrade usage user valid value vehicle vendor verify visa voucher wait warning week window
""".split()


def _text(rng, n_words: int) -> str:
    words = [rng.choice(_WORDS) for _ in range(n_words)]
    sentences, i = [], 0
    while i < len(words):
        k = rng.randint(6, 14)
        chunk = words[i : i + k]
        sentences.append(chunk[0].capitalize() + " " + " ".join(chunk[1:]) + ".")
        i += k
    return " ".join(sentences)


def sample_context(size_kb: int = 10, seed: int = 0) -> tuple[dict, list[str]]:
    """A travel-agent style context of roughly size_kb kilobytes (as JSON), plus a dictionary.

    Text is generated from a fixed vocabulary with a seeded RNG, so it is
    reproducible but not artificially repetitive: it compresses about as well
    as real English JSON (3-4x with gzip), not 20x+ like copy-pasted filler.
    """
    import random

    rng = random.Random(seed)
    target = size_kb * 1024
    sys_text = _text(rng, 60)
    tools: dict = {}
    while len(json.dumps({"sys": sys_text, "tools": tools}, separators=(",", ":"))) < target:
        i = len(tools)
        tools[f"tool_{i}"] = {
            "description": _text(rng, rng.randint(25, 45)),
            "params": {
                rng.choice(_WORDS) + "_" + rng.choice(_WORDS): rng.choice(["string", "integer", "number", "boolean"])
                for _ in range(rng.randint(2, 5))
            },
        }
    ctx = {"sys": sys_text, "tools": tools, "hist": [], "vars": {"budget": 500, "status": "new"}}
    dictionary = ["sys", "tools", "hist", "vars", "budget", "status", "last_task",
                  "description", "params", *tools.keys()]
    return ctx, dictionary
