"""Two-computer benchmark mode (run here over loopback) and the validation report."""

import asyncio

from sayonce.bench.harness import write_csv
from sayonce.bench.remote import RemoteServer, run
from sayonce.bench.validate import load, main as validate_main, report

SYSTEMS = ["jsonrpc", "sayonce"]


def remote_rows(rounds=4):
    async def go():
        server = await RemoteServer(0, SYSTEMS, "127.0.0.1").start()
        try:
            return await run("127.0.0.1", server.port, "loop", SYSTEMS, [10], rounds, 2, "mcp")
        finally:
            await server.close()
    return asyncio.run(go())


def test_remote_run_matches_local_bytes():
    from sayonce.bench.harness import sweep

    rows, meta = remote_rows()
    assert len(meta["rtt_ms_before"]) == 10 and meta["label"] == "loop"
    assert {r["network"] for r in rows} == {"loop"}
    assert len(rows) == len(SYSTEMS) * 2 * 5
    local = asyncio.run(sweep(SYSTEMS, [10], 4, workload="mcp", progress=False))
    for name in SYSTEMS:
        rem = [r for r in rows if r["system"] == name and r["repeat"] == 0]
        loc = [r for r in local if r["system"] == name]
        # Same messages over the same protocol: setup bytes are identical, rounds within a few bytes.
        assert rem[0]["bytes_total"] == loc[0]["bytes_total"]
        assert abs(rem[-1]["cum_bytes"] - loc[-1]["cum_bytes"]) <= 4 * 8
        assert all(r["llm_prompt_tokens"] == 0 for r in rem)


def test_unknown_system_on_server_is_reported():
    async def go():
        server = await RemoteServer(0, ["sayonce"], "127.0.0.1").start()
        try:
            await run("127.0.0.1", server.port, "loop", ["jsonrpc"], [1], 1, 1, "mcp")
        finally:
            await server.close()
    try:
        asyncio.run(go())
    except SystemExit as e:
        assert "jsonrpc" in str(e)
    else:
        raise AssertionError("expected SystemExit")


def test_validation_report(tmp_path):
    rows, meta = remote_rows(rounds=2)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_csv(rows, a, meta)
    for r in rows:
        r["latency_ms"] = float(r["latency_ms"]) * 2
    write_csv(rows, b, meta)
    text = report({"first": load([str(a)]), "second": load([str(b)])})
    assert "## loop, 10 KB context" in text
    assert "| sayonce |" in text and "+100%" in text
    assert "JSON-RPC takes longer than SayOnce by first:" in text
    out = tmp_path / "v.md"
    validate_main([f"first={a}", f"second={tmp_path}/b*.csv", "--out", str(out)])
    assert out.read_text().startswith("# Network validation")
