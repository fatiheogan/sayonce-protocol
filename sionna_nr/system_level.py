"""System level: uplink rate of phones in a 5G NR macro cell, with Sionna SYS and the link-level curves.

    python sionna_nr/system_level.py --bler results/sionna_nr/bler.csv --out results/sionna_nr

Steps:
  1. Drop UEs in one sector of a 3GPP TR 38.901 UMa cell (ISD 500 m, 80 % indoor,
     Sionna ``gen_single_sector_topology``) and generate their channels with
     Sionna's UMa model (path loss, shadow fading, O2I penetration, BS antenna pattern).
  2. Path loss per UE: Sionna SYS ``get_pathloss`` on the OFDM channel.
  3. For each candidate allocation (1 ... 273 PRBs): UE transmit power from Sionna SYS
     ``open_loop_uplink_power_control`` (TS 38.213 open loop, P0 = -90 dBm/PRB,
     alpha = 1, P_max = 23 dBm = power class 3), SNR per resource element at the gNB.
     The link-level curves were simulated with 2 receive antennas; the 16-element panel's
     extra array gain (10 log10(16/2) = 9 dB) is added, its extra diversity is not.
  4. Link adaptation with the link-level TBLER curves: pick the MCS with the highest
     goodput whose first-transmission TBLER is at most 10 % (the usual BLER target).
     The scheduler gives the UE the allocation with the highest goodput: a
     power-limited phone at the cell edge does better on fewer PRBs.
  5. Uplink goodput = TBS * (1 - TBLER) / slot * uplink share of the TDD pattern.
  6. Turn the 10th, 50th and 90th percentile UE into link profiles for the SayOnce
     network emulator (rate, one-way delay, residual loss after HARQ).

Assumptions are listed in ``ASSUMPTIONS`` and written next to the results.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sionna  # noqa: E402
import sionna.sys as sys_  # noqa: E402
from sionna.phy.channel import cir_to_ofdm_channel, gen_single_sector_topology, subcarrier_frequencies
from sionna.phy.channel.tr38901 import UMa, PanelArray
from sionna.phy.nr import PUSCHConfig

from mapping import ASSUMPTIONS, link_profile, load_bler, tbler_at  # noqa: E402

NOISE_DBM_HZ = -174.0
SCS_HZ = 30e3


_TBS_CACHE: dict[tuple[int, int], int] = {}


def tb_size(mcs: int, n_prb: int) -> int:
    """Transport block size (bits) of one PUSCH slot, from Sionna's 5G NR config (TS 38.214)."""
    key = (mcs, n_prb)
    if key not in _TBS_CACHE:
        c = PUSCHConfig()
        c.carrier.subcarrier_spacing = 30
        c.carrier.n_size_grid = n_prb
        c.num_antenna_ports = 1
        c.num_layers = 1
        c.tb.mcs_table = 1
        c.tb.mcs_index = mcs
        v = c.tb_size
        _TBS_CACHE[key] = int(v.item() if hasattr(v, "item") else v)
    return _TBS_CACHE[key]


