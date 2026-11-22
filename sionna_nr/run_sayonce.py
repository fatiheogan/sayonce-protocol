"""Run SayOnce and the baselines over the 5G NR uplink profiles derived with Sionna.

    python sionna_nr/run_sayonce.py --profiles results/sionna_nr/profiles.json \\
        --out results/sionna_nr/net.csv --repeats 5

Uses the same harness, workload and in-process emulator as Section 7 of the report
(``sayonce.bench.harness``, ``sayonce.bench.netem``); only the link profiles
(rate, one-way delay, residual loss after HARQ) come from the Sionna simulation.
The emulator applies one rate to both directions; the downlink of a real cell is
faster, but replies are a few hundred bytes in every system, so this hardly matters.

Radio energy uses the LTE parameters of Huang et al. (MobiSys 2012), because no
comparable measured 5G NR parameters are in the model; the numbers are marked so.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sayonce.bench import energy  # noqa: E402
from sayonce.bench.harness import sweep, write_csv  # noqa: E402
from sayonce.bench.netem import NetConditions  # noqa: E402

SYSTEMS = ["jsonrpc", "jsonrpc-gzip", "cbor-full", "json-delta", "sayonce"]


def load_profiles(path: Path, only: list[str] | None = None) -> list[NetConditions]:
    data = json.loads(path.read_text())
    return [NetConditions(delay_ms=p["delay_ms"], loss=p["loss"], bandwidth_mbps=p["bandwidth_mbps"], name=p["name"])
            for p in data["profiles"] if not only or p["name"] in only]


def merge(parts: list[Path], out: Path) -> None:
    """Concatenate harness CSVs of a run that was split into parallel parts."""
    import csv
    rows, fields = [], None
    for part in parts:
        with part.open() as f:
            r = csv.DictReader(f)
            fields = fields or r.fieldnames
            rows += list(r)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    metas = [json.loads(p.with_suffix(".meta.json").read_text()) for p in parts if p.with_suffix(".meta.json").exists()]
    out.with_suffix(".meta.json").write_text(json.dumps({"merged_from": [str(p) for p in parts], "parts": metas},
                                                        indent=2))


def write_energy(csv_path: Path, nets: list[str], gaps: list[float]) -> int:
    # Radio energy with the LTE parameters (no measured NR parameters in the model).
    import csv
    for n in nets:
        energy.NETWORK_RADIO[n] = "lte"
    erows = energy.table(energy.load_sessions(csv_path), gaps)
    for r in erows:
        r["radio"] = "LTE parameters (Huang 2012) on the NR link"
    edir = csv_path.parent / "energy"
    edir.mkdir(parents=True, exist_ok=True)
    with (edir / "energy.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(erows[0]))
        w.writeheader()
        w.writerows(erows)
    (edir / "energy.md").write_text(energy.markdown(erows))
    return len(erows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--profiles", type=Path, default=Path("results/sionna_nr/profiles.json"))
    p.add_argument("--out", type=Path, default=Path("results/sionna_nr/net.csv"))
    p.add_argument("--systems", nargs="+", default=SYSTEMS)
    p.add_argument("--context-kb", type=int, nargs="+", default=[10, 100])
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--workload", default="mcp")
    p.add_argument("--gaps", type=float, nargs="+", default=[0, 2, 5, 15])
    p.add_argument("--only", nargs="+", help="run only these profiles (e.g. nr-p10), to split a run into parts")
    p.add_argument("--no-energy", action="store_true", help="skip the energy step (for a part of a split run)")
    p.add_argument("--merge", type=Path, nargs="+",
                   help="instead of running: merge these part CSVs into --out and compute energy")
    a = p.parse_args()

    if a.merge:
        merge(a.merge, a.out)
        names = [n.name for n in load_profiles(a.profiles)]
        print(f"merged {len(a.merge)} parts into {a.out}; {write_energy(a.out, names, a.gaps)} energy rows")
        return

    nets = load_profiles(a.profiles, a.only)
    t0 = time.perf_counter()
    rows = asyncio.run(sweep(a.systems, a.context_kb, a.rounds, a.repeats, a.workload, seed=0, networks=nets))
    meta = {"args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
            "networks": [n.__dict__ for n in nets], "emulation": "in-process proxy (sayonce.bench.netem)",
            "link_profiles": "Sionna 5G NR uplink (sionna_nr/system_level.py)",
            "python": platform.python_version(), "platform": platform.platform(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "duration_s": round(time.perf_counter() - t0, 1)}
    write_csv(rows, a.out, meta)

    msg = f"wrote {len(rows)} rows to {a.out}"
    if not a.no_energy:
        msg += f" and {write_energy(a.out, [n.name for n in nets], a.gaps)} energy rows"
    print(msg)


if __name__ == "__main__":
    main()
