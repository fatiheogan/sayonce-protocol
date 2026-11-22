"""Figures and tables for the Sionna 5G NR experiment.

    python sionna_nr/analyze.py --dir results/sionna_nr

Reads bler.csv (link level), ue_links.csv + profiles.json (system level) and
net.csv + energy/energy.csv (SayOnce over the derived links), writes
fig_bler.png, fig_uplink_cdf.png, fig_time.png and summary.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sayonce.bench.analyze import SERIES  # noqa: E402

PROFILE_LABEL = {"nr-p10": "10th pct. UE", "nr-p50": "median UE", "nr-p90": "90th pct. UE"}
SYSTEMS = ["jsonrpc", "jsonrpc-gzip", "cbor-full", "json-delta", "sayonce"]


def fig_bler(d: Path) -> list[list]:
    curves = defaultdict(list)
    meta = {}
    with (d / "bler.csv").open() as f:
        for r in csv.DictReader(f):
            m = int(r["mcs"])
            curves[m].append((float(r["snr_db"]), float(r["tbler"])))
            meta[m] = (int(r["modulation_order"]), float(r["code_rate"]), float(r["spectral_efficiency"]))
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    cmap = plt.get_cmap("viridis")
    thresholds = []
    for i, m in enumerate(sorted(curves)):
        pts = sorted(curves[m])
        x = [p[0] for p in pts]
        y = [max(p[1], 1e-3) for p in pts]
        qm = {2: "QPSK", 4: "16QAM", 6: "64QAM"}[meta[m][0]]
        ax.semilogy(x, y, marker="o", markersize=3, color=cmap(i / max(1, len(curves) - 1)),
                    label=f"MCS {m} ({qm}, R={meta[m][1]:.2f})")
        # SNR at which the TBLER first reaches the 10 % target (log-linear interpolation)
        thr = None
        for (s0, b0), (s1, b1) in zip(pts, pts[1:]):
            if b0 > 0.1 >= b1:
                l0, l1 = np.log10(max(b0, 1e-4)), np.log10(max(b1, 1e-4))
                thr = s0 + (np.log10(0.1) - l0) / (l1 - l0) * (s1 - s0)
                break
        thresholds.append([m, qm, f"{meta[m][1]:.3f}", f"{meta[m][2]:.2f}",
                           f"{thr:.1f}" if thr is not None else "–"])
    ax.axhline(0.1, color="#888888", lw=0.8, ls="--")
    ax.text(ax.get_xlim()[0] + 0.3, 0.115, "10 % target", fontsize=7, color="#555555")
    ax.set_xlabel("SNR per resource element and receive antenna (dB)")
    ax.set_ylabel("transport block error rate")
    ax.set_ylim(1e-3, 1.05)
    ax.set_title("Sionna PHY: 5G NR PUSCH over TDL-C, 3 km/h, 2 RX antennas", fontsize=9)
    ax.legend(fontsize=6, ncol=2, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(d / "fig_bler.png", dpi=200)
    plt.close(fig)
    return thresholds


def fig_cdf(d: Path, profiles: dict) -> None:
    with (d / "ue_links.csv").open() as f:
        rates = np.array([float(r["uplink_mbps"]) for r in csv.DictReader(f)])
    served = np.sort(rates[rates > 0])
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.step(served, np.arange(1, len(served) + 1) / len(served), where="post", color="#2a78d6")
    ax.set_xscale("log")
    for name, p in profiles.items():
        ax.axvline(p["bandwidth_mbps"], color="#eb6834", lw=0.8, ls="--")
        ax.text(p["bandwidth_mbps"] * 1.08, 0.04 + 0.3 * ["nr-p10", "nr-p50", "nr-p90"].index(name),
                f"{PROFILE_LABEL[name]}\n{p['bandwidth_mbps']:.2f} Mbit/s", fontsize=7, color="#b04a1e")
    ax.set_xlabel("uplink goodput (Mbit/s, log scale)")
    ax.set_ylabel("CDF of served UEs")
    ax.set_title("Sionna SYS: phones in a 3GPP UMa cell, n78 100 MHz TDD (DDDSU)", fontsize=9)
    fig.tight_layout()
    fig.savefig(d / "fig_uplink_cdf.png", dpi=200)
    plt.close(fig)


def total_times(rows: list[dict]) -> dict:
    acc = defaultdict(lambda: defaultdict(float))
    for r in rows:
        acc[(r["network"], int(float(r["context_kb"])), r["system"])][int(r["repeat"])] += float(r["latency_ms"]) / 1000
    return {k: list(v.values()) for k, v in acc.items()}


def fig_time(d: Path, times: dict, nets: list[str], ctxs: list[int], rounds: int) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    width = 0.38
    for j, kb in enumerate(ctxs):
        ratios = [mean(times[(n, kb, "jsonrpc")]) / mean(times[(n, kb, "sayonce")]) for n in nets]
        xs = [i + (j - 0.5) * width for i in range(len(nets))]
        bars = ax.bar(xs, ratios, width=width * 0.95, color="#2a78d6" if kb == max(ctxs) else "#c4c2b8",
                      label=f"{kb} KB context")
        for b, r in zip(bars, ratios):
            ax.text(b.get_x() + b.get_width() / 2, r, f"{r:.1f}x", ha="center", va="bottom", fontsize=8)
    ax.axhline(1, color="#888888", lw=0.8, ls="--")
    ax.set_xticks(range(len(nets)), [PROFILE_LABEL.get(n, n) for n in nets])
    ax.set_ylabel("JSON-RPC time / SayOnce time")
    ax.set_title(f"{rounds}-round conversation over Sionna-derived 5G NR uplinks (mean of runs)", fontsize=9)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(d / "fig_time.png", dpi=200)
    plt.close(fig)


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dir", type=Path, default=Path("results/sionna_nr"))
    a = p.parse_args()
    d = a.dir
    prof = json.loads((d / "profiles.json").read_text())
    details = prof["profile_details"]
    thresholds = fig_bler(d)
    fig_cdf(d, details)

    with (d / "net.csv").open() as f:
        rows = list(csv.DictReader(f))
    times = total_times(rows)
    nets = [n for n in ("nr-p10", "nr-p50", "nr-p90") if any(k[0] == n for k in times)]
    ctxs = sorted({k[1] for k in times})
    rounds = max(int(r["round"]) for r in rows)
    fig_time(d, times, nets, ctxs, rounds)

    md = ["# SayOnce over a Sionna-simulated 5G NR uplink", "",
          f"Sionna {prof['sionna']}; generated by `sionna_nr/analyze.py`. Method and assumptions: "
          "`docs/sionna-5g.md`.", "",
          "## 1. Link level: PUSCH TBLER (Sionna PHY)", "",
          "SNR at which the first-transmission TBLER reaches 10 % (TDL-C, 300 ns, 3 km/h, 2 RX, LS estimation):", "",
          md_table(["MCS", "modulation", "code rate", "bits/symbol", "SNR @ 10 % TBLER (dB)"], thresholds), "",
          "![TBLER](fig_bler.png)", "",
          "## 2. System level: uplink goodput of phones in a UMa cell (Sionna SYS)", ""]
    st = prof["stats"]
    md += [f"{st['ues']} UEs, {st['indoor_share']:.0%} indoor; {st['outage']} UEs "
           f"({st['outage'] / st['ues']:.1%}) cannot reach the lowest simulated MCS and are in outage.", "",
           md_table(["percentile (served UEs)", *st["uplink_mbps_percentiles_served"].keys()],
                    [["uplink Mbit/s", *st["uplink_mbps_percentiles_served"].values()]]), "",
           "Link profiles given to the emulator:", "",
           md_table(["profile", "UE", "distance", "indoor", "path loss", "PRBs", "SNR", "MCS", "TBLER",
                     "rate (Mbit/s)", "one-way delay", "residual loss"],
                    [[PROFILE_LABEL[n], v["ue"], f"{v['distance_m']:.0f} m", "yes" if v["indoor"] else "no",
                      f"{v['pathloss_db']:.1f} dB", v["prb"], f"{v['snr_db']:.1f} dB", v["mcs"], v["tbler"],
                      v["bandwidth_mbps"], f"{v['delay_ms']} ms", v["loss"]] for n, v in details.items()]), "",
           "![uplink CDF](fig_uplink_cdf.png)", "",
           "## 3. SayOnce over these links", "",
           f"Total time of a {rounds}-round conversation (setup included), mean over repeats, in seconds:", ""]
    header = ["system"] + [f"{PROFILE_LABEL[n]}, {kb} KB" for kb in ctxs for n in nets]
    body = []
    for s in SYSTEMS:
        if not any(k[2] == s for k in times):
            continue
        body.append([SERIES[s]["label"]] + [f"{mean(times[(n, kb, s)]):.2f}" for kb in ctxs for n in nets])
    body.append(["**JSON-RPC / SayOnce**"] + [
        f"**{mean(times[(n, kb, 'jsonrpc')]) / mean(times[(n, kb, 'sayonce')]):.1f}x**" for kb in ctxs for n in nets])
    md += [md_table(header, body), "", "![time](fig_time.png)", ""]

    epath = d / "energy" / "energy.csv"
    if epath.exists():
        with epath.open() as f:
            er = list(csv.DictReader(f))
        ek = {(r["network"], int(r["context_kb"]), r["system"], float(r["gap_s"])): float(r["total_j"]) for r in er}
        gaps = sorted({k[3] for k in ek})
        md += ["## 4. Radio energy (LTE RRC parameters of Huang et al. 2012 applied to the NR link)", "",
               f"Energy saving of SayOnce against JSON-RPC per {rounds}-round session, {max(ctxs)} KB context:", "",
               md_table(["profile"] + [f"gap {g:g} s" for g in gaps],
                        [[PROFILE_LABEL[n]] + [
                            f"{1 - ek[(n, max(ctxs), 'sayonce', g)] / ek[(n, max(ctxs), 'jsonrpc', g)]:.0%}"
                            for g in gaps] for n in nets]), ""]
    (d / "summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
