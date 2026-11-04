"""The "mcp" workload: contexts built from real MCP tool definitions."""

import asyncio
import json

import pytest

from sayonce.bench.faults import run_fault
from sayonce.bench.harness import sweep
from sayonce.bench.workload import WORKLOADS, _MCP_DATA, mcp_agent, mcp_context, mcp_tools
from sayonce.messages import Intent


def json_kb(obj) -> float:
    return len(json.dumps(obj, separators=(",", ":"))) / 1024


def test_data_file_has_real_servers():
    doc = json.loads(_MCP_DATA.read_text(encoding="utf-8"))
    assert len(doc["servers"]) >= 10
    for s in doc["servers"]:
        assert s["package"] and s["version"] and s["license"] and s["tools"]
        for t in s["tools"]:
            assert set(t) == {"name", "description", "inputSchema"}
            assert t["inputSchema"].get("type") == "object"
    names = [n for n, _ in mcp_tools()]
    assert len(names) == len(set(names)) > 200
    assert "filesystem__read_text_file" in names or "filesystem__read_file" in names


@pytest.mark.parametrize("kb", [1, 10, 50, 100])
def test_context_reaches_target_size(kb):
    ctx, dictionary = mcp_context(kb)
    size = json_kb({"sys": ctx["sys"], "tools": ctx["tools"]})
    assert kb <= size < kb + 30  # whole tools are added, so it can overshoot by one tool
    assert set(ctx) == {"sys", "tools", "hist", "vars"}
    assert set(ctx["tools"]) <= set(dictionary)


def test_larger_context_extends_smaller_one():
    small, _ = mcp_context(10)
    large, _ = mcp_context(100)
    assert list(large["tools"])[: len(small["tools"])] == list(small["tools"])


def test_too_large_context_is_rejected():
    with pytest.raises(ValueError):
        mcp_context(10_000)


def test_workload_is_reproducible_and_registered():
    assert WORKLOADS["mcp"] is mcp_agent
    a, b = mcp_agent(10, 10, seed=3), mcp_agent(10, 10, seed=3)
    assert [r.content for r in a.rounds] == [r.content for r in b.rounds]
    assert [r.delta for r in a.rounds] == [r.delta for r in b.rounds]
    assert [r.intent for r in a.rounds].count(Intent.INFORM) == 2
    assert a.name == "mcp"


def test_all_systems_run_on_real_tools():
    rows = asyncio.run(sweep(["jsonrpc", "jsonrpc-gzip", "cbor-full", "json-delta", "sayonce"], [10], 5,
                             workload="mcp", progress=False))
    last = {r["system"]: r for r in rows if r["round"] == 5}
    assert set(last) == {"jsonrpc", "jsonrpc-gzip", "cbor-full", "json-delta", "sayonce"}
    assert all(r["workload"] == "mcp" for r in rows)
    # The worker's LLM reads the same prompt whatever the protocol.
    assert len({r["llm_prompt_tokens"] for r in last.values()}) == 1
    assert last["sayonce"]["cum_bytes"] < last["jsonrpc-gzip"]["cum_bytes"] < last["jsonrpc"]["cum_bytes"]


def test_faults_accept_the_workload():
    rows = asyncio.run(run_fault("server_restart", 10, 12, 5, workload="mcp"))
    assert rows[-1]["round"] == 12
    assert sum(r["resyncs"] for r in rows) >= 1
