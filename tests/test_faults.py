import asyncio

import pytest

from sayonce.bench.faults import FAULTS, run_fault, summarize
from sayonce.bench.netem import NetConditions

ROUNDS, EVERY = 6, 3  # faults at rounds 3 and 6


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 60))


@pytest.fixture(scope="module")
def rows():
    out = []
    for kind in FAULTS:
        out += run(run_fault(kind, 3, ROUNDS, EVERY))
    return out


def of(rows, kind):
    return [r for r in rows if r["fault"] == kind]


def test_every_kind_recovers_and_completes(rows):
    # run_fault raises if client and server end out of sync, so reaching here means recovery worked
    for kind in FAULTS:
        rs = of(rows, kind)
        assert [r["round"] for r in rs] == list(range(ROUNDS + 1))
        assert sum(r["is_fault"] for r in rs) == (0 if kind == "none" else ROUNDS // EVERY)


@pytest.mark.parametrize("kind", ["corrupt_msg", "server_diverge", "client_diverge", "server_restart"])
def test_one_resync_per_fault(rows, kind):
    rs = of(rows, kind)
    assert [r["resyncs"] for r in rs if r["is_fault"]] == [1, 1]
    assert all(r["resyncs"] == 0 for r in rs if not r["is_fault"])


def test_resume_without_resync(rows):
    faulty = [r for r in of(rows, "drop_resume") if r["is_fault"]]
    assert all(r["resumed"] == 1 and r["resyncs"] == 0 for r in faulty)
    restarted = [r for r in of(rows, "server_restart") if r["is_fault"]]
    assert all(r["resumed"] == 0 for r in restarted)


def test_summary_is_paired_and_sensible(rows):
    s = {r["fault"]: r for r in summarize(rows)}
    assert s["none"]["extra_bytes_per_fault"] == 0
    setup = s["none"]["setup_bytes"]
    for kind in ("corrupt_msg", "server_diverge", "client_diverge", "server_restart"):
        assert s[kind]["paired"]
        # a resync re-sends the context once: roughly the setup cost
        assert 0.5 * setup < s[kind]["extra_bytes_per_fault"] < 3 * setup
    assert s["drop_resume"]["extra_bytes_per_fault"] < 0.5 * setup  # no context re-sent


def test_faults_over_emulated_network():
    rows = run(run_fault("corrupt_msg", 2, 4, 2, NetConditions(delay_ms=10)))
    faulty = [r for r in rows if r["is_fault"]]
    normal = [r for r in rows if r["round"] > 0 and not r["is_fault"]]
    assert min(r["latency_ms"] for r in faulty) > max(r["latency_ms"] for r in normal)  # an extra round trip


def test_unknown_fault():
    with pytest.raises(ValueError):
        run(run_fault("meteor", 2, 2, 1))
