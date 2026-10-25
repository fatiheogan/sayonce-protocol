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

## Next

- `harness.py` (step 6): parameter sweeps, token counting, CSV output.
- Network emulation with `tc netem` (step 7).
