"""Reproducible multi-round workloads.

A workload is the list of client messages for one conversation: each round has
an intent, the message content and a small client-side delta. The same seed
always gives the same workload, and every system receives exactly the same one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ..agents import _text, sample_context
from ..messages import DeltaOp, Intent


@dataclass
class Round:
    intent: Intent
    content: Any
    delta: list = field(default_factory=list)
    task_id: int | None = None


@dataclass
class Workload:
    name: str
    context: dict
    dictionary: list[str]
    rounds: list[Round]


def travel_planning(context_kb: int, rounds: int, seed: int = 0, msg_words: int = 20) -> Workload:
    """A client agent iteratively refines a trip with a worker agent.

    Most rounds are REQUESTs; every 5th round is an INFORM (new constraint);
    every round adjusts one shared variable via a delta.
    """
    ctx, dictionary = sample_context(context_kb, seed=seed)
    rng = random.Random(seed + 1)
    out = []
    for i in range(rounds):
        if i % 5 == 4:
            intent = Intent.INFORM
            content = "New constraint: " + _text(rng, msg_words // 2)
        else:
            intent = Intent.REQUEST
            content = f"Step {i + 1}: " + _text(rng, msg_words)
        delta = [[DeltaOp.SET, ["vars", "budget"], 500 - 5 * i]]
        out.append(Round(intent=intent, content=content, delta=delta, task_id=i))
    return Workload(name="travel", context=ctx, dictionary=dictionary, rounds=out)


WORKLOADS = {"travel": travel_planning}
