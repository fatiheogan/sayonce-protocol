import asyncio
import csv
import json

import pytest

from sayonce.bench.harness import COLUMNS, RunConfig, main, run_one, summary, sweep
from sayonce.bench.tokens import TokenCounter, _approx_tokens, to_text
from sayonce.bench.workload import travel_planning
from sayonce.messages import Intent

ROUNDS = 6


@pytest.fixture(scope="module")
def rows():
    return asyncio.run(sweep(["jsonrpc", "json-delta", "sayonce"], [5], ROUNDS, progress=False))


def by_system(rows, name):
    return [r for r in rows if r["system"] == name]


def test_row_shape(rows):
    assert len(rows) == 3 * (ROUNDS + 1)
    for r in rows:
        assert set(r) == set(COLUMNS)
    assert [r["round"] for r in by_system(rows, "sayonce")] == list(range(ROUNDS + 1))
    assert by_system(rows, "sayonce")[0]["intent"] == "SETUP"


def test_cumulative_columns_add_up(rows):
    for name in ("jsonrpc", "sayonce"):
        rs = by_system(rows, name)
        assert rs[-1]["cum_bytes"] == sum(r["bytes_total"] for r in rs)
        assert rs[-1]["cum_wire_tokens"] == sum(r["wire_tokens_total"] for r in rs)
        assert all(a["cum_bytes"] <= b["cum_bytes"] for a, b in zip(rs, rs[1:]))


def test_stateless_setup_is_free_stateful_is_not(rows):
    assert by_system(rows, "jsonrpc")[0]["bytes_total"] == 0
    assert by_system(rows, "sayonce")[0]["bytes_total"] > 1000
    assert by_system(rows, "sayonce")[0]["wire_tokens_total"] > 100


def test_llm_prompt_tokens_identical_across_systems(rows):
    """Same agent, same context: the worker's LLM reads the same prompt in every system."""
    ref = [r["llm_prompt_tokens"] for r in by_system(rows, "jsonrpc")]
    for name in ("json-delta", "sayonce"):
        assert [r["llm_prompt_tokens"] for r in by_system(rows, name)] == ref
    assert ref[1] > 0


def test_inform_rounds_do_not_call_the_llm(rows):
    for r in by_system(rows, "sayonce"):
        if r["intent"] == "INFORM":
            assert r["llm_prompt_tokens"] == 0


def test_prefix_cache_grows_with_history(rows):
    rs = [r for r in by_system(rows, "sayonce") if r["llm_prompt_tokens"] > 0]
    assert rs[0]["llm_prefix_cached_tokens"] == 0  # nothing cached before the first call
    for r in rs[1:]:
        assert 0 < r["llm_prefix_cached_tokens"] <= r["llm_prompt_tokens"]
        assert r["llm_uncached_tokens"] == r["llm_prompt_tokens"] - r["llm_prefix_cached_tokens"]


def test_delta_sends_fewer_wire_tokens(rows):
    full = by_system(rows, "jsonrpc")[-1]["cum_wire_tokens"]
    delta = by_system(rows, "sayonce")[-1]["cum_wire_tokens"]
    assert delta < full


def test_summary_table(rows):
    text = summary(rows, at_rounds=(1, ROUNDS))
    assert "sayonce" in text and f"bytes@{ROUNDS}" in text


def test_workload_is_reproducible():
    a, b = travel_planning(5, 10, seed=3), travel_planning(5, 10, seed=3)
    assert [r.content for r in a.rounds] == [r.content for r in b.rounds]
    assert a.context == b.context
    assert travel_planning(5, 10, seed=4).rounds[0].content != a.rounds[0].content
    assert [r.intent for r in a.rounds].count(Intent.INFORM) == 2


def test_cli_writes_csv_and_meta(tmp_path):
    out = tmp_path / "r.csv"
    main(["--systems", "sayonce", "jsonrpc", "--context-kb", "2", "--rounds", "3", "--out", str(out)])
    with out.open() as f:
        data = list(csv.DictReader(f))
    assert len(data) == 2 * 4
    meta = json.loads(out.with_suffix(".meta.json").read_text())
    assert meta["systems"] == ["sayonce", "jsonrpc"] and meta["tokenizer"] == data[0]["tokenizer"]


def test_run_one_single_system():
    rows = asyncio.run(run_one(RunConfig("cbor-full", 2, 2)))
    assert len(rows) == 3 and rows[0]["bytes_total"] > 0  # dictionary is sent on connect


# ------------------------------------------------------------------ tokens


def test_approx_counter_is_in_a_sensible_range():
    text = to_text({"sys": "You are a helpful travel planning agent.", "budget": 500})
    n = len(_approx_tokens(text))
    assert len(text) / 6 < n < len(text) / 2


def test_to_text_handles_bytes_and_enums():
    assert to_text({"h": b"\x01\x02", "i": Intent.REQUEST}) == '{"h":"0102","i":1}'


def test_common_prefix():
    c = TokenCounter()
    assert c.common_prefix("hello world foo", "hello world bar") >= 2
    assert c.common_prefix("abc", "xyz") == 0


def test_tiktoken_if_available():
    c = TokenCounter()
    if not c.exact:
        pytest.skip("tiktoken encoding not available offline")
    assert c.count("hello world") == 2
