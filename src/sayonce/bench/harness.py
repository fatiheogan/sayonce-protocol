"""Benchmark harness: run every system on the same workloads and write a CSV.

    python -m sayonce.bench.harness --systems all --context-kb 1 10 50 100 \\
        --rounds 50 --repeats 3 --out results/sweep.csv

One row per (system, context size, repeat, round). Round 0 is the session
setup (HELLO for SayOnce, session/open for json-delta, nothing for stateless
baselines). Cumulative values can be read at any round, so a 50-round run also
gives the 1, 5, 10 and 20 round results.

Columns (spec section 8):

  bytes_sent / bytes_received / header_bytes   application bytes on the wire
  wire_tokens_sent / wire_tokens_received      tokens of the information that crossed the wire
  llm_prompt_tokens                            tokens the worker's LLM read this round
  llm_prefix_cached_tokens                     leading tokens shared with the previous prompt
                                               (what a provider prefix cache could reuse)
  latency_ms, cpu_ms                           per round (cpu = client + server, same process)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..agents import MockLLM, WorkerAgent, render_prompt
from ..session import Request, Response
from .systems import SYSTEMS, System, make_system
from .tokens import TokenCounter, default_counter
from .workload import WORKLOADS, Workload

COLUMNS = [
    "system", "workload", "context_kb", "repeat", "round", "intent",
    "bytes_sent", "bytes_received", "bytes_total", "header_bytes", "cum_bytes",
    "wire_tokens_sent", "wire_tokens_received", "wire_tokens_total", "cum_wire_tokens",
    "llm_prompt_tokens", "llm_prefix_cached_tokens", "llm_uncached_tokens",
    "latency_ms", "cpu_ms", "tokenizer",
]


@dataclass
class RunConfig:
    system: str
    context_kb: int
    rounds: int
    workload: str = "travel"
    seed: int = 0
    repeat: int = 0


class PromptRecorder:
    """Wraps the worker agent and records the prompt its LLM reads each round."""

    def __init__(self, agent: WorkerAgent):
        self.agent = agent
        self.last_prompt: str | None = None

    def __call__(self, req: Request) -> Response:
        before = self.agent.llm.calls
        resp = self.agent(req)
        self.last_prompt = render_prompt(req.ctx) if self.agent.llm.calls > before else None
        return resp


class _TokenCache:
    """Tokenizing a 100 KB prompt 50 times per system is slow; prompts repeat across systems."""

    def __init__(self, counter: TokenCounter):
        self.counter = counter
        self._enc: dict[str, list] = {}

    def encode(self, text: str) -> list:
        key = hashlib.sha1(text.encode()).hexdigest()
        if key not in self._enc:
            self._enc[key] = self.counter.encode(text)
        return self._enc[key]

    def prefix(self, a: list, b: list) -> int:
        n = 0
        for x, y in zip(a, b):
            if x != y:
                break
            n += 1
        return n


async def run_one(cfg: RunConfig, counter: TokenCounter | None = None, cache: _TokenCache | None = None,
                  workload: Workload | None = None) -> list[dict[str, Any]]:
    counter = counter or default_counter()
    cache = cache or _TokenCache(counter)
    wl = workload or WORKLOADS[cfg.workload](cfg.context_kb, cfg.rounds, seed=cfg.seed)

    recorder = PromptRecorder(WorkerAgent(MockLLM()))
    system: System = make_system(cfg.system)
    await system.start(recorder)
    rows: list[dict[str, Any]] = []
    base = {"system": cfg.system, "workload": wl.name, "context_kb": cfg.context_kb,
            "repeat": cfg.repeat, "tokenizer": counter.name}
    raw: list[tuple] = []
    try:
        c0 = time.process_time()
        setup = await system.open("agent-a", wl.context, wl.dictionary)
        setup_cpu = time.process_time() - c0
        for rnd in wl.rounds:
            c0 = time.process_time()
            res = await system.request(rnd.intent, rnd.content, delta=rnd.delta, task_id=rnd.task_id)
            cpu = time.process_time() - c0
            raw.append((rnd, res, cpu, recorder.last_prompt))
    finally:
        await system.close()

    # Token counting happens after the run, so it does not affect cpu_ms or latency.
    cum_bytes = setup.bytes_total
    setup_tokens = counter.count_json(setup.info_sent) if setup.info_sent is not None else 0
    cum_tokens = setup_tokens
    rows.append({**base, "round": 0, "intent": "SETUP",
                 "bytes_sent": setup.bytes_sent, "bytes_received": setup.bytes_received,
                 "bytes_total": setup.bytes_total, "header_bytes": setup.header_bytes, "cum_bytes": cum_bytes,
                 "wire_tokens_sent": setup_tokens, "wire_tokens_received": 0,
                 "wire_tokens_total": setup_tokens, "cum_wire_tokens": cum_tokens,
                 "llm_prompt_tokens": 0, "llm_prefix_cached_tokens": 0, "llm_uncached_tokens": 0,
                 "latency_ms": 0.0, "cpu_ms": round(setup_cpu * 1000, 3)})

    prev_prompt_tokens: list | None = None
    for i, (rnd, res, cpu, prompt) in enumerate(raw, start=1):
        ts, tr = counter.count_json(res.info_sent), counter.count_json(res.info_received)
        cum_bytes += res.bytes_total
        cum_tokens += ts + tr
        if prompt is not None:
            ptoks = cache.encode(prompt)
            cached = cache.prefix(prev_prompt_tokens, ptoks) if prev_prompt_tokens is not None else 0
            prev_prompt_tokens = ptoks
            llm_in = len(ptoks)
        else:
            llm_in = cached = 0
        rows.append({**base, "round": i, "intent": rnd.intent.name,
                     "bytes_sent": res.bytes_sent, "bytes_received": res.bytes_received,
                     "bytes_total": res.bytes_total, "header_bytes": res.header_bytes, "cum_bytes": cum_bytes,
                     "wire_tokens_sent": ts, "wire_tokens_received": tr, "wire_tokens_total": ts + tr,
                     "cum_wire_tokens": cum_tokens,
                     "llm_prompt_tokens": llm_in, "llm_prefix_cached_tokens": cached,
                     "llm_uncached_tokens": llm_in - cached,
                     "latency_ms": round(res.latency_s * 1000, 3), "cpu_ms": round(cpu * 1000, 3)})
    return rows


async def sweep(systems: Iterable[str], context_kbs: Iterable[int], rounds: int, repeats: int = 1,
                workload: str = "travel", seed: int = 0, progress: bool = True) -> list[dict[str, Any]]:
    counter = default_counter()
    cache = _TokenCache(counter)
    rows: list[dict[str, Any]] = []
    for kb in context_kbs:
        wl = WORKLOADS[workload](kb, rounds, seed=seed)  # same workload for every system
        for rep in range(repeats):
            for name in systems:
                t0 = time.perf_counter()
                rows += await run_one(RunConfig(name, kb, rounds, workload, seed, rep), counter, cache, wl)
                if progress:
                    print(f"  {name:13s} {kb:>4} KB  repeat {rep}  {time.perf_counter() - t0:5.1f}s", file=sys.stderr)
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path, meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))


def summary(rows: list[dict[str, Any]], at_rounds: Iterable[int] = (1, 10, 50)) -> str:
    """Cumulative bytes and wire tokens at selected rounds (repeat 0)."""
    lines = []
    keys = sorted({(r["context_kb"], r["system"]) for r in rows}, key=lambda k: (k[0], list(SYSTEMS).index(k[1])))
    by = {(r["context_kb"], r["system"], r["round"]): r for r in rows if r["repeat"] == 0}
    max_round = max(r["round"] for r in rows)
    at = [n for n in at_rounds if n <= max_round]
    head = f"{'ctx':>5} {'system':13s}" + "".join(f" {'bytes@' + str(n):>12} {'tok@' + str(n):>10}" for n in at)
    lines.append(head)
    last_kb = None
    for kb, name in keys:
        if last_kb is not None and kb != last_kb:
            lines.append("")
        last_kb = kb
        cells = "".join(f" {by[(kb, name, n)]['cum_bytes']:>12,} {by[(kb, name, n)]['cum_wire_tokens']:>10,}" for n in at)
        lines.append(f"{kb:>4}K {name:13s}{cells}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Run the SayOnce benchmark sweep.")
    p.add_argument("--systems", nargs="+", default=["all"], help=f"any of {list(SYSTEMS)} or 'all'")
    p.add_argument("--context-kb", nargs="+", type=int, default=[1, 10, 50, 100])
    p.add_argument("--rounds", type=int, default=50)
    p.add_argument("--repeats", type=int, default=1, help="repeat runs (bytes are deterministic; latency is not)")
    p.add_argument("--workload", default="travel", choices=list(WORKLOADS))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=Path("results/sweep.csv"))
    args = p.parse_args(argv)

    systems = list(SYSTEMS) if args.systems == ["all"] else args.systems
    counter = default_counter()
    if not counter.exact:
        print("WARNING: tiktoken not available, using approximate token counts "
              "(column tokenizer=approx). Do not use these numbers in the final report.", file=sys.stderr)

    t0 = time.perf_counter()
    rows = asyncio.run(sweep(systems, args.context_kb, args.rounds, args.repeats, args.workload, args.seed))
    meta = {
        "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "systems": systems,
        "tokenizer": counter.name,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": round(time.perf_counter() - t0, 1),
        "network": "localhost, no emulation",
    }
    write_csv(rows, args.out, meta)
    print(summary(rows))
    print(f"\nwrote {len(rows)} rows to {args.out} (tokenizer: {counter.name})")


if __name__ == "__main__":
    main()
