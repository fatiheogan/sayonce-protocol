# SayOnce

[![tests](https://github.com/fatiheogan/sayonce-protocol/actions/workflows/tests.yml/badge.svg)](https://github.com/fatiheogan/sayonce-protocol/actions/workflows/tests.yml)

**A token- and bandwidth-efficient communication protocol for AI agents.**

CSE 476/575 Mobile Communication and Networks, Fall 2026, Gebze Technical University
Instructor: Prof. Dr. Hasari Çelebi

## Team

| Name | Student ID | GitHub |
|---|---|---|
| Ömer Faruk Gürsel | 210104004053 | [@omerfarukgursel](https://github.com/omerfarukgursel) |
| Fatih Emre Oğan | 230104004090 | [@fatiheogan](https://github.com/fatiheogan) |
| Enes Ersoy | 220104004083 | [@errsoyeness](https://github.com/errsoyeness) |

## Research question

Can a compact, intent-based protocol that shares the context once and then sends
only changes reduce the bytes and tokens needed for multi-round agent
communication, compared with the JSON-based approach used today (MCP, A2A)?

## Approach

- **Compact binary messages** (Protobuf / CBOR) instead of verbose JSON.
- **Intent-based message types** with a small fixed vocabulary (REQUEST, INFORM, DELEGATE, ...).
- **Shared context with delta updates**: context is agreed once at session start,
  later messages carry only what changed, with RESYNC on version mismatch or loss.

### Message flow

```
Agent A (client)                               Agent B (server)
   | -- HELLO(dictionary, tools, ctx v0) ----------> |
   | -- MSG(intent, ctx_v, delta) -----------------> |
   | <------------------------------ REPLY(delta) -- |
   | <- - - - - RESYNC (version mismatch / loss) - - |
```

## Experiments

| Baselines | Parameters | Metrics |
|---|---|---|
| JSON-RPC/HTTP (MCP/A2A style) | rounds: 1–50 | bytes on the wire |
| JSON + gzip/zstd | context: 1–100 KB | LLM tokens |
| Binary only (no delta) | loss: 0–5%, delay: 50–200 ms (`tc netem`) | latency, CPU |

## Repository layout

```
src/sayonce/     protocol library (codec, messages, context, transport, session, agents)
examples/        runnable demos
tests/           unit tests
benchmarks/      benchmark harness and baselines
docs/            proposal, protocol spec (docs/protocol.md), report
```

## Getting started

```bash
git clone https://github.com/fatiheogan/sayonce-protocol.git
cd sayonce-protocol
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
python examples/demo.py --rounds 10 --context-kb 20   # two agents talking
```

## Live demo: two terminals or two computers

```bash
python examples/live.py            # menu: start the server or the client
```

Or directly:

```bash
python examples/live.py server --port 7474                          # Agent B
python examples/live.py client --host <server IP> --port 7474       # Agent A
```

The client sends the shared context once, then the tasks you type. Every
round it also replays the same conversation over JSON-RPC/HTTP on the client
machine and prints both byte counts side by side. Client commands:

| command | what it does |
|---|---|
| any text | send it as a task |
| `/set KEY VALUE` | change a shared variable; only the delta is sent |
| `/auto N` | send N sample tasks, one per second |
| `/drop` | cut the connection and resume the session without re-sending the context |
| `/stats` | totals so far |
| `/quit` | close the session |

On two computers, put both on the same network (a phone hotspot is the safest;
university Wi-Fi often isolates devices) and allow Python through the
firewall on the server computer. In Wireshark, the filter `tcp.port == 7474`
shows one large HELLO followed by small messages. Restarting the server and
then typing `/drop` on the client shows recovery: the context is sent once
more as a SNAPSHOT and the session continues.

The protocol is specified in [docs/protocol.md](docs/protocol.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the team workflow.
