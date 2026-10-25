import asyncio
import json

import pytest

from sayonce.agents import WorkerAgent, sample_context
from sayonce.bench.systems import SYSTEMS, delta_from_json, delta_to_json, make_system
from sayonce.messages import DeltaOp, Intent, ReplyStatus

ROUNDS = 8


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 30))


async def drive(name: str, rounds: int = ROUNDS, size_kb: int = 10):
    system = make_system(name)
    await system.start(WorkerAgent())
    ctx, d = sample_context(size_kb)
    try:
        setup = await system.open("agent-a", ctx, d)
        results = []
        for i in range(rounds):
            delta = [[DeltaOp.SET, ["vars", "budget"], 500 - i]]
            intent = Intent.INFORM if i == 3 else Intent.REQUEST
            results.append(await system.request(intent, f"question {i}", delta=delta, task_id=i))
        return setup, results, json.loads(json.dumps(system.client_ctx))
    finally:
        await system.close()


@pytest.fixture(scope="module")
def all_runs():
    return {name: run(drive(name)) for name in SYSTEMS}


def test_every_system_gives_identical_answers_and_context(all_runs):
    """Fairness check: same agent, same work, so the same results.

    If a system fed the agent a different context, the mock LLM's answers
    (which include a hash of the prompt) would differ.
    """
    ref_name = "jsonrpc"
    _, ref_results, ref_ctx = all_runs[ref_name]
    for name, (_, results, ctx) in all_runs.items():
        assert [r.content for r in results] == [r.content for r in ref_results], name
        assert [r.status for r in results] == [r.status for r in ref_results], name
        assert ctx == ref_ctx, name
    assert len(ref_ctx["hist"]) == 2 * ROUNDS
    assert ref_ctx["vars"]["status"] == "done"


def test_all_replies_ok(all_runs):
    for name, (_, results, _) in all_runs.items():
        assert all(r.status == ReplyStatus.OK for r in results), name


def total(results, setup=None):
    return sum(r.bytes_total for r in results) + (setup.bytes_total if setup else 0)


def test_expected_byte_ordering(all_runs):
    t = {name: total(res, setup) for name, (setup, res, _) in all_runs.items()}
    # delta beats full context, for both encodings
    assert t["sayonce"] < t["cbor-full"]
    assert t["json-delta"] < t["jsonrpc"]
    # binary beats JSON, for both context strategies
    assert t["cbor-full"] < t["jsonrpc"]
    assert t["sayonce"] < t["json-delta"]
    # compression helps the full-context baseline
    assert t["jsonrpc-gzip"] < t["jsonrpc"] and t["jsonrpc-zstd"] < t["jsonrpc"]
    # and after a few rounds SayOnce beats everything. (In the first 2-3 rounds a
    # compressed full-context baseline can win, because HELLO is not compressed.)
    assert t["sayonce"] == min(t.values())


def test_full_context_requests_grow_delta_requests_do_not(all_runs):
    for name in ("jsonrpc", "cbor-full"):
        sent = [r.bytes_sent for r in all_runs[name][1]]
        assert sent[-1] > sent[0], name  # history keeps growing
    for name in ("sayonce", "json-delta"):
        sent = [r.bytes_sent for r in all_runs[name][1]]
        assert max(sent) - min(sent) < 40, name  # roughly constant per round


def test_header_bytes_reported_for_http_only(all_runs):
    for name, (_, results, _) in all_runs.items():
        hb = sum(r.header_bytes for r in results)
        if name.startswith("json"):
            assert hb > 0, name
            assert all(r.header_bytes < r.bytes_total for r in results), name
        else:
            assert hb == 0, name


def test_info_is_reported_for_token_counting(all_runs):
    for name, (setup, results, _) in all_runs.items():
        for r in results:
            assert r.info_sent is not None and r.info_received is not None, name
            json.dumps(r.info_sent)  # must be renderable as JSON text
        if name in ("sayonce", "json-delta"):
            assert setup.info_sent is not None


def test_stateless_setup_costs_nothing(all_runs):
    assert all_runs["jsonrpc"][0].bytes_total == 0
    ctx, _ = sample_context(10)
    ctx_json = len(json.dumps(ctx, separators=(",", ":")))
    # SayOnce pays for the context once, up front, in its CBOR form ...
    raw = all_runs["sayonce-raw"][0].bytes_sent
    assert 0.5 * ctx_json < raw < ctx_json
    # ... and zstd-compressed, which makes that one-time cost a fraction of it
    assert all_runs["sayonce"][0].bytes_sent < 0.6 * raw


def test_delta_json_roundtrip():
    delta = [[DeltaOp.SET, ["vars", "x"], 1], [DeltaOp.DEL, ["vars", "y"]], [DeltaOp.APPEND, ["hist"], [1]]]
    assert delta_from_json(delta_to_json(delta)) == delta


def test_unknown_system():
    with pytest.raises(ValueError):
        make_system("nope")
