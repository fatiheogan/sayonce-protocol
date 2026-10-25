import asyncio
import random
import time

import pytest

from sayonce.bench.harness import parse_network, sweep
from sayonce.bench.netem import MIN_RTO_S, MSS, PROFILES, NetConditions, NetemProxy, _Direction


def run(coro, timeout=30):
    return asyncio.run(asyncio.wait_for(coro, timeout))


async def echo_server():
    async def handle(reader, writer):
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
        writer.close()

    return await asyncio.start_server(handle, "127.0.0.1", 0)


async def roundtrip(cond: NetConditions, payload: bytes, seed: int = 0) -> tuple[float, bytes, NetemProxy]:
    server = await echo_server()
    port = server.sockets[0].getsockname()[1]
    proxy = await NetemProxy(port, cond, seed=seed).start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy.port)
        t0 = time.perf_counter()
        writer.write(payload)
        await writer.drain()
        got = await reader.readexactly(len(payload))
        elapsed = time.perf_counter() - t0
        writer.close()
        return elapsed, got, proxy
    finally:
        await proxy.close()
        server.close()
        await server.wait_closed()


# ------------------------------------------------------------------ through the proxy


def test_delay_adds_one_rtt():
    elapsed, got, _ = run(roundtrip(NetConditions(delay_ms=50), b"ping"))
    assert got == b"ping"
    assert 0.1 <= elapsed < 0.2  # 2 x 50 ms one-way


def test_bandwidth_limits_throughput():
    payload = b"x" * 125_000  # 1 Mbit
    elapsed, got, _ = run(roundtrip(NetConditions(bandwidth_mbps=10), payload))
    assert got == payload
    assert elapsed >= 0.1  # at least 1 Mbit / 10 Mbit/s one way


def test_loss_delays_but_never_corrupts():
    payload = bytes(random.Random(1).randbytes(60_000))
    elapsed, got, proxy = run(roundtrip(NetConditions(delay_ms=5, loss=0.2), payload, seed=3))
    assert got == payload  # TCP semantics: data arrives complete and in order
    assert proxy.stats.lost > 0
    ideal, _, _ = run(roundtrip(NetConditions(delay_ms=5), payload))
    assert elapsed > ideal


def test_loss_is_reproducible_with_seed():
    payload = b"y" * 30_000
    a = run(roundtrip(NetConditions(loss=0.1), payload, seed=7))[2].stats.lost
    b = run(roundtrip(NetConditions(loss=0.1), payload, seed=7))[2].stats.lost
    assert a == b


# ------------------------------------------------------------------ link model


def test_schedule_serialization_and_order():
    d = _Direction(NetConditions(delay_ms=10, bandwidth_mbps=8), random.Random(0))  # 1 byte per us
    out = d.schedule(0.0, b"a" * (3 * MSS))
    times = [t for t, _ in out]
    assert times == sorted(times)
    assert times[0] == pytest.approx(MSS / 1e6 + 0.010)
    assert times[-1] == pytest.approx(3 * MSS / 1e6 + 0.010)
    assert b"".join(seg for _, seg in out) == b"a" * (3 * MSS)


class _LoseFirst(random.Random):
    def __init__(self):
        super().__init__(0)
        self.n = 0

    def random(self):
        self.n += 1
        return 0.0 if self.n == 1 else 1.0  # only the first segment is lost


def test_fast_retransmit_when_enough_segments_follow():
    cond = NetConditions(delay_ms=20, loss=0.5)
    d = _Direction(cond, _LoseFirst())
    out = d.schedule(0.0, b"a" * (5 * MSS))
    assert out[0][0] == pytest.approx(0.020 + cond.rtt_s)  # one extra RTT
    assert all(t >= out[0][0] for t, _ in out)  # head-of-line blocking


def test_timeout_when_message_is_short():
    cond = NetConditions(delay_ms=20, loss=0.5)
    d = _Direction(cond, _LoseFirst())
    [(t, _)] = d.schedule(0.0, b"small")
    assert t == pytest.approx(0.020 + max(MIN_RTO_S, cond.rtt_s) + cond.rtt_s)


def test_profiles_and_parsing():
    assert parse_network("3g") is PROFILES["3g"]
    n = parse_network("100:2:5")
    assert (n.delay_ms, n.loss, n.bandwidth_mbps) == (100, 0.02, 5)
    assert n.label() == "d100ms_l2%_5Mbps"
    with pytest.raises(Exception):
        parse_network("fast")


# ------------------------------------------------------------------ harness integration


def test_harness_runs_through_emulated_network():
    cond = NetConditions(delay_ms=20, bandwidth_mbps=2)
    rows = run(sweep(["jsonrpc", "sayonce"], [5], 3, progress=False, networks=[cond]), timeout=60)
    by = {(r["system"], r["round"]): r for r in rows}
    assert all(r["network"] == cond.label() and r["delay_ms"] == 20 for r in rows)
    assert all(r["net_segments"] > 0 for r in rows)
    for name in ("jsonrpc", "sayonce"):
        for rnd in (1, 2, 3):
            assert by[(name, rnd)]["latency_ms"] >= 40  # at least one RTT
    # full context over a 2 Mbit/s link costs more time per round than a delta
    assert by[("jsonrpc", 3)]["latency_ms"] > by[("sayonce", 3)]["latency_ms"]
    # SayOnce pays for the context once, in setup
    assert by[("sayonce", 0)]["latency_ms"] > by[("jsonrpc", 0)]["latency_ms"]


def test_bytes_identical_with_and_without_emulation():
    ideal = run(sweep(["sayonce"], [5], 3, progress=False))
    slow = run(sweep(["sayonce"], [5], 3, progress=False, networks=[NetConditions(delay_ms=5)]), timeout=60)
    assert [r["bytes_total"] for r in ideal] == [r["bytes_total"] for r in slow]
