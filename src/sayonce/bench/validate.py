"""Compare total conversation time across measurement methods.

Each argument is LABEL=CSV (a glob may match several CSVs), for example the
in-process emulator, kernel tc netem and a real phone hotspot:

    python -m sayonce.bench.validate emulator='results/real/emu_*.csv' \\
        netem='results/real/netem_*.csv' hotspot=results/real/hotspot-4g.csv \\
        --out results/real/validation.md

For every (network, context size, system) it reports the median total time of
one conversation (setup plus all rounds) over the repeats, and how many times
longer JSON-RPC takes than SayOnce. When two methods measured the same network,
the table puts them side by side with the relative difference.
"""

from __future__ import annotations

import argparse
import csv
import glob
import statistics
from collections import defaultdict
from pathlib import Path

ORDER = ["jsonrpc", "jsonrpc-gzip", "jsonrpc-zstd", "cbor-full", "json-delta", "sayonce-raw", "sayonce"]


def load(paths: list[str]) -> dict[tuple[str, int, str], list[float]]:
    """(network, context_kb, system) -> total seconds per repeat."""
    totals: dict[tuple[str, int, str, int], float] = defaultdict(float)
    for path in paths:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                key = (r["network"], int(r["context_kb"]), r["system"], int(r["repeat"]))
                totals[key] += float(r["latency_ms"]) / 1000
    out: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    for (net, kb, system, _), t in sorted(totals.items()):
        out[(net, kb, system)].append(t)
    return out


def fmt(xs: list[float] | None) -> str:
    if not xs:
        return "-"
    med = statistics.median(xs)
    return f"{med:.2f} s" if len(xs) == 1 else f"{med:.2f} s ({min(xs):.2f}-{max(xs):.2f})"


def report(sources: dict[str, dict]) -> str:
    labels = list(sources)
    nets = sorted({k[0] for d in sources.values() for k in d})
    lines = ["# Network validation", "",
             "Median total time of one conversation (setup + all rounds) over the repeats, "
             "with the range in brackets. Lower is better.", ""]
    for net in nets:
        kbs = sorted({k[1] for d in sources.values() for k in d if k[0] == net})
        for kb in kbs:
            systems = sorted({k[2] for d in sources.values() for k in d if k[:2] == (net, kb)},
                             key=lambda s: ORDER.index(s) if s in ORDER else 99)
            present = [lb for lb in labels if any(k[:2] == (net, kb) for k in sources[lb])]
            lines += [f"## {net}, {kb} KB context", ""]
            head = "| system | " + " | ".join(present) + (" | difference |" if len(present) == 2 else " |")
            lines += [head, "|---" * (len(present) + 1 + (len(present) == 2)) + "|"]
            for s in systems:
                vals = [sources[lb].get((net, kb, s)) for lb in present]
                row = f"| {s} | " + " | ".join(fmt(v) for v in vals)
                if len(present) == 2:
                    a, b = vals
                    diff = (statistics.median(b) / statistics.median(a) - 1) * 100 if a and b else None
                    row += f" | {diff:+.0f}%" if diff is not None else " | -"
                lines.append(row + " |")
            ratios = []
            for lb in present:
                j, so = sources[lb].get((net, kb, "jsonrpc")), sources[lb].get((net, kb, "sayonce"))
                if j and so:
                    ratios.append(f"{lb}: {statistics.median(j) / statistics.median(so):.1f}x")
            if ratios:
                lines += ["", "JSON-RPC takes longer than SayOnce by " + ", ".join(ratios) + "."]
            lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sources", nargs="+", help="LABEL=CSV_OR_GLOB")
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    sources = {}
    for spec in a.sources:
        label, _, pattern = spec.partition("=")
        paths = sorted(glob.glob(pattern))
        if not label or not paths:
            raise SystemExit(f"no CSV matches {spec!r} (expected LABEL=CSV_OR_GLOB)")
        sources[label] = load(paths)
    text = report(sources)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n")
        print(f"wrote {a.out}")
    print(text)


if __name__ == "__main__":
    main()
