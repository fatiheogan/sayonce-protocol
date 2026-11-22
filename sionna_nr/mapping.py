"""Pure helpers for the Sionna 5G NR experiment (no Sionna or PyTorch import, so CI can test them).

Assumptions of the system-level model, TBLER-curve interpolation and the mapping from
a UE's uplink (rate, TBLER) to the emulator's link profile (rate, delay, loss).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

ASSUMPTIONS = {
    "band": "n78 TDD, 3.5 GHz, 100 MHz, 30 kHz SCS (273 PRBs)",
    "tdd_pattern": "DDDSU: 1 uplink slot in 5 (uplink share 0.2, special slot not used for data)",
    "slot_s": 0.0005,
    "uplink_share": 0.2,
    "ue": "1 antenna, 1 layer, power class 3 (23 dBm)",
    "gnb_noise_figure_db": 5.0,
    "gnb_rx_antennas": 16,          # the 4x2 dual-polarised panel used in the UMa channel
    "link_level_rx_antennas": 2,    # antennas simulated in link_level.py
    "power_control": "open loop TS 38.213 (Sionna SYS), P0 = -90 dBm per PRB, alpha = 1",
    "scenario": "3GPP TR 38.901 UMa, single sector, ISD 500 m, 80 % indoor (O2I low-loss)",
    "interference": "none (single sector); the cell edge is therefore optimistic",
    "bler_target": 0.1,
    "harq_max_tx": 4,
    "core_one_way_delay_ms": 20.0,
    "harq_rtt_ms": 2.5,
    "candidate_prbs": [1, 2, 4, 8, 17, 34, 68, 136, 273],
}

def load_bler(path: Path) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """MCS -> (snr_db sorted, tbler)."""
    pts: dict[int, list[tuple[float, float]]] = defaultdict(list)
    with path.open() as f:
        for r in csv.DictReader(f):
            pts[int(r["mcs"])].append((float(r["snr_db"]), float(r["tbler"])))
    return {m: (np.array([s for s, _ in sorted(v)]), np.array([b for _, b in sorted(v)])) for m, v in pts.items()}


def tbler_at(curve: tuple[np.ndarray, np.ndarray], snr_db: np.ndarray) -> np.ndarray:
    """Interpolate log10(TBLER) linearly in SNR; 1 left of the curve, last value's trend to the right."""
    snr, bler = curve
    logb = np.log10(np.clip(bler, 1e-4, 1.0))
    out = np.interp(snr_db, snr, logb, left=0.0, right=logb[-1])
    return np.clip(10 ** out, 0.0, 1.0)


def link_profile(name: str, rate_bps: float, bler: float) -> dict:
    """Emulator parameters for one UE: rate, one-way delay, residual segment loss after HARQ."""
    harq = ASSUMPTIONS["harq_max_tx"]
    # Mean extra delay from HARQ retransmissions (geometric, capped at harq_max_tx transmissions)
    # plus waiting for the next uplink slot (half a TDD period on average).
    extra_tx = sum(bler ** k for k in range(1, harq))
    delay = ASSUMPTIONS["core_one_way_delay_ms"] + extra_tx * ASSUMPTIONS["harq_rtt_ms"] + 2.5 / 2
    residual = bler ** harq  # all HARQ transmissions failed; RLC/TCP must recover
    if rate_bps <= 0:
        raise ValueError("a UE in outage has no link profile (rate 0 would mean 'unlimited' in the emulator)")
    return {"name": name, "delay_ms": round(delay, 2), "loss": float(f"{residual:.2e}"),
            "bandwidth_mbps": max(round(rate_bps / 1e6, 4), 1e-4)}
