# Benchmarks

## Systems compared

All systems live in `src/sayonce/bench/systems.py` behind one interface
(`start`, `open`, `request`, `close`) and run the **same** agent
(`WorkerAgent` with the deterministic mock LLM). A test checks that every
system produces identical answers and the identical final context, so the
only difference between them is what goes over the wire.

| Name | Spec ID | Encoding | Transport | Context per round |
|---|---|---|---|---|
| `jsonrpc` | B1 | JSON-RPC (compact) | HTTP/1.1 keep-alive | full |
| `jsonrpc-gzip` | B2 | JSON-RPC + gzip | HTTP/1.1 keep-alive | full |
| `jsonrpc-zstd` | B2 | JSON-RPC + zstd | HTTP/1.1 keep-alive | full |
| `cbor-full` | B3 | CBOR + dictionary | TCP | full |
| `json-delta` | B4 | JSON-RPC (compact) | HTTP/1.1 keep-alive | delta |
| `sayonce` | S | CBOR + dictionary | TCP | delta |

Notes on fairness:

- JSON is compact (no spaces) and HTTP connections are kept alive: the
  favourable case for the baselines.
- HTTP header bytes are counted, and also reported separately
  (`RoundResult.header_bytes`) so results can be shown with and without them.
- The stateless baselines have no setup cost; SayOnce and `json-delta` pay
  for the context once in their setup message.
- `sample_context()` generates varied text from a seeded vocabulary. It
  compresses about 3x like real JSON. (An earlier version used repeated
  filler that compressed 25x, which made the compressed baselines look
  unrealistically good.)

## Workloads

Every system receives exactly the same workload (`--workload`):

| workload | context | messages |
|---|---|---|
| `travel` (default) | generated: a short system prompt and tool definitions written from a seeded vocabulary | generated travel-planning requests |
| `mcp` | **real**: a coding-agent system prompt and the tool definitions of 12 public MCP servers (225 tools, 287 KB) | hand-written software-engineering requests that use those tools |

The `mcp` tools were captured with `scripts/capture_mcp_tools.py`, which
starts each server and stores its `tools/list` answer (name, description and
input schema, exactly what an agent passes to its LLM). The servers, their
versions and licences are listed in `src/sayonce/bench/data/mcp_tools.json`:
time, fetch, filesystem, git, sequential-thinking, memory, context7,
playwright, sentry, notion, firecrawl and atlassian. A context of N KB holds
the system prompt plus the tools in that order until it reaches N KB, so a
small context looks like a minimal developer setup and a large one like an
agent with many integrations. Both workloads have the same shape: every 5th
round is an INFORM, and every round changes one shared variable.

Real tool definitions are JSON schemas with many repeated keys, so they
compress better than the generated text (gzip: about 5-6x instead of 3x). That
makes the compressed baselines stronger, which is why the `mcp` workload is
the fairer test. Results: `results/final_mcp/`.

## First observations (localhost, mock LLM)

Cumulative bytes, both directions:

| Context | Rounds | jsonrpc | jsonrpc-gzip | cbor-full | json-delta | sayonce |
|---|---|---|---|---|---|---|
| 10 KB | 1 | 11.4 KB | 4.6 KB | 9.8 KB | 12.1 KB | 9.9 KB |
| 10 KB | 50 | 887 KB | 324 KB | 764 KB | 64 KB | 24 KB |
| 100 KB | 1 | 103 KB | 31 KB | 93 KB | 104 KB | 93 KB |
| 100 KB | 50 | 5.49 MB | 1.63 MB | 4.81 MB | 156 KB | 107 KB |

- Full-context systems grow with every round; delta systems stay nearly flat.
- Delta is the main gain; binary encoding adds a smaller gain on top.
- In the **first 2-3 rounds** a compressed full-context baseline sends fewer
  bytes than SayOnce, because the SayOnce HELLO is not compressed. Compressing
  large frames (HELLO / SNAPSHOT) is a possible improvement.

## Running the sweep

```bash
pip install -e ".[dev]"          # includes tiktoken and zstandard
python -m sayonce.bench.harness --systems all --context-kb 1 10 50 100 --rounds 50 --out results/sweep.csv
```

This writes one row per (system, context size, repeat, round) to the CSV and
a `.meta.json` file with the settings, tokenizer and machine info. Round 0 is
the session setup. Because rows are cumulative, a 50-round run also gives the
results at 1, 5, 10 and 20 rounds. The full sweep takes about a minute.

**Tokenizer:** token counts use tiktoken `o200k_base`. tiktoken downloads its
encoding file on first use; if it cannot (offline), the harness falls back to
an approximate counter, prints a warning and writes `tokenizer=approx` in
every row. Only `o200k_base` numbers belong in the report.

