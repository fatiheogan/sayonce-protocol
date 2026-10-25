import asyncio
import csv

from sayonce.bench.analyze import build, crossover_round, load
from sayonce.bench.faults import COLUMNS as FAULT_COLUMNS
from sayonce.bench.faults import run_fault
from sayonce.bench.harness import COLUMNS, sweep
from sayonce.bench.netem import NetConditions
from sayonce.bench.systems import SYSTEMS

PRICES = {"in": 3.0, "cached": 0.3, "out": 15.0, "gb": 2.0}


def write(rows, path):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def test_build_report_and_figures(tmp_path):
    ideal = asyncio.run(sweep(list(SYSTEMS), [2, 5], 6, progress=False))
    net = asyncio.run(sweep(["jsonrpc", "sayonce"], [2], 3, progress=False,
                            networks=[NetConditions(name="ideal"), NetConditions(delay_ms=5, name="slow")]))
    write(ideal, tmp_path / "sweep.csv")
    write(net, tmp_path / "net.csv")

    faults = []
    for kind in ("none", "corrupt_msg", "drop_resume"):
        faults += asyncio.run(run_fault(kind, 2, 4, 2))
    with (tmp_path / "faults.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FAULT_COLUMNS)
        w.writeheader()
        w.writerows(faults)

    report = build(tmp_path / "sweep.csv", tmp_path / "out", tmp_path / "net.csv", PRICES, tmp_path / "faults.csv")
    text = report.read_text()
    assert "corrupt_msg" in text and "drop_resume" in text
    for section in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7."):
        assert section in text
    for fig in ("fig1_cumulative_bytes", "fig2_cumulative_wire_tokens", "fig3_ablation",
                "fig4_llm_tokens", "fig5_network_time"):
        assert (tmp_path / "out" / f"{fig}.png").stat().st_size > 10_000
        assert f"{fig}.png" in text
    assert "binary on top of delta" in text and "JSON-RPC / SayOnce" in text
    if ideal[0]["tokenizer"] != "o200k_base":
        assert "Preliminary" in text


def test_load_converts_numbers(tmp_path):
    rows = asyncio.run(sweep(["sayonce"], [2], 2, progress=False))
    write(rows, tmp_path / "s.csv")
    back = load(tmp_path / "s.csv")
    assert isinstance(back[0]["bytes_total"], int) and isinstance(back[1]["latency_ms"], float)
    assert back[0]["system"] == "sayonce"


def test_crossover_round():
    rows = []
    a = [10, 11, 12, 13]  # starts high, grows slowly
    b = [3, 8, 13, 18]  # starts low, grows fast
    for i, (x, y) in enumerate(zip(a, b)):
        rows.append({"system": "sayonce", "context_kb": 1, "repeat": 0, "round": i, "cum_bytes": x})
        rows.append({"system": "jsonrpc-gzip", "context_kb": 1, "repeat": 0, "round": i, "cum_bytes": y})
    assert crossover_round(rows, 1) == 2


def test_mean_ci():
    from sayonce.bench.analyze import mean_ci, t95

    m, h, n = mean_ci([10.0, 12.0, 14.0])
    assert (m, n) == (12.0, 3)
    assert abs(h - t95(2) * 2 / 3 ** 0.5) < 1e-9  # sd = 2
    assert mean_ci([5.0]) == (5.0, 0.0, 1)
    assert t95(1000) == 1.96 and t95(11) == t95(10)
