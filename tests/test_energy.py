import csv

import pytest

from sayonce.bench.energy import RADIOS, load_sessions, main, session_energy

LTE = RADIOS["lte"]


def test_single_round_pays_promotion_transfer_and_full_tail():
    e = session_energy([(1_000_000, 0, 1000.0)], LTE, gap_s=5)
    assert e.promotions == 1
    assert e.promo_mj == pytest.approx(LTE.p_promo * LTE.t_promo)
    # 8 Mbit up in 1 s: alpha_up * 8 + beta * 1
    assert e.transfer_mj == pytest.approx(LTE.alpha_up * 8 + LTE.beta)
    assert e.tail_mj == pytest.approx(LTE.p_tail * LTE.t_tail)


def test_short_gap_keeps_radio_connected_long_gap_promotes_again():
    rounds = [(100, 100, 10.0)] * 3
    short = session_energy(rounds, LTE, gap_s=1)
    long = session_energy(rounds, LTE, gap_s=LTE.t_tail + 1)
    assert short.promotions == 1
    assert long.promotions == 2  # rounds 1 and 2; round 0 -> 1 has no gap
    assert long.total_mj > short.total_mj


def test_empty_setup_round_is_skipped_and_setup_has_no_gap():
    with_setup = [(0, 0, 1.0), (100, 100, 10.0), (100, 100, 10.0)]
    assert session_energy(with_setup, LTE, gap_s=30).promotions == 2
    hello_first = [(5000, 40, 20.0), (100, 100, 10.0)]
    assert session_energy(hello_first, LTE, gap_s=30).promotions == 1


def test_fewer_bytes_never_cost_more_energy():
    big = session_energy([(100_000, 500, 100.0)] * 5, LTE, gap_s=2)
    small = session_energy([(200, 250, 60.0)] * 5, LTE, gap_s=2)
    assert small.total_mj < big.total_mj


def test_main_writes_report(tmp_path):
    src = tmp_path / "net.csv"
    fields = ["system", "context_kb", "network", "repeat", "round", "bytes_sent", "bytes_received", "latency_ms"]
    with src.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for system, up in (("jsonrpc", 50_000), ("sayonce", 300)):
            for rnd in range(4):
                w.writerow({"system": system, "context_kb": 10, "network": "4g", "repeat": 0, "round": rnd,
                            "bytes_sent": 0 if rnd == 0 and system == "jsonrpc" else up,
                            "bytes_received": 200, "latency_ms": 80})
            w.writerow({"system": system, "context_kb": 10, "network": "ideal", "repeat": 0, "round": 1,
                        "bytes_sent": up, "bytes_received": 200, "latency_ms": 1})
    assert len(load_sessions(src)) == 4
    main([str(src), "--gaps", "0", "5", "--out", str(tmp_path / "out")])
    md = (tmp_path / "out" / "energy.md").read_text()
    assert "4g (LTE), 10 KB context" in md and "ideal" not in md
    assert (tmp_path / "out" / "fig_energy_gap.png").exists()
