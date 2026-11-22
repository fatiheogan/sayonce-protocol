"""Link level: 5G NR PUSCH transport-block error rate (TBLER) vs SNR, simulated with Sionna PHY.

    python sionna_nr/link_level.py --out results/sionna_nr/bler.csv

For each MCS (TS 38.214 table 1, up to 64-QAM) the script sends batches of
complete PUSCH slots through a 3GPP TDL channel and counts transport blocks
whose CRC fails. Everything in the chain is Sionna's 5G NR implementation:
TB segmentation and CRC, 5G LDPC encoding/decoding, rate matching, QAM mapping,
DMRS pilots, OFDM resource grid, LS channel estimation and LMMSE equalisation.

Simulation setup (assumptions, see docs/sionna-5g.md):
  * band n78, carrier 3.5 GHz, 30 kHz subcarrier spacing
  * one UE antenna, one layer, no transform precoding (CP-OFDM)
  * gNB with 2 receive antennas
  * channel: TDL-C (NLOS), delay spread 300 ns, UE speed 3 km/h
  * 16 PRBs are simulated to keep the run short on a CPU; the TBLER of an MCS
    depends on the code rate and modulation, much less on the allocation size

The SNR is the average received SNR per resource element and receive antenna
(unit-power channel, noise variance no = 10^(-SNR/10)). For each MCS the SNR is
stepped in 1 dB steps from just below the expected waterfall until the TBLER
falls under 1 %, so the run only spends time where the curve changes.
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path

import torch

import sionna
from sionna.phy.channel import OFDMChannel
from sionna.phy.channel.tr38901 import TDL
from sionna.phy.nr import PUSCHConfig, PUSCHReceiver, PUSCHTransmitter

MCS_INDICES = [3, 6, 9, 11, 14, 17, 20, 24, 27]  # MCS 0-2: code rate < 1/5, below the LDPC encoder's range


def make_config(mcs: int, n_prb: int) -> PUSCHConfig:
    c = PUSCHConfig()
    c.carrier.subcarrier_spacing = 30
    c.carrier.n_size_grid = n_prb
    c.num_antenna_ports = 1
    c.num_layers = 1
    c.tb.mcs_table = 1
    c.tb.mcs_index = mcs
    return c


def _f(v) -> float:
    return float(v.item()) if hasattr(v, "item") else float(v)


def spectral_efficiency(c: PUSCHConfig) -> float:
    return _f(c.tb.num_bits_per_symbol) * _f(c.tb.target_coderate)


def simulate_mcs(mcs: int, args, writer, f) -> None:
    c = make_config(mcs, args.prb)
    tx = PUSCHTransmitter(c)
    rx = PUSCHReceiver(tx, return_tb_crc_status=True)
    tdl = TDL("C", delay_spread=args.delay_spread_ns * 1e-9, carrier_frequency=args.fc_ghz * 1e9,
              min_speed=args.speed_kmh / 3.6, max_speed=args.speed_kmh / 3.6, num_rx_ant=args.rx_ant)
    channel = OFDMChannel(tdl, tx.resource_grid)
    se = spectral_efficiency(c)
    # AWGN Shannon SNR for this spectral efficiency; the fading waterfall lies a few dB around it.
    snr = math.floor(10 * math.log10(2 ** se - 1)) + args.snr_offset
    seen_high = False
    while snr <= 40:
        errors = blocks = 0
        t0 = time.time()
        while blocks < args.max_blocks:
            no = torch.tensor(10 ** (-snr / 10))
            x, _ = tx(args.batch)
            y = channel(x, no)
            _, crc = rx(y, no)
            errors += int((~crc.bool()).sum())
            blocks += crc.numel()
            if errors >= args.min_errors and blocks >= args.batch:
                break
        bler = errors / blocks
        writer.writerow({"mcs": mcs, "modulation_order": int(_f(c.tb.num_bits_per_symbol)),
                         "code_rate": round(_f(c.tb.target_coderate), 4), "spectral_efficiency": round(se, 4),
                         "tb_size_sim": int(_f(c.tb_size)), "snr_db": snr, "blocks": blocks, "errors": errors,
                         "tbler": round(bler, 5)})
        f.flush()
        print(f"MCS {mcs:2d}  SNR {snr:5.1f} dB  TBLER {bler:.3f}  ({errors}/{blocks}, {time.time() - t0:.0f}s)",
              flush=True)
        if bler > 0.9 and not seen_high:
            snr += 2  # still left of the waterfall: move faster
            continue
        seen_high = True
        if bler < 0.01:
            break
        snr += 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", type=Path, default=Path("results/sionna_nr/bler.csv"))
    p.add_argument("--mcs", type=int, nargs="+", default=MCS_INDICES)
    p.add_argument("--prb", type=int, default=16)
    p.add_argument("--rx-ant", type=int, default=2)
    p.add_argument("--fc-ghz", type=float, default=3.5)
    p.add_argument("--delay-spread-ns", type=float, default=300)
    p.add_argument("--speed-kmh", type=float, default=3)
    p.add_argument("--batch", type=int, default=100)
    p.add_argument("--max-blocks", type=int, default=200, help="transport blocks per SNR point at most")
    p.add_argument("--min-errors", type=int, default=50, help="stop a point early once this many errors")
    p.add_argument("--snr-offset", type=int, default=-3,
                   help="first SNR point relative to the AWGN Shannon SNR of the MCS (dB)")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    sionna.phy.config.seed = args.seed
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mcs", "modulation_order", "code_rate", "spectral_efficiency",
                                          "tb_size_sim", "snr_db", "blocks", "errors", "tbler"])
        w.writeheader()
        for mcs in args.mcs:
            simulate_mcs(mcs, args, w, f)
    print(f"wrote {args.out}  (sionna {sionna.__version__}, torch {torch.__version__})")


if __name__ == "__main__":
    main()
