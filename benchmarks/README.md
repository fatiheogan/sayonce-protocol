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

## Next

- Network emulation with `tc netem` (step 7).
