"""Radio energy of a session on a phone, from harness CSVs (RRC state model).

    python -m sayonce.bench.energy results/final_mcp/net.csv --out results/final_mcp/energy

Bytes are not the whole story on a phone. The cellular radio has to be woken up
(RRC promotion) before it can send, and after the last packet it stays in a
high-power "tail" state for seconds in case more data comes. This module puts
each run of the harness through that state machine and reports the radio energy
per session, so the report can say how much of the byte saving turns into
battery saving.

Model (Huang et al., "A Close Examination of Performance and Power
Characteristics of 4G LTE Networks", MobiSys 2012, Tables 3 and 4):

* transfer: P = alpha_up * up_Mbps + alpha_down * down_Mbps + beta, so a round
  of duration d costs alpha_up * Mbit_up + alpha_down * Mbit_down + beta * d;
* promotion: P_promo for T_promo before the first round, and again whenever the
  radio went idle between rounds;
* tail: after each round the radio stays at P_tail; if the next round starts
  within T_tail it is still connected (tail energy for the gap, no promotion),
  otherwise it pays the full tail, goes idle, and the next round pays promotion.

``gap`` is the time between rounds (the agent / LLM thinking); the first
request follows the setup round (SayOnce HELLO, JSON-delta's first full
context) immediately. The harness sends
rounds back to back, so the gap is a parameter here, not a measurement. Idle
power is left out (it is the same for every system). EDGE has no parameters in
the paper; it uses the 3G values and is marked so in the table.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


@dataclass(frozen=True)
class Radio:
    name: str
    alpha_up: float     # mW per Mbps
    alpha_down: float   # mW per Mbps
    beta: float         # mW while transferring
    p_promo: float      # mW
    t_promo: float      # s
    p_tail: float       # mW
    t_tail: float       # s


# Huang et al., MobiSys 2012.
RADIOS = {
    "lte": Radio("LTE", 438.39, 51.97, 1288.04, 1210.7, 0.2601, 1060.0, 11.576),
    "3g": Radio("3G", 868.98, 122.12, 817.88, 659.4, 0.5821, 803.9, 8.088),
    "wifi": Radio("WiFi", 283.17, 137.01, 132.86, 124.4, 0.0791, 119.3, 0.238),
}
# Which radio a harness network profile runs on.
NETWORK_RADIO = {"4g": "lte", "3g": "3g", "edge": "3g", "wifi": "wifi", "lan": "wifi"}

SYSTEM_ORDER = ["jsonrpc", "jsonrpc-gzip", "jsonrpc-zstd", "cbor-full", "json-delta", "sayonce-raw", "sayonce"]


@dataclass
class Energy:
    transfer_mj: float = 0.0
    promo_mj: float = 0.0
    tail_mj: float = 0.0
    promotions: int = 0
    radio_on_s: float = 0.0

    @property
    def total_mj(self) -> float:
        return self.transfer_mj + self.promo_mj + self.tail_mj


def session_energy(rounds: list[tuple[int, int, float]], radio: Radio, gap_s: float) -> Energy:
    """rounds: (bytes_sent, bytes_received, latency_ms) in order, setup round included."""
    e = Energy()
    connected = False
    for i, (up, down, latency_ms) in enumerate(rounds):
        if up == 0 and down == 0:
            continue  # a setup step that sent nothing (JSON-RPC has no handshake)
        if not connected:
            e.promo_mj += radio.p_promo * radio.t_promo
            e.radio_on_s += radio.t_promo
            e.promotions += 1
        d = latency_ms / 1000
        e.transfer_mj += radio.alpha_up * up * 8 / 1e6 + radio.alpha_down * down * 8 / 1e6 + radio.beta * d
        e.radio_on_s += d
        last = all(u == 0 and r == 0 for u, r, _ in rounds[i + 1:])
        gap = 0.0 if i == 0 else gap_s  # the first request follows the setup at once
        if not last and gap < radio.t_tail:
            e.tail_mj += radio.p_tail * gap
            e.radio_on_s += gap
            connected = True
        else:
            e.tail_mj += radio.p_tail * radio.t_tail
            e.radio_on_s += radio.t_tail
            connected = False
    return e


def load_sessions(path: Path) -> dict[tuple, list[list[tuple[int, int, float]]]]:
    """(network, context_kb, system) -> one list of rounds per repeat."""
    runs: dict[tuple, dict[int, list[tuple[int, int, int, float]]]] = defaultdict(lambda: defaultdict(list))
    with path.open() as f:
        for r in csv.DictReader(f):
            key = (r["network"], int(float(r["context_kb"])), r["system"])
            runs[key][int(r["repeat"])].append(
                (int(r["round"]), int(r["bytes_sent"]), int(r["bytes_received"]), float(r["latency_ms"])))
    return {k: [[(u, d, lat) for _, u, d, lat in sorted(rs)] for rs in reps.values()] for k, reps in runs.items()}


def table(sessions, gaps: list[float]) -> list[dict]:
    rows = []
    for (network, ctx, system), reps in sessions.items():
        radio_key = NETWORK_RADIO.get(network)
        if radio_key is None:
            continue  # "ideal" and custom profiles have no radio
        radio = RADIOS[radio_key]
        for gap in gaps:
            es = [session_energy(r, radio, gap) for r in reps]
            rows.append({
                "network": network, "radio": radio.name + (" (3G values)" if network == "edge" else ""),
                "context_kb": ctx, "system": system, "gap_s": gap, "rounds": len(reps[0]) - 1,
                "total_j": mean(e.total_mj for e in es) / 1000,
                "transfer_j": mean(e.transfer_mj for e in es) / 1000,
                "overhead_j": mean(e.promo_mj + e.tail_mj for e in es) / 1000,
                "radio_on_s": mean(e.radio_on_s for e in es),
                "promotions": mean(e.promotions for e in es),
            })
    order = {s: i for i, s in enumerate(SYSTEM_ORDER)}
    rows.sort(key=lambda r: (r["network"], r["context_kb"], r["gap_s"], order.get(r["system"], 99)))
    return rows


def markdown(rows: list[dict]) -> str:
    out = ["# Radio energy per session (RRC model)", "",
           "Model and parameters: Huang et al., MobiSys 2012 (see `sayonce/bench/energy.py`).",
           "`gap` = time between rounds (agent thinking). Energy is for the whole session,",
           "including the setup round and the final tail. Idle power is not included.", ""]
    groups = defaultdict(list)
    for r in rows:
        groups[(r["network"], r["radio"], r["context_kb"], r["gap_s"])].append(r)
    for (network, radio, ctx, gap), rs in groups.items():
        base = next((r for r in rs if r["system"] == "jsonrpc"), None)
        out += [f"## {network} ({radio}), {ctx} KB context, {rs[0]['rounds']} rounds, gap {gap:g} s", "",
                "| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |",
                "|---|---|---|---|---|---|"]
        for r in rs:
            rel = f"{r['total_j'] / base['total_j'] - 1:+.0%}" if base and r is not base else "–"
            out.append(f"| {r['system']} | {r['total_j']:.2f} | {r['transfer_j']:.2f} | {r['overhead_j']:.2f} "
                       f"| {r['radio_on_s']:.1f} | {rel} |")
        out.append("")
    return "\n".join(out)


def figure(rows: list[dict], path: Path, network: str = "4g", ctx: int | None = None) -> bool:
    """Energy vs gap on one network; ctx defaults to the largest context measured."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from sayonce.bench.analyze import SERIES

    ctxs = [r["context_kb"] for r in rows if r["network"] == network]
    if ctx is None and ctxs:
        ctx = max(ctxs)
    sel = [r for r in rows if r["network"] == network and r["context_kb"] == ctx]
    if not sel:
        return False
    fig, ax = plt.subplots(figsize=(6, 3.4))
    for system in SYSTEM_ORDER:
        pts = sorted((r["gap_s"], r["total_j"]) for r in sel if r["system"] == system)
        if not pts:
            continue
        st = SERIES.get(system, {"color": "#888888", "marker": "o", "label": system})
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=st["color"], marker=st["marker"], label=st["label"])
    ax.set_xlabel("time between rounds (s)")
    ax.set_ylabel("radio energy per session (J)")
    ax.set_title(f"Radio energy, {network} ({sel[0]['radio']}), {ctx} KB context")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("csv", type=Path, help="harness CSV with --network profiles (e.g. results/final_mcp/net.csv)")
    p.add_argument("--gaps", type=float, nargs="+", default=[0, 2, 5, 15],
                   help="seconds between rounds to evaluate (default: 0 2 5 15)")
    p.add_argument("--out", type=Path, default=Path("results/energy"))
    a = p.parse_args(argv)

    rows = table(load_sessions(a.csv), a.gaps)
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "energy.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (a.out / "energy.md").write_text(markdown(rows))
    figure(rows, a.out / "fig_energy_gap.png")
    print(f"wrote {len(rows)} rows to {a.out}/energy.csv, energy.md")


if __name__ == "__main__":
    main()
