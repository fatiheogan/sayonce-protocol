"""In-process network emulator: a TCP proxy that adds delay, bandwidth limits and loss.

    client  --->  NetemProxy(listen port)  --->  server
            <---                           <---

Works on any OS (no root, no Linux tc), deterministic with a seed, so
experiments can be repeated exactly. For validation on Linux / WSL2 use
scripts/netem.sh (kernel tc netem) with the harness's --external-netem flag.

Model, per direction:

* Data is cut into TCP-sized segments (MSS 1460 B).
* Bandwidth: each segment occupies the link for len*8/rate seconds;
  segments queue behind each other (serialization delay).
* Delay: fixed one-way propagation delay added to every segment
  (same meaning as `tc netem delay` on the loopback interface).
* Loss: each segment is lost with probability p. TCP hides loss as extra
  delay, not missing data: a lost segment is delivered after a retransmission
  penalty. If at least 3 more segments follow it in the same burst, fast
  retransmit recovers it in about one RTT; otherwise the sender waits for a
  retransmission timeout (Linux minimum 200 ms) plus one RTT.
  Delivery stays in order (head-of-line blocking), as in TCP.

This is an approximation of TCP (no congestion window, no slow start). It is
good for comparing protocols under the same conditions; absolute numbers
should be checked with tc netem.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

MSS = 1460
MIN_RTO_S = 0.200
FAST_RETRANSMIT_DUPACKS = 3


@dataclass(frozen=True)
class NetConditions:
    delay_ms: float = 0.0  # one-way propagation delay
    loss: float = 0.0  # segment loss probability, 0..1
    bandwidth_mbps: float = 0.0  # 0 = unlimited
    name: str = ""

    @property
    def rtt_s(self) -> float:
        return 2 * self.delay_ms / 1000

    @property
    def is_ideal(self) -> bool:
        return self.delay_ms == 0 and self.loss == 0 and self.bandwidth_mbps == 0

    def label(self) -> str:
        if self.name:
            return self.name
        bw = f"{self.bandwidth_mbps:g}Mbps" if self.bandwidth_mbps else "inf"
        return f"d{self.delay_ms:g}ms_l{self.loss * 100:g}%_{bw}"


# Illustrative link profiles for a mobile-communications discussion. These are
# assumptions for the experiments, not measurements; cite sources in the report
# if you use them as "typical" values.
PROFILES: dict[str, NetConditions] = {
    "ideal": NetConditions(name="ideal"),
    "lan": NetConditions(1, 0.0, 1000, "lan"),
    "wifi": NetConditions(10, 0.005, 50, "wifi"),
    "4g": NetConditions(30, 0.01, 20, "4g"),
    "3g": NetConditions(75, 0.02, 2, "3g"),
    "edge": NetConditions(150, 0.02, 0.2, "edge"),
    "satellite": NetConditions(300, 0.005, 10, "satellite"),
}


@dataclass
class _Direction:
    cond: NetConditions
    rng: random.Random
    link_free_at: float = 0.0
    last_delivery: float = 0.0
    segments: int = 0
    lost: int = 0

    def schedule(self, now: float, data: bytes) -> list[tuple[float, bytes]]:
        """Return (delivery time, bytes) for each segment of this burst."""
        out = []
        segs = [data[i : i + MSS] for i in range(0, len(data), MSS)]
        rate = self.cond.bandwidth_mbps * 1e6 / 8 if self.cond.bandwidth_mbps else 0.0
        rtt = self.cond.rtt_s
        for idx, seg in enumerate(segs):
            start = max(now, self.link_free_at)
            done = start + (len(seg) / rate if rate else 0.0)
            self.link_free_at = done
            t = done + self.cond.delay_ms / 1000
            self.segments += 1
            if self.cond.loss and self.rng.random() < self.cond.loss:
                self.lost += 1
                following = len(segs) - idx - 1
                if following >= FAST_RETRANSMIT_DUPACKS:
                    t += rtt  # fast retransmit
                else:
                    t += max(MIN_RTO_S, rtt) + rtt  # wait for timeout, then resend
                # the resend also occupies the link
                self.link_free_at += len(seg) / rate if rate else 0.0
            t = max(t, self.last_delivery)  # in-order delivery
            self.last_delivery = t
            out.append((t, seg))
        return out


@dataclass
class ProxyStats:
    segments: int = 0
    lost: int = 0
    connections: int = 0


class NetemProxy:
    """Forward TCP connections from a local port to the target, through the link model."""

    def __init__(self, target_port: int, cond: NetConditions, seed: int = 0,
                 target_host: str = "127.0.0.1", host: str = "127.0.0.1"):
        self.target = (target_host, target_port)
        self.cond = cond
        self.host = host
        self.port = 0
        self.stats = ProxyStats()
        self._seed = seed
        self._server: asyncio.base_events.Server | None = None
        self._tasks: set[asyncio.Task] = set()
        self._writers: set[asyncio.StreamWriter] = set()
        self._dirs: list[_Direction] = []

    async def start(self) -> "NetemProxy":
        self._server = await asyncio.start_server(self._on_client, self.host, 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def close(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        for w in list(self._writers):
            w.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self._collect()

    def _collect(self) -> None:
        self.stats.segments = sum(d.segments for d in self._dirs)
        self.stats.lost = sum(d.lost for d in self._dirs)

    async def _on_client(self, c_reader: asyncio.StreamReader, c_writer: asyncio.StreamWriter) -> None:
        s_reader, s_writer = await asyncio.open_connection(*self.target)
        self._writers |= {c_writer, s_writer}
        n = self.stats.connections
        self.stats.connections += 1
        up = _Direction(self.cond, random.Random(self._seed * 1000 + 2 * n))
        down = _Direction(self.cond, random.Random(self._seed * 1000 + 2 * n + 1))
        self._dirs += [up, down]
        tasks = [
            asyncio.ensure_future(self._pump(c_reader, s_writer, up)),
            asyncio.ensure_future(self._pump(s_reader, c_writer, down)),
        ]
        self._tasks.update(tasks)
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._tasks.difference_update(tasks)
            for w in (c_writer, s_writer):
                w.close()
                self._writers.discard(w)
            self._collect()

    async def _pump(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, d: _Direction) -> None:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[float, bytes] | None] = asyncio.Queue()

        async def deliver() -> None:
            while True:
                item = await queue.get()
                if item is None:
                    if writer.can_write_eof():
                        writer.write_eof()
                    return
                t, seg = item
                wait = t - loop.time()
                if wait > 0:
                    await asyncio.sleep(wait)
                writer.write(seg)
                await writer.drain()

        sender = asyncio.ensure_future(deliver())
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                for item in d.schedule(loop.time(), data):
                    queue.put_nowait(item)
        except (ConnectionError, OSError):
            pass
        finally:
            queue.put_nowait(None)
            try:
                await sender
            except (ConnectionError, OSError):
                pass