def drop_ues(num_drops: int, ues_per_drop: int, fc: float, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Path loss (dB), 2D distance (m) and indoor flag per UE, from Sionna's UMa channel."""
    sionna.phy.config.seed = seed
    bs = PanelArray(num_rows_per_panel=4, num_cols_per_panel=2, polarization="dual", polarization_type="cross",
                    antenna_pattern="38.901", carrier_frequency=fc)
    ut = PanelArray(num_rows_per_panel=1, num_cols_per_panel=1, polarization="single", polarization_type="V",
                    antenna_pattern="omni", carrier_frequency=fc)
    channel = UMa(carrier_frequency=fc, o2i_model="low", ut_array=ut, bs_array=bs, direction="uplink")
    freqs = subcarrier_frequencies(12, SCS_HZ * 273)  # 12 frequency samples across the band
    pls, dists, indoor = [], [], []
    for _ in range(num_drops):
        topo = gen_single_sector_topology(batch_size=1, num_ut=ues_per_drop, scenario="uma")
        ut_loc, bs_loc, _, _, _, in_state = topo
        channel.set_topology(*topo)
        a, tau = channel(num_time_samples=1, sampling_frequency=1.0)[:2]
        h = cir_to_ofdm_channel(freqs, a, tau, normalize=False)
        pl_all, _ = sys_.get_pathloss(h)                       # [1, num_rx=1, num_ut, symbols]
        pls.append(10 * torch.log10(pl_all.reshape(-1)).numpy())
        dists.append(torch.linalg.norm(ut_loc[0, :, :2] - bs_loc[0, 0, :2], dim=-1).numpy())
        indoor.append(in_state[0].numpy().astype(bool))
    return np.concatenate(pls), np.concatenate(dists), np.concatenate(indoor)


def ue_power_dbm(pathloss_db: np.ndarray, n_prb: int) -> np.ndarray:
    """Sionna SYS open-loop uplink power control (TS 38.213 7.1.1) for an allocation of n_prb PRBs."""
    pl_lin = torch.tensor(10 ** (pathloss_db / 10), dtype=torch.float64)
    n_sc = torch.full_like(pl_lin, 12 * n_prb)
    p_w = sys_.open_loop_uplink_power_control(pl_lin, n_sc, alpha=1.0, p0_dbm=-90.0, ut_max_power_dbm=23.0,
                                              precision="double")
    return 10 * np.log10(p_w.numpy()) + 30  # W -> dBm


def link_adaptation(snr_db: np.ndarray, n_prb: int, curves) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Best MCS per UE with first-transmission TBLER <= target; returns (mcs, tbler, goodput bit/s)."""
    target = ASSUMPTIONS["bler_target"]
    share, slot = ASSUMPTIONS["uplink_share"], ASSUMPTIONS["slot_s"]
    best_mcs = np.full(snr_db.shape, -1)
    best_bler = np.ones(snr_db.shape)
    best_rate = np.zeros(snr_db.shape)
    for mcs, curve in sorted(curves.items()):
        b = tbler_at(curve, snr_db)
        rate = tb_size(mcs, n_prb) * (1 - b) / slot * share
        ok = (b <= target) & (rate > best_rate)
        best_mcs[ok], best_bler[ok], best_rate[ok] = mcs, b[ok], rate[ok]
    return best_mcs, best_bler, best_rate


def evaluate(pathloss_db: np.ndarray, curves) -> dict[str, np.ndarray]:
    noise_re = NOISE_DBM_HZ + 10 * math.log10(SCS_HZ) + ASSUMPTIONS["gnb_noise_figure_db"]
    best = {k: np.zeros(pathloss_db.shape) for k in ("rate", "snr", "bler", "power")}
    best["mcs"] = np.full(pathloss_db.shape, -1)
    best["prb"] = np.zeros(pathloss_db.shape, dtype=int)
    for n in ASSUMPTIONS["candidate_prbs"]:
        p = ue_power_dbm(pathloss_db, n)
        snr = p - 10 * math.log10(12 * n) - pathloss_db - noise_re  # per RE and receive antenna
        # The link-level curves use 2 receive antennas; the panel has 16. Add the extra array gain
        # (16/2 -> 9 dB), not the extra diversity, so the result stays on the conservative side.
        snr = snr + 10 * math.log10(ASSUMPTIONS["gnb_rx_antennas"] / ASSUMPTIONS["link_level_rx_antennas"])
        mcs, bler, rate = link_adaptation(snr, n, curves)
        better = rate > best["rate"]
        for k, v in (("rate", rate), ("snr", snr), ("bler", bler), ("power", p), ("mcs", mcs)):
            best[k][better] = v[better]
        best["prb"][better] = n
    return best


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bler", type=Path, default=Path("results/sionna_nr/bler.csv"))
    p.add_argument("--out", type=Path, default=Path("results/sionna_nr"))
    p.add_argument("--drops", type=int, default=40)
    p.add_argument("--ues-per-drop", type=int, default=50)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()

    curves = load_bler(a.bler)
    pl, dist, indoor = drop_ues(a.drops, a.ues_per_drop, 3.5e9, a.seed)
    best = evaluate(pl, curves)
    a.out.mkdir(parents=True, exist_ok=True)

    with (a.out / "ue_links.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ue", "distance_m", "indoor", "pathloss_db", "prb", "tx_power_dbm", "snr_db", "mcs",
                    "tbler", "uplink_mbps"])
        for i in range(len(pl)):
            w.writerow([i, round(float(dist[i]), 1), int(indoor[i]), round(float(pl[i]), 2), int(best["prb"][i]),
                        round(float(best["power"][i]), 2), round(float(best["snr"][i]), 2), int(best["mcs"][i]),
                        round(float(best["bler"][i]), 4), round(float(best["rate"][i]) / 1e6, 3)])

    rates = best["rate"]
    served = np.flatnonzero(rates > 0)  # UEs in outage cannot carry the session at all
    order = served[np.argsort(rates[served])]
    profiles, summary = [], {}
    for pct, name in ((10, "nr-p10"), (50, "nr-p50"), (90, "nr-p90")):
        idx = order[min(len(order) - 1, int(round(pct / 100 * (len(order) - 1))))]
        prof = link_profile(name, float(rates[idx]), float(best["bler"][idx]))
        profiles.append(prof)
        summary[name] = {"percentile": pct, "ue": int(idx), "distance_m": round(float(dist[idx]), 1),
                         "indoor": bool(indoor[idx]), "pathloss_db": round(float(pl[idx]), 1),
                         "prb": int(best["prb"][idx]), "snr_db": round(float(best["snr"][idx]), 1),
                         "mcs": int(best["mcs"][idx]), "tbler": round(float(best["bler"][idx]), 3), **prof}
    stats = {"ues": int(len(pl)), "outage": int((rates == 0).sum()),
             "note": "profile percentiles are taken over served UEs (uplink rate > 0)",
             "uplink_mbps_percentiles_served": {str(q): round(float(np.percentile(rates[served], q)) / 1e6, 2)
                                         for q in (5, 10, 25, 50, 75, 90, 95)},
             "indoor_share": round(float(indoor.mean()), 3)}
    meta = {"assumptions": ASSUMPTIONS, "stats": stats, "profile_details": summary,
            "sionna": sionna.__version__, "seed": a.seed, "drops": a.drops, "ues_per_drop": a.ues_per_drop}
    (a.out / "profiles.json").write_text(json.dumps({"profiles": profiles, **meta}, indent=2))
    print(json.dumps({"stats": stats, "profiles": summary}, indent=2))


if __name__ == "__main__":
    main()