### Columns

| Column | Meaning |
|---|---|
| `bytes_sent`, `bytes_received`, `header_bytes`, `cum_bytes` | application bytes on the wire (HTTP headers included and also shown separately) |
| `wire_tokens_*`, `cum_wire_tokens` | tokens of the information that crossed the wire, rendered as compact JSON |
| `llm_prompt_tokens` | tokens the worker's LLM read this round (0 for INFORM, which does not call the LLM) |
| `llm_prefix_cached_tokens` | leading tokens shared with the previous prompt, i.e. what a provider prefix cache could reuse |
| `latency_ms`, `cpu_ms` | per round; CPU covers client and server, which run in the same process |

## Findings from the first sweep (localhost, approximate tokens)

1. **Wire tokens drop like bytes.** At 100 KB context and 50 rounds the
   information sent between the agents is about 28k tokens with SayOnce vs
   1.2M with full-context JSON-RPC (about 40x).

2. **LLM prompt tokens are the same in every system.** The worker agent
   renders the whole shared context as its prompt each round, whatever the
   protocol. So SayOnce does not reduce what the LLM reads; it reduces what
   the agents send each other. The LLM-side saving comes from prefix caching
   (about 96-97% of prompt tokens are a repeated prefix here), and a stateless
   baseline could get the same cache hits if it re-renders the prompt in a
   stable order. What SayOnce adds on that side is that stable order is part of
   the protocol (spec 5.2), rather than something each client must get right.
   This answers the research question more precisely than "SayOnce saves
   LLM tokens", and should be stated that way in the report.

3. **Context store cost.** The first version copied and re-hashed the whole
   context on every message, which made SayOnce slower per round than JSON-RPC
   on localhost at 100 KB. The store now copies only changed segments and
   hashes segments separately, with history as a hash chain (spec 5.5). Store
   cost per message dropped from about 1.2 ms to 0.03 ms (about 35x), and
   SayOnce is now also faster per round on localhost (100 KB, 50 rounds, mean:
   2.4 ms vs 3.3 ms for JSON-RPC). Most of the remaining time is the mock LLM
   rendering the prompt, which is the same in every system.

## Analysis (figures and tables)

```bash
python -m sayonce.bench.analyze results/sweep.csv --network-csv results/net.csv --out results/analysis
```

Writes `analysis.md` (every figure has a matching table) and five figures:
cumulative bytes, tokens exchanged between agents, the 2x2 ablation, what the
worker LLM reads (with the prefix-cacheable share), and total time per link.
The cost table uses example prices; set them with `--price-in`,
`--price-cached`, `--price-out` and `--price-gb` and state them in the report.
Preliminary results are in `results/preliminary/` (approximate tokens).

## Cost of recovery (faults)

```bash
python -m sayonce.bench.faults --context-kb 10 100 --rounds 50 --fault-every 10 --network ideal 3g --out results/faults.csv
python -m sayonce.bench.analyze results/sweep.csv --network-csv results/net.csv --faults-csv results/faults.csv --out results/analysis
```

Injects a fault before every Nth round of a SayOnce conversation and
measures the extra bytes and time against the same round of a fault-free run.
Kinds: `corrupt_msg`, `server_diverge`, `client_diverge` (each recovered by
one RESYNC + SNAPSHOT), `drop_resume` (connection lost, session resumed) and
`server_restart` (session lost, client re-sends its context). A run fails if
client and server do not end in sync.

First results: one RESYNC costs about one compressed context (≈6 KB at
10 KB, ≈33 KB at 100 KB) and on 3G one extra round trip plus that transfer
(≈0.2-0.4 s). Resuming a session the server still holds costs a few hundred
bytes and one round trip.

## Network emulation

Two ways to run the same experiments over a slower, lossy link, plus a real
network check (see [docs/real-network.md](../docs/real-network.md)):
`scripts/netem_validate.sh` compares the emulator with kernel `tc netem`, and
`python -m sayonce.bench.remote` runs the benchmark between two computers.

**1. In-process proxy (any OS, default).** `sayonce/bench/netem.py` puts a TCP
proxy between client and server that adds one-way delay, a bandwidth limit
and segment loss. It is deterministic with a seed.

```bash
python -m sayonce.bench.harness --network ideal 4g 3g edge --context-kb 10 100 --rounds 20 --out results/net.csv
python -m sayonce.bench.harness --network 100:2:5 ...   # DELAY_MS:LOSS_%:MBIT/S (0 = unlimited)
```

