"""Run the benchmark between two computers over a real network (for example a phone hotspot).

On the server computer (Agent B):

    python -m sayonce.bench.remote serve

On the client computer (Agent A), with the IP address the server printed:

    python -m sayonce.bench.remote run --host 192.168.43.10 --label hotspot-4g \\
        --workload mcp --context-kb 10 100 --rounds 20 --repeats 3 --out results/real/hotspot-4g.csv

The server starts every system once, listening on all interfaces, and answers
on a control port (default 7480) with the port of each system. The client then
runs exactly the same workloads as the harness, but every request crosses the
real link. The CSV has the harness columns; use it for time (latency_ms). Bytes
match the local runs to within a few bytes (the mock LLM's answer numbering
continues across runs on a long-lived server). The LLM token columns are 0
because the worker runs on the other computer.

The client also measures the round-trip time of the link (TCP connects to the
control port) and stores it in the .meta.json file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import socket
import statistics
import sys
import time
from pathlib import Path

from ..agents import MockLLM, WorkerAgent
from .harness import RunConfig, run_one, write_csv
from .netem import NetConditions
from .systems import SYSTEMS, make_system
from .tokens import default_counter
from .workload import WORKLOADS

CONTROL_PORT = 7480
DEFAULT_SYSTEMS = ["jsonrpc", "jsonrpc-gzip", "cbor-full", "json-delta", "sayonce"]


def local_ips() -> list[str]:
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; picks the outgoing interface
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips


# ---------------------------------------------------------------------- server


class RemoteServer:
    """All systems plus the control port that tells clients where they are."""

    def __init__(self, port: int = CONTROL_PORT, systems: list[str] | None = None, host: str = "0.0.0.0"):
        self.port, self.host = port, host
        self.names = systems or DEFAULT_SYSTEMS
        self.running: dict = {}
        self.control: asyncio.Server | None = None

    async def start(self) -> "RemoteServer":
        for name in self.names:
            system = make_system(name)
            system.listen_host = self.host
            await system.start(WorkerAgent(MockLLM()))
            self.running[name] = system
        directory = json.dumps({"systems": {n: s.server_port for n, s in self.running.items()},
                                "host": socket.gethostname()}).encode() + b"\n"

        async def on_control(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            writer.write(directory)
            try:
                await writer.drain()
            finally:
                writer.close()

        self.control = await asyncio.start_server(on_control, self.host, self.port)
        self.port = self.control.sockets[0].getsockname()[1]
        return self

    async def close(self) -> None:
        if self.control:
            self.control.close()
            await self.control.wait_closed()
        for s in self.running.values():
            await s.close()


async def serve(port: int = CONTROL_PORT, systems: list[str] | None = None, host: str = "0.0.0.0") -> None:
    server = await RemoteServer(port, systems, host).start()
    print(f"SayOnce benchmark server on {socket.gethostname()}, control port {server.port}")
    for name, s in server.running.items():
        print(f"  {name:14s} port {s.server_port}")
    print("Run the client on the other computer with one of these addresses:")
    for ip in local_ips():
        print(f"  python -m sayonce.bench.remote run --host {ip}")
    print("Windows may ask to allow Python through the firewall: allow it on private networks.")
    print("Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    finally:
        await server.close()


# ---------------------------------------------------------------------- client


async def fetch_directory(host: str, port: int, timeout: float = 10) -> dict:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    try:
        return json.loads(await asyncio.wait_for(reader.readline(), timeout))
    finally:
        writer.close()


async def measure_rtt(host: str, port: int, samples: int = 10) -> list[float]:
    """TCP connect time in ms; a connect takes one round trip (SYN, SYN-ACK)."""
    out = []
    for _ in range(samples):
        t0 = time.perf_counter()
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 10)
        out.append((time.perf_counter() - t0) * 1000)
        writer.close()
        await asyncio.sleep(0.05)
    return out


async def run(host: str, port: int, label: str, systems: list[str], context_kbs: list[int], rounds: int,
              repeats: int, workload: str, seed: int = 0) -> tuple[list[dict], dict]:
    directory = await fetch_directory(host, port)
    missing = [s for s in systems if s not in directory["systems"]]
    if missing:
        raise SystemExit(f"the server does not run {missing}; it has {list(directory['systems'])}")
    rtt = await measure_rtt(host, port)
    print(f"connected to {directory['host']} at {host}; RTT median {statistics.median(rtt):.1f} ms "
          f"(min {min(rtt):.1f}, max {max(rtt):.1f})", file=sys.stderr)
    net = NetConditions(delay_ms=round(statistics.median(rtt) / 2, 2), name=label)
    counter = default_counter()
    rows: list[dict] = []
    for kb in context_kbs:
        wl = WORKLOADS[workload](kb, rounds, seed=seed)
        for rep in range(repeats):
            for name in systems:
                t0 = time.perf_counter()
                cfg = RunConfig(name, kb, rounds, workload, seed, rep, net,
                                remote_host=host, remote_port=directory["systems"][name])
                rows += await run_one(cfg, counter, workload=wl)
                print(f"  {label:>12s}  {name:14s} {kb:>4} KB  repeat {rep}  {time.perf_counter() - t0:6.1f}s",
                      file=sys.stderr)
    rtt_after = await measure_rtt(host, port)
    meta = {"label": label, "host": host, "server": directory["host"], "client": socket.gethostname(),
            "rtt_ms_before": [round(x, 2) for x in rtt], "rtt_ms_after": [round(x, 2) for x in rtt_after],
            "emulation": "none: real network between two computers", "tokenizer": counter.name,
            "python": platform.python_version(), "platform": platform.platform(),
            "args": {"systems": systems, "context_kb": context_kbs, "rounds": rounds, "repeats": repeats,
                     "workload": workload, "seed": seed}}
    return rows, meta


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start all systems for a remote client")
    s.add_argument("--port", type=int, default=CONTROL_PORT)
    s.add_argument("--systems", nargs="+", default=DEFAULT_SYSTEMS, choices=list(SYSTEMS))
    r = sub.add_parser("run", help="run the benchmark against a remote server")
    r.add_argument("--host", required=True)
    r.add_argument("--port", type=int, default=CONTROL_PORT)
    r.add_argument("--label", default="real", help="name of the link, e.g. hotspot-4g or wifi")
    r.add_argument("--systems", nargs="+", default=DEFAULT_SYSTEMS, choices=list(SYSTEMS))
    r.add_argument("--context-kb", nargs="+", type=int, default=[10, 100])
    r.add_argument("--rounds", type=int, default=20)
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--workload", default="mcp", choices=list(WORKLOADS))
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", type=Path, default=Path("results/real/remote.csv"))
    a = p.parse_args(argv)

    if a.cmd == "serve":
        try:
            asyncio.run(serve(a.port, a.systems))
        except KeyboardInterrupt:
            print("Stopped.")
        return
    t0 = time.time()
    rows, meta = asyncio.run(run(a.host, a.port, a.label, a.systems, a.context_kb, a.rounds, a.repeats,
                                 a.workload, a.seed))
    meta["duration_s"] = round(time.time() - t0, 1)
    write_csv(rows, a.out, meta)
    print(f"wrote {len(rows)} rows to {a.out}")


if __name__ == "__main__":
    main()
