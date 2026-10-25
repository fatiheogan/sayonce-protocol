"""Cost of recovery: SayOnce under injected faults (spec 5.7, 5.8, 8.4).

    python -m sayonce.bench.faults --context-kb 10 100 --rounds 50 --fault-every 10 \\
        --network ideal 3g --out results/faults.csv

Each run is a normal SayOnce conversation in which a fault is injected before
every Nth round. Fault kinds:

  corrupt_msg     a MSG is modified in transit; the server's hash check fails, it sends
                  RESYNC, the client rolls back, sends a SNAPSHOT and repeats the MSG
  server_diverge  the server's context silently differs (bug); detected on the next MSG,
                  same recovery as corrupt_msg
  client_diverge  the client's context differs after its MSG was accepted; detected on
                  the REPLY, client sends RESYNC, server answers with a SNAPSHOT
  drop_resume     the connection drops between rounds; the client resumes the session
                  and the server still has it, so no context is re-sent
  server_restart  the server restarts and loses all sessions; the resume fails and the
                  client sends its whole context as a SNAPSHOT

Stateless baselines have nothing to recover, so this is SayOnce only. (A corrupted
message there is not detected at all; it simply produces a wrong answer.)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from ..agents import WorkerAgent
from ..codec import Frame, context_hash
from ..context import ContextStore
from ..messages import MessageType
from ..session import ClientSession, Server
from .harness import parse_network
from .netem import PROFILES, NetConditions, NetemProxy
from .workload import travel_planning

FAULTS = ["none", "corrupt_msg", "server_diverge", "client_diverge", "drop_resume", "server_restart"]
COLUMNS = ["fault", "context_kb", "network", "round", "is_fault", "bytes_sent", "bytes_received",
           "bytes_total", "cum_bytes", "latency_ms", "resyncs", "resumed"]


def diverge(store: ContextStore, key: str = "fault_marker", value: Any = "diverged") -> None:
    """Give a store a different but internally consistent context (a buggy or restarted peer)."""
    v, ctx, _ = store.snapshot()
    ctx["vars"][key] = value
    store.load_snapshot(v, ctx, context_hash(ctx))


async def run_fault(kind: str, context_kb: int, rounds: int, fault_every: int,
                    net: NetConditions = PROFILES["ideal"], seed: int = 0) -> list[dict[str, Any]]:
    if kind not in FAULTS:
        raise ValueError(f"unknown fault {kind!r}, choose from {FAULTS}")
    wl = travel_planning(context_kb, rounds, seed=seed)
    server = await Server(WorkerAgent(), agent_id="agent-b").start()
    server_port = server.port
    proxy = None
    if not net.is_ideal:
        proxy = await NetemProxy(server_port, net, seed=seed).start()
    port = proxy.port if proxy else server_port

    rows: list[dict[str, Any]] = []
    base = {"fault": kind, "context_kb": context_kb, "network": net.label()}
    t0 = time.perf_counter()
    client = await ClientSession.open("127.0.0.1", port, "agent-a", wl.context, wl.dictionary)
    cum = client.conn.stats.bytes_total
    rows.append({**base, "round": 0, "is_fault": 0, "bytes_sent": client.conn.stats.bytes_sent,
                 "bytes_received": client.conn.stats.bytes_received, "bytes_total": cum, "cum_bytes": cum,
                 "latency_ms": round((time.perf_counter() - t0) * 1000, 3), "resyncs": 0, "resumed": 0})
    try:
        for i, rnd in enumerate(wl.rounds, start=1):
            is_fault = kind != "none" and i % fault_every == 0
            extra_sent = extra_recv = 0
            resumed = 0
            t0 = time.perf_counter()
            restore_send = None
            resyncs_before = client.resync_count  # carried over to a resumed session

            if is_fault:
                if kind == "corrupt_msg":
                    def tamper(frame: Frame, done: list = []) -> Frame:  # noqa: B006 - one-shot state
                        if frame.type == MessageType.MSG and not done:
                            done.append(1)
                            body = dict(frame.body)
                            body[1] = "tampered in transit"
                            return Frame(type=frame.type, seq=frame.seq, ctx_v=frame.ctx_v, body=body)
                        return frame
                    client.conn.fault = tamper
                elif kind == "server_diverge":
                    diverge(server.sessions[client.session_id])
                elif kind == "client_diverge":
                    orig = client._send_msg

                    async def send_then_diverge(*a, _orig=orig, **kw):
                        seq = await _orig(*a, **kw)
                        diverge(client.store)
                        return seq

                    client._send_msg = send_then_diverge
                    restore_send = orig
                elif kind in ("drop_resume", "server_restart"):
                    await client.close(bye=False)
                    if kind == "server_restart":
                        await server.close()
                        server = await Server(WorkerAgent(), agent_id="agent-b", port=server_port).start()
                    client = await ClientSession.resume("127.0.0.1", port, client)
                    extra_sent, extra_recv = client.conn.stats.bytes_sent, client.conn.stats.bytes_received
                    resumed = int(client.resumed)

            res = await client.request(rnd.intent, rnd.content, delta=rnd.delta, task_id=rnd.task_id)
            client.conn.fault = None
            if restore_send is not None:
                client._send_msg = restore_send
            resyncs = client.resync_count - resyncs_before  # includes a SNAPSHOT sent while resuming

            sent, recv = res.bytes_sent + extra_sent, res.bytes_received + extra_recv
            cum += sent + recv
            rows.append({**base, "round": i, "is_fault": int(is_fault), "bytes_sent": sent, "bytes_received": recv,
                         "bytes_total": sent + recv, "cum_bytes": cum,
                         "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                         "resyncs": resyncs, "resumed": resumed})

        # the run is only valid if both sides ended in sync
        final = server.sessions[client.session_id]
        if final.hash != client.store.hash:
            raise RuntimeError(f"{kind}: client and server ended out of sync")
    finally:
        await client.close()
        await server.close()
        if proxy:
            await proxy.close()
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extra bytes and time per fault.

    Paired comparison: each faulty round is compared with the same round of the
    fault-free run ("none") under the same context size and network, because rounds
    differ in size (e.g. every 5th round is a short INFORM). Falls back to the mean
    of the run's normal rounds if no "none" run is present.
    """
    ref = {(r["context_kb"], r["network"], r["round"]): r for r in rows if r["fault"] == "none"}
    out = []
    keys = list(dict.fromkeys((r["fault"], r["context_kb"], r["network"]) for r in rows))
    for fault, kb, net in keys:
        rs = [r for r in rows if (r["fault"], r["context_kb"], r["network"]) == (fault, kb, net)]
        setup = next(r for r in rs if r["round"] == 0)
        normal = [r for r in rs if r["round"] > 0 and not r["is_fault"]]
        faulty = [r for r in rs if r["is_fault"]]
        nb = statistics.mean(r["bytes_total"] for r in normal)
        nl = statistics.mean(r["latency_ms"] for r in normal)
        extra_b, extra_ms = [], []
        for r in faulty:
            base = ref.get((kb, net, r["round"]))
            extra_b.append(r["bytes_total"] - (base["bytes_total"] if base else nb))
            extra_ms.append(r["latency_ms"] - (base["latency_ms"] if base else nl))
        out.append({
            "fault": fault, "context_kb": kb, "network": net, "faults": len(faulty),
            "setup_bytes": setup["bytes_total"], "normal_round_bytes": round(nb), "normal_round_ms": round(nl, 2),
            "extra_bytes_per_fault": round(statistics.mean(extra_b)) if extra_b else 0,
            "extra_ms_per_fault": round(statistics.mean(extra_ms), 2) if extra_ms else 0.0,
            "resyncs": sum(r["resyncs"] for r in rs),
            "paired": bool(faulty) and all((kb, net, r["round"]) in ref for r in faulty),
        })
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Measure SayOnce recovery cost under injected faults.")
    p.add_argument("--faults", nargs="+", default=FAULTS, choices=FAULTS)
    p.add_argument("--context-kb", nargs="+", type=int, default=[10, 100])
    p.add_argument("--rounds", type=int, default=50)
    p.add_argument("--fault-every", type=int, default=10)
    p.add_argument("--network", nargs="+", type=parse_network, default=[PROFILES["ideal"]])
    p.add_argument("--out", type=Path, default=Path("results/faults.csv"))
    a = p.parse_args(argv)

    async def go():
        rows = []
        for net in a.network:
            for kb in a.context_kb:
                for kind in a.faults:
                    t0 = time.perf_counter()
                    rows += await run_fault(kind, kb, a.rounds, a.fault_every, net)
                    print(f"  {net.label():>10s} {kind:15s} {kb:>4} KB  {time.perf_counter() - t0:5.1f}s",
                          file=sys.stderr)
        return rows

    rows = asyncio.run(go())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    summary = summarize(rows)
    print(f"{'network':>10s} {'fault':15s} {'ctx':>5s} {'faults':>6s} {'setup':>9s} {'normal':>8s} "
          f"{'extra B/fault':>13s} {'extra ms/fault':>14s} {'resyncs':>7s}")
    for s in summary:
        print(f"{s['network']:>10s} {s['fault']:15s} {s['context_kb']:>4}K {s['faults']:>6} {s['setup_bytes']:>9,} "
              f"{s['normal_round_bytes']:>8,} {s['extra_bytes_per_fault']:>13,} {s['extra_ms_per_fault']:>14.2f} "
              f"{s['resyncs']:>7}")
    print(f"\nwrote {len(rows)} rows to {a.out}")


if __name__ == "__main__":
    main()