Model per direction: data is cut into 1460-byte segments; each segment
occupies the link for `len*8/rate` (queueing behind earlier ones), then
travels for the one-way delay. A lost segment arrives late instead of never,
as with TCP: one extra RTT if at least 3 segments follow it (fast
retransmit), otherwise a 200 ms timeout plus one RTT. Delivery stays in order.
It does not model congestion control (slow start), and the TCP handshake
is not delayed (each system opens one connection, so this is the same for all).

**2. Kernel `tc netem` (Linux / WSL2, root).** For validating the proxy with
real TCP behaviour:

```bash
sudo scripts/netem.sh profile 3g
python -m sayonce.bench.harness --network 3g --external-netem --out results/netem_3g.csv
sudo scripts/netem.sh clear
```

`--external-netem` only records the conditions; the harness does not start its
own proxy. netem on `lo` affects all loopback traffic while it is active.

### Link profiles

Illustrative assumptions for the mobile-communication discussion (not
measurements; cite sources if presented as typical values):

| Profile | One-way delay | Loss | Bandwidth |
|---|---|---|---|
| `lan` | 1 ms | 0 % | 1000 Mbit/s |
| `wifi` | 10 ms | 0.5 % | 50 Mbit/s |
| `4g` | 30 ms | 1 % | 20 Mbit/s |
| `3g` | 75 ms | 2 % | 2 Mbit/s |
| `edge` | 150 ms | 2 % | 0.2 Mbit/s |
| `satellite` | 300 ms | 0.5 % | 10 Mbit/s |

New CSV columns: `network`, `delay_ms`, `loss`, `bandwidth_mbps`,
`net_segments`, `net_lost_segments`. The setup row (round 0) now records the
setup latency, which matters because SayOnce sends the context there.

### First network results (in-process proxy, mock LLM)

Total wall time for setup plus 20 rounds, in seconds (lower is better):

| Network | Context | jsonrpc | jsonrpc-gzip | cbor-full | json-delta | sayonce | SayOnce vs jsonrpc |
|---|---|---|---|---|---|---|---|
| ideal | 10 KB | 0.02 | 0.03 | 0.02 | 0.02 | 0.02 | 0.8x faster |
| ideal | 100 KB | 0.06 | 0.15 | 0.09 | 0.05 | 0.05 | 1.3x faster |
| 4g | 10 KB | 1.97 | 1.86 | 1.69 | 1.62 | 1.61 | 1.2x faster |
| 4g | 100 KB | 3.85 | 2.47 | 3.17 | 1.75 | 1.75 | 2.2x faster |
| 3g | 10 KB | 5.41 | 4.56 | 5.27 | 3.72 | 3.63 | 1.5x faster |
| 3g | 100 KB | 13.74 | 7.13 | 12.23 | 4.12 | 4.09 | 3.4x faster |
| edge | 10 KB | 19.81 | 12.23 | 18.16 | 8.33 | 7.66 | 2.6x faster |
| edge | 100 KB | 95.76 | 33.43 | 84.13 | 12.16 | 11.16 | 8.6x faster |

Observations:

- **The slower the link, the bigger the gain.** On an EDGE-like link with a
  100 KB context, SayOnce finishes 20 rounds in about 11 s vs 96 s for
  JSON-RPC (8.6x) and 33 s for gzip-compressed JSON-RPC (3x).
- **On fast links the gain is small.** With ideal localhost or 4G and a 10 KB
  context, time is dominated by round trips, not bytes, so all systems are
  close.
- **Delta drives the time saving; binary encoding barely matters for time.**
  `json-delta` is within about 10% of SayOnce on every link, while
  `cbor-full` (binary, no delta) is almost as slow as JSON-RPC. Encoding still
  saves bytes (see above), but once only deltas travel, messages are small
  enough that latency is set by the RTT.
- SayOnce's setup (sending the context once) is included in these totals.

These runs used approximate token counts (tokenizer offline); bytes and times
do not depend on the tokenizer. Re-run with tiktoken and, ideally, validate a
few points with `tc netem` before the report.


## Radio energy on a phone (RRC model)

```bash
python -m sayonce.bench.energy results/final_mcp/net.csv --out results/final_mcp/energy
```

Puts every run of a network CSV through the LTE / 3G radio state machine
(promotion, transfer, tail; parameters from Huang et al., MobiSys 2012) and
writes `energy.md`, `energy.csv` and `fig_energy_gap.png`. `--gaps` sets the
time between rounds (agent thinking), which the harness does not measure.

What it shows: on LTE with 100 KB contexts SayOnce uses 40% less radio energy
than JSON-RPC when rounds follow each other at once, but only 4-8% once there
are 5-15 s between rounds, because the radio's tail (about 11.6 s at 1 W)
dominates and costs the same for every protocol. On slow links (3G, EDGE),
where transfer time dominates, the saving stays large (about 47% on EDGE at a
5 s gap).
