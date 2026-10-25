"""Turn harness CSVs into report figures and tables (step 9).

    python -m sayonce.bench.analyze results/sweep.csv --network-csv results/net.csv --out results/analysis

Writes PNG figures and analysis.md (tables) into --out. Every figure has a
matching table in analysis.md, so no number depends on reading a chart.

Prices used for the cost table are EXAMPLE values (flags --price-*). Set them
to the provider and data plan you want to discuss, and say so in the report.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# ------------------------------------------------------------------ style
# Categorical slots are fixed per system (colour follows the entity, never rank).
# Palette validated for CVD separation; contrast is relieved by direct labels
# and by the tables in analysis.md.
SERIES = {
    "sayonce":      {"color": "#2a78d6", "marker": "o", "label": "SayOnce"},
    "jsonrpc":      {"color": "#eb6834", "marker": "s", "label": "JSON-RPC"},
    "jsonrpc-gzip": {"color": "#1baf7a", "marker": "^", "label": "JSON-RPC+gzip"},
    "jsonrpc-zstd": {"color": "#eda100", "marker": "v", "label": "JSON-RPC+zstd"},
    "cbor-full":    {"color": "#e87ba4", "marker": "D", "label": "CBOR, no delta"},
    "json-delta":   {"color": "#008300", "marker": "P", "label": "JSON + delta"},
    "sayonce-raw":  {"color": "#6250d6", "marker": "X", "label": "SayOnce, no zstd"},
}
ORDER = ["jsonrpc", "jsonrpc-gzip", "jsonrpc-zstd", "cbor-full", "json-delta", "sayonce-raw", "sayonce"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#2b2b2a", "#6b6a64", "#e6e5e0"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "lines.linewidth": 2, "lines.markersize": 4, "axes.axisbelow": True,
})


def fmt_bytes(n: float) -> str:
    for unit, div in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= div:
            return f"{n / div:.3g} {unit}"
    return f"{n:.0f} B"


def fmt_num(n: float) -> str:
    for unit, div in (("M", 1e6), ("k", 1e3)):
        if n >= div:
            return f"{n / div:.3g}{unit}"
    return f"{n:.0f}"


# ------------------------------------------------------------------ data


def load(path: Path) -> list[dict]:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k in ("system", "workload", "network", "intent", "tokenizer"):
                continue
            try:
                r[k] = float(v) if "." in v or "e" in v else int(v)
            except (ValueError, TypeError):
                pass
    return rows


def present(rows: list[dict]) -> list[str]:
    have = {r["system"] for r in rows}
    return [s for s in ORDER if s in have]


def series(rows, system, kb, col, network=None, repeat=0):
    rs = [r for r in rows if r["system"] == system and r["context_kb"] == kb and r["repeat"] == repeat
          and (network is None or r["network"] == network)]
    rs.sort(key=lambda r: r["round"])
    return [r["round"] for r in rs], [r[col] for r in rs]


def at_round(rows, system, kb, col, rnd, network=None):
    xs, ys = series(rows, system, kb, col, network)
    return ys[xs.index(rnd)] if rnd in xs else None


# ------------------------------------------------------------------ figures


def _end_labels(ax, ends: list[tuple[float, str, str]], log: bool) -> None:
    """Direct labels at line ends, nudged apart so they never overlap."""
    if not ends:
        return
    tr = (lambda v: math.log10(max(v, 1e-9))) if log else (lambda v: v)
    inv = (lambda v: 10 ** v) if log else (lambda v: v)
    lo, hi = ax.get_ylim()
    span = tr(hi) - tr(lo)
    gap = span * 0.065
    items = sorted(((tr(y), text, color) for y, text, color in ends), key=lambda t: t[0])
    placed: list[float] = []
    for y, _, _ in items:
        placed.append(max(y, placed[-1] + gap) if placed else y)
    overflow = placed[-1] - (tr(hi) - gap * 0.3)  # shift down if pushed off the top
    if overflow > 0:
        placed = [p - overflow for p in placed]
    x = ax.get_xlim()[1]
    for (_, text, color), y in zip(items, placed):
        ax.annotate(text, xy=(x, inv(y)), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK, annotation_clip=False)
        ax.plot([x], [inv(y)], marker="s", markersize=5, color=color, clip_on=False)


def _shared_legend(fig, systems: list[str]) -> None:
    handles = [plt.Line2D([], [], color=SERIES[s]["color"], marker=SERIES[s]["marker"], markersize=5)
               for s in systems]
    fig.legend(handles, [SERIES[s]["label"] for s in systems], loc="upper left", bbox_to_anchor=(0.01, 0.95),
               ncol=len(systems), frameon=False, fontsize=8.5, handlelength=1.8, columnspacing=1.6)


def fig_cumulative(rows, col: str, ylabel: str, title: str, path: Path, systems: list[str],
                   network: str | None = None) -> None:
    """Small multiples, one per context size. Starts at round 1 (setup is included in the
    cumulative value); round 0 of stateless systems is 0 and cannot be drawn on a log axis."""
    kbs = sorted({r["context_kb"] for r in rows if network is None or r["network"] == network})
    fig, axes = plt.subplots(1, len(kbs), figsize=(3.3 * len(kbs), 3.6), squeeze=False)
    for ax, kb in zip(axes[0], kbs):
        for s in systems:
            xs, ys = series(rows, s, kb, col, network)
            pts = [(x, y) for x, y in zip(xs, ys) if x >= 1]
            if not pts:
                continue
            xs, ys = zip(*pts)
            st = SERIES[s]
            ax.plot(xs, ys, color=st["color"], marker=st["marker"], markevery=max(1, len(xs) // 6))
        ax.set_yscale("log")
        ax.set_xlim(left=1)
        ax.set_title(f"{kb} KB context", loc="left")
        ax.set_xlabel("round")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: fmt_bytes(v) if "bytes" in col else fmt_num(v)))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    axes[0][0].set_ylabel(ylabel)
    fig.suptitle(title, x=0.01, y=0.99, ha="left", fontweight="bold", fontsize=11)
    _shared_legend(fig, systems)
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    fig.savefig(path, dpi=200)
    plt.close(fig)


ABLATION_CELLS = [
    ("jsonrpc", "JSON / full"),
    ("cbor-full", "CBOR / full"),
    ("json-delta", "JSON / delta"),
    ("sayonce-raw", "CBOR / delta"),
    ("sayonce", "CBOR / delta + zstd"),
]


def fig_ablation(rows, rnd: int, path: Path) -> list[list]:
    """Ablation: encoding (JSON / CBOR) x context (full / delta), plus frame compression.

    Cumulative bytes at round rnd. The last row is the full protocol."""
    have = {r["system"] for r in rows}
    cells = [(s, lab) for s, lab in ABLATION_CELLS if s in have]
    kbs = sorted({r["context_kb"] for r in rows})
    fig, axes = plt.subplots(1, len(kbs), figsize=(3.4 * len(kbs) + 0.4, 0.5 * len(cells) + 1.0), squeeze=False)
    table = []
    labels = [lab for _, lab in cells]
    for i, (ax, kb) in enumerate(zip(axes[0], kbs)):
        vals = [at_round(rows, s, kb, "cum_bytes", rnd) or 0 for s, _ in cells]
        ypos = list(range(len(cells)))[::-1]  # first cell on top
        # Dot plot, not bars: bar length means nothing on a log axis.
        for y, v, (s, _) in zip(ypos, vals, cells):
            ax.plot([v], [y], marker="o", markersize=8, color=SERIES[s]["color"],
                    markeredgecolor=SURFACE, markeredgewidth=2, linestyle="none")
            ax.annotate(fmt_bytes(v), xy=(v, y), xytext=(8, 0), textcoords="offset points",
                        va="center", fontsize=8, color=INK)
        ax.set_xscale("log")
        ax.set_xlim(min(vals) / 2.5, max(vals) * 6)
        ax.set_ylim(-0.6, len(cells) - 0.4)
        ax.set_yticks(ypos, labels if i == 0 else [""] * len(cells))
        ax.set_title(f"{kb} KB context", loc="left")
        ax.grid(axis="y", visible=False)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt_bytes(v)))
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        table.append([kb, *vals])
    fig.suptitle(f"Ablation: cumulative bytes after {rnd} rounds (encoding / context strategy)", x=0.01, ha="left",
                 fontweight="bold", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return table


_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
        10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042}


def t95(df: int) -> float:
    """Two-sided 95% Student t critical value (normal approximation above 30)."""
    if df in _T95:
        return _T95[df]
    smaller = [k for k in _T95 if k < df]
    return 1.96 if df > 30 else _T95[max(smaller)]


def mean_ci(values: list[float]) -> tuple[float, float, int]:
    """(mean, half-width of the 95% confidence interval, n). Half-width is 0 for n < 2."""
    n = len(values)
    if n == 0:
        return float("nan"), 0.0, 0
    m = sum(values) / n
    if n < 2:
        return m, 0.0, n
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    return m, t95(n - 1) * math.sqrt(var / n), n


def total_times(rows, system, kb, network) -> list[float]:
    """Total wall time (setup + all rounds) in seconds, one value per repeat."""
    acc: dict[int, float] = defaultdict(float)
    for r in rows:
        if r["system"] == system and r["context_kb"] == kb and r["network"] == network:
            acc[r["repeat"]] += r["latency_ms"] / 1000
    return [acc[k] for k in sorted(acc)]


def total_time(rows, system, kb, network) -> float:
    return mean_ci(total_times(rows, system, kb, network))[0]


def fmt_ci(m: float, h: float, n: int, unit: str = "s") -> str:
    if n < 2:
        return f"{m:.3g} {unit}"
    return f"{m:.3g} ± {h:.2g} {unit}"


def fig_network(rows, path: Path) -> dict:
    """Small multiples: one row per context size, one column per link, linear y per panel.

    Links differ in scale by 1000x, so each panel has its own linear axis instead of
    one log axis (bar length is only meaningful on a linear axis from zero).
    """
    nets = list(dict.fromkeys(r["network"] for r in rows))
    kbs = sorted({r["context_kb"] for r in rows})
    systems = present(rows)
    out = {(kb, s): [mean_ci(total_times(rows, s, kb, n)) for n in nets] for kb in kbs for s in systems}
    fig, axes = plt.subplots(len(kbs), len(nets), figsize=(2.5 * len(nets), 2.3 * len(kbs) + 0.8), squeeze=False)
    for i, kb in enumerate(kbs):
        for j, net in enumerate(nets):
            ax = axes[i][j]
            stats = [out[(kb, s)][j] for s in systems]
            vals = [m for m, _, _ in stats]
            errs = [h for _, h, _ in stats]
            ax.bar(range(len(systems)), vals, color=[SERIES[s]["color"] for s in systems], width=0.78,
                   edgecolor=SURFACE, linewidth=2)
            if any(errs):
                ax.errorbar(range(len(systems)), vals, yerr=errs, fmt="none", ecolor=INK, elinewidth=1,
                            capsize=2.5, capthick=1)
            top = max(v + e for v, e in zip(vals, errs))
            for x, (v, e) in enumerate(zip(vals, errs)):
                ax.annotate(f"{v:.3g}", xy=(x, v + e), xytext=(0, 2),
                            textcoords="offset points", ha="center", va="bottom", fontsize=6.5, color=INK2)
            ax.set_ylim(0, top * 1.2)
            ax.set_xticks([])
            ax.grid(axis="x", visible=False)
            ax.set_title(f"{net}, {kb} KB", loc="left", fontsize=9)
            if j == 0:
                ax.set_ylabel("seconds")
    n_rounds = max(r["round"] for r in rows)
    reps = len({r["repeat"] for r in rows})
    ci = f", mean ± 95% CI of {reps} runs" if reps > 1 else ""
    fig.suptitle(f"Total time for setup + {n_rounds} rounds, by link{ci} (each panel has its own scale)",
                 x=0.01, y=0.995, ha="left", fontweight="bold", fontsize=11)
    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[s]["color"]) for s in systems]
    fig.legend(handles, [SERIES[s]["label"] for s in systems], loc="upper left",
               bbox_to_anchor=(0.01, 0.965), ncol=len(systems), frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return out


def fig_llm_tokens(rows, kb: int, path: Path) -> tuple[list, list, list]:
    # Not about protocols (identical in every system), so it uses colours no system owns.
    total_c, uncached_c = "#a8a79f", "#4a4944"  # neutral greys: no system owns these
    xs, prompt = series(rows, "sayonce", kb, "llm_prompt_tokens")
    _, uncached = series(rows, "sayonce", kb, "llm_uncached_tokens")
    cum_p, cum_u, a, b = [], [], 0, 0
    for p, u in zip(prompt, uncached):
        a += p
        b += u
        cum_p.append(a)
        cum_u.append(b)
    keep = [i for i, x in enumerate(xs) if x >= 1]
    px, pp, pu = [xs[i] for i in keep], [cum_p[i] for i in keep], [cum_u[i] for i in keep]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.plot(px, pp, color=total_c, marker="s", markevery=max(1, len(px) // 6))
    ax.plot(px, pu, color=uncached_c, marker="o", markevery=max(1, len(px) // 6))
    ax.set_yscale("log")
    ax.set_xlim(left=1)
    ax.set_xlabel("round")
    ax.set_ylabel("cumulative LLM input tokens")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt_num(v)))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    _end_labels(ax, [(pp[-1], "all prompt tokens", total_c),
                     (pu[-1], "not a repeated prefix", uncached_c)], log=True)
    fig.suptitle(f"What the worker's LLM reads, {kb} KB context", x=0.01, ha="left", fontweight="bold", fontsize=11)
    ax.set_title("identical for every protocol; the gap is what a prefix cache can serve",
                 loc="left", fontsize=8.5, fontweight="normal", color=INK2)
    fig.tight_layout(rect=(0, 0, 0.78, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return xs, cum_p, cum_u


# ------------------------------------------------------------------ tables


def md_table(header: list[str], rows: Iterable[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def crossover_round(rows, kb, a="sayonce", b="jsonrpc-gzip") -> int | None:
    """First round from which a's cumulative bytes stay below b's."""
    xa, ya = series(rows, a, kb, "cum_bytes")
    xb, yb = series(rows, b, kb, "cum_bytes")
    if not xa or not xb:
        return None
    first = None
    for r, va, vb in zip(xa, ya, yb):
        if va < vb:
            first = r if first is None else first
        else:
            first = None
    return first


def build(sweep: Path, out: Path, network_csv: Path | None, prices: dict,
          faults_csv: Path | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    rows = load(sweep)
    ideal = [r for r in rows if r.get("network", "ideal") == "ideal"] or rows
    systems = present(ideal)
    kbs = sorted({r["context_kb"] for r in ideal})
    R = max(r["round"] for r in ideal)
    marks = [n for n in (1, 5, 10, 20, 50, 100) if n <= R]
    tokenizer = ideal[0]["tokenizer"]
    md: list[str] = [f"# SayOnce benchmark analysis\n",
                     f"Source: `{sweep}` ({len(rows)} rows), tokenizer `{tokenizer}`, up to {R} rounds.",
                     ""]
    if tokenizer != "o200k_base":
        md += ["> **Preliminary:** token counts are approximate (tiktoken was not available). "
               "Re-run the harness with tiktoken before using token numbers in the report.\n"]

    # 1. cumulative bytes
    fig_cumulative(ideal, "cum_bytes", "cumulative bytes (log)",
                   "Bytes on the wire grow with every round unless only deltas are sent",
                   out / "fig1_cumulative_bytes.png", systems)
    md += ["## 1. Cumulative bytes on the wire\n", "![](fig1_cumulative_bytes.png)\n"]
    for kb in kbs:
        body = []
        for s in systems:
            body.append([SERIES[s]["label"], *[fmt_bytes(at_round(ideal, s, kb, "cum_bytes", n)) for n in marks]])
        ref = at_round(ideal, "jsonrpc", kb, "cum_bytes", R)
        so = at_round(ideal, "sayonce", kb, "cum_bytes", R)
        md += [f"**{kb} KB context**\n", md_table(["system", *[f"round {n}" for n in marks]], body), ""]
        if ref and so:
            line = f"After {R} rounds SayOnce sends {ref / so:.1f}x fewer bytes than JSON-RPC"
            gz = at_round(ideal, "jsonrpc-gzip", kb, "cum_bytes", R)
            if gz:
                line += f" and {gz / so:.1f}x fewer than JSON-RPC+gzip"
            cr = crossover_round(ideal, kb)
            if cr is not None and cr > 1:
                line += f"; it stays below gzip from round {cr} on (the uncompressed HELLO costs more at first)"
            md += [line + ".\n"]

    # header share
    hb = [[kb, f"{100 * sum(r['header_bytes'] for r in ideal if r['system'] == 'jsonrpc' and r['context_kb'] == kb) / max(1, at_round(ideal, 'jsonrpc', kb, 'cum_bytes', R)):.1f} %",
           f"{100 * sum(r['header_bytes'] for r in ideal if r['system'] == 'json-delta' and r['context_kb'] == kb) / max(1, at_round(ideal, 'json-delta', kb, 'cum_bytes', R)):.1f} %"]
          for kb in kbs if "json-delta" in systems and "jsonrpc" in systems]
    if hb:
        md += ["HTTP header share of all bytes:\n", md_table(["context", "JSON-RPC", "JSON + delta"], hb), ""]

    # 2. wire tokens
    tok_systems = [s for s in systems if s not in ("jsonrpc-gzip", "jsonrpc-zstd")]
    fig_cumulative(ideal, "cum_wire_tokens", "cumulative tokens (log)",
                   "Tokens of information exchanged between the agents",
                   out / "fig2_cumulative_wire_tokens.png", tok_systems)
    md += ["## 2. Tokens exchanged between the agents\n", "![](fig2_cumulative_wire_tokens.png)\n",
           "Tokens measure information, not encoding: compression does not change them (gzip/zstd "
           "are left out), and the CBOR full-context line lies on top of JSON-RPC because both "
           "carry the same information.\n"]
    for kb in kbs:
        body = [[SERIES[s]["label"], *[fmt_num(at_round(ideal, s, kb, "cum_wire_tokens", n)) for n in marks]]
                for s in tok_systems]
        md += [f"**{kb} KB context**\n", md_table(["system", *[f"round {n}" for n in marks]], body), ""]

    # 3. ablation
    if all(s in systems for s in ("jsonrpc", "cbor-full", "json-delta", "sayonce")):
        table = fig_ablation(ideal, R, out / "fig3_ablation.png")
        names = [s for s, _ in ABLATION_CELLS if s in systems]
        md += [f"## 3. Ablation: what does each idea contribute? ({R} rounds)\n", "![](fig3_ablation.png)\n"]
        body, factors = [], []
        for kb, *vals in table:
            v = dict(zip(names, vals))
            body.append([f"{kb} KB", *[fmt_bytes(x) for x in vals]])
            f = [f"{kb} KB", f"{v['jsonrpc'] / v['cbor-full']:.2f}x", f"{v['jsonrpc'] / v['json-delta']:.1f}x"]
            raw = v.get("sayonce-raw")
            if raw:
                f += [f"{v['json-delta'] / raw:.2f}x", f"{raw / v['sayonce']:.2f}x"]
            else:
                f += [f"{v['json-delta'] / v['sayonce']:.2f}x"]
            f.append(f"{v['jsonrpc'] / v['sayonce']:.1f}x")
            factors.append(f)
        md += [md_table(["context", *[lab for s, lab in ABLATION_CELLS if s in systems]], body), ""]
        fh = ["context", "binary alone", "delta alone", "binary on top of delta"]
        if "sayonce-raw" in systems:
            fh.append("zstd for large frames on top")
        fh.append("all together")
        md += ["Gain factors (bytes of the system before / after adding the idea):\n", md_table(fh, factors), "",
               "Delta is the main gain. Binary encoding alone saves little when the full context is "
               "sent (the context text dominates), but on top of delta it matters more, because the "
               "remaining messages are small and their JSON keys, framing and HTTP headers become "
               "a large share of each message. Compressing large frames mainly shrinks the one-time "
               "HELLO, so its share of the total falls as conversations get longer.\n"]

    # 4. LLM tokens
    kb_big = kbs[-1]
    xs, cum_p, cum_u = fig_llm_tokens(ideal, kb_big, out / "fig4_llm_tokens.png")
    md += [f"## 4. What the worker's LLM reads ({kb_big} KB context)\n", "![](fig4_llm_tokens.png)\n",
           "The worker renders the whole shared context as its prompt every round, in every system, "
           "so LLM input tokens are identical across protocols. What changes is how much of that "
           "prompt is a repeated prefix that a provider prefix cache can serve.\n",
           md_table(["", f"after {R} rounds"],
                    [["LLM input tokens", fmt_num(cum_p[-1])],
                     ["of which not a repeated prefix", fmt_num(cum_u[-1])],
                     ["cacheable share", f"{100 * (1 - cum_u[-1] / cum_p[-1]):.1f} %"]]), ""]

    # 5. cost per 1k conversations
    md += [f"## 5. Cost per 1,000 conversations of {R} rounds\n",
           f"Example prices (set with --price-*): input ${prices['in']}/M tokens, cached input "
           f"${prices['cached']}/M, output ${prices['out']}/M, data ${prices['gb']}/GB. "
           "**These are assumptions, not quotes.**\n"]
    for kb in kbs:
        llm = {k: sum(r[k] for r in ideal if r["system"] == "sayonce" and r["context_kb"] == kb)
               for k in ("llm_prompt_tokens", "llm_uncached_tokens", "llm_prefix_cached_tokens", "llm_output_tokens")}
        no_cache = (llm["llm_prompt_tokens"] * prices["in"] + llm["llm_output_tokens"] * prices["out"]) / 1e6 * 1000
        cached = (llm["llm_uncached_tokens"] * prices["in"] + llm["llm_prefix_cached_tokens"] * prices["cached"]
                  + llm["llm_output_tokens"] * prices["out"]) / 1e6 * 1000
        body = [[SERIES[s]["label"], f"${at_round(ideal, s, kb, 'cum_bytes', R) / 1e9 * prices['gb'] * 1000:,.2f}"]
                for s in systems]
        md += [f"**{kb} KB context**\n",
               md_table(["system", "data transfer cost"], body), "",
               md_table(["LLM cost (same for every system)", "per 1k conversations"],
                        [["prompt re-read every round, no cache", f"${no_cache:,.2f}"],
                         ["with prefix caching", f"${cached:,.2f}"]]), ""]
    md += ["LLM cost dominates data cost by orders of magnitude. The protocol's direct saving is in "
           "transfer (bytes, time on slow links). Its LLM-side contribution is indirect: a stable, "
           "versioned context makes prefix caching reliable.\n"]

    # 6. network
    if network_csv is not None and network_csv.exists():
        nrows = load(network_csv)
        times = fig_network(nrows, out / "fig5_network_time.png")
        nets = list(dict.fromkeys(r["network"] for r in nrows))
        nR = max(r["round"] for r in nrows)
        md += [f"## 6. Time over emulated links ({nR} rounds, setup included)\n", "![](fig5_network_time.png)\n"]
        reps = len({r["repeat"] for r in nrows})
        md += [f"Mean ± 95% confidence interval over {reps} runs (Student t). Bytes are deterministic; "
               "time varies with emulated loss and scheduling.\n" if reps > 1 else
               "Single run: re-run the harness with `--repeats 3` or more to get confidence intervals.\n"]
        for kb in sorted({k for k, _ in times}):
            body = [[SERIES[s]["label"], *[fmt_ci(*c) for c in times[(kb, s)]]] for s in present(nrows)]
            if (kb, "jsonrpc") in times and (kb, "sayonce") in times:
                body.append(["**JSON-RPC / SayOnce**", *[f"**{a[0] / b[0]:.1f}x**" if b[0] else "-"
                                                         for a, b in zip(times[(kb, "jsonrpc")], times[(kb, "sayonce")])]])
            md += [f"**{kb} KB context**\n", md_table(["system", *nets], body), ""]
        md += ["The slower the link, the larger the gain. Time savings come from delta; binary "
               "encoding changes little once messages are small.\n"]

    # 7. recovery cost
    if faults_csv is not None and faults_csv.exists():
        from .faults import summarize as summarize_faults

        frows = load(faults_csv)
        summ = summarize_faults(frows)
        fR = max(r["round"] for r in frows)
        every = sorted({r["round"] for r in frows if r["is_fault"]})
        md += [f"## 7. Cost of recovery (SayOnce, {fR} rounds, fault before rounds {every})\n",
               "Extra cost of one fault compared with the same round of a fault-free run. A RESYNC "
               "re-sends the whole context once (compressed); resuming a session the server still "
               "has costs only a new connection.\n"]
        for net in dict.fromkeys(r["network"] for r in summ):
            body = []
            for r in summ:
                if r["network"] != net or r["fault"] == "none":
                    continue
                body.append([r["fault"], f"{r['context_kb']} KB", fmt_bytes(r["setup_bytes"]),
                             fmt_bytes(max(0, r["extra_bytes_per_fault"])), f"{r['extra_ms_per_fault']:.1f} ms",
                             r["resyncs"]])
            md += [f"**{net}**\n", md_table(["fault", "context", "setup (HELLO)", "extra bytes / fault",
                                             "extra time / fault", "resyncs"], body), ""]
        md += ["Stateless baselines have no state to recover, but they also cannot detect a corrupted "
               "message: it simply produces a wrong answer. SayOnce detects it with the context hash.\n"]

    report = out / "analysis.md"
    report.write_text("\n".join(md))
    return report


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sweep", type=Path, help="CSV from the harness on an ideal network")
    p.add_argument("--network-csv", type=Path, help="CSV from a harness run with --network profiles")
    p.add_argument("--faults-csv", type=Path, help="CSV from python -m sayonce.bench.faults")
    p.add_argument("--out", type=Path, default=Path("results/analysis"))
    p.add_argument("--price-in", type=float, default=3.0, help="$ per million input tokens (example)")
    p.add_argument("--price-cached", type=float, default=0.30, help="$ per million cached input tokens (example)")
    p.add_argument("--price-out", type=float, default=15.0, help="$ per million output tokens (example)")
    p.add_argument("--price-gb", type=float, default=2.0, help="$ per GB transferred (example)")
    a = p.parse_args(argv)
    prices = {"in": a.price_in, "cached": a.price_cached, "out": a.price_out, "gb": a.price_gb}
    report = build(a.sweep, a.out, a.network_csv, prices, a.faults_csv)
    print(f"wrote {report} and figures in {a.out}")


if __name__ == "__main__":
    main()
