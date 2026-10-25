# SayOnce Protocol Specification

Version: 0.1 (draft)
Status: working draft for implementation, will be refined as the project progresses.

## 1. Goals and non-goals

**Goals**

- Send the shared context (instructions, tool definitions, history) **once** per session.
- After that, send only **what changed** (deltas) plus the new message.
- Keep messages **compact** (binary encoding, dictionary references, small integer keys).
- Detect divergence between the two sides and **recover** with a resynchronization step.
- Make bytes and tokens **measurable** so the protocol can be compared fairly with JSON baselines.

**Non-goals (v0.1)**

- Security (authentication, encryption). Can be layered on with TLS later.
- More than two parties per session. Multi-agent setups use one session per pair.
- Concurrent requests inside one session. A session is strictly request/response (see 5.1).

## 2. Terminology

| Term | Meaning |
|---|---|
| Client | The agent that opens the session (Agent A). |
| Server | The agent that accepts the session (Agent B). |
| Context | The shared state both sides keep in sync: instructions, tools, history, variables. |
| Context version `ctx_v` | Integer that increases by 1 every time the context changes. |
| Context hash `ctx_h` | 8-byte fingerprint of the context, used to detect divergence. |
| Delta | A list of operations that turns context version `n` into `n+1`. |
| Dictionary | List of strings agreed at HELLO, referenced later by index. |

## 3. Transport and framing

SayOnce runs over any reliable byte stream. v0.1 uses **TCP**. QUIC is optional future work.

Each frame on the wire is:

```
+----------------------+---------------------------+
| length (4 bytes, BE) | CBOR-encoded frame        |
+----------------------+---------------------------+
```

- `length` is the number of bytes of the CBOR part, unsigned 32-bit big-endian.
- Maximum frame size: 16 MiB. Larger frames are rejected with `ERROR(FRAME_TOO_LARGE)`.

### 3.1 Frame structure

A frame is a CBOR **array** (not a map, to save key bytes):

```
[ ver, type, seq, ctx_v, body ]
```

| Field | Type | Description |
|---|---|---|
| `ver` | uint | Protocol version. `1` for this spec. |
| `type` | uint | Message type (section 4). |
| `seq` | uint | Sequence number, starts at 0 per direction, +1 per frame sent. |
| `ctx_v` | uint | Context version the sender had **before** this frame. |
| `body` | map | Type-specific fields. Keys are small unsigned integers. |

## 4. Message types

| Code | Name | Direction | Purpose |
|---|---|---|---|
| 1 | `HELLO` | C → S | Open a session, send dictionary, tools and initial context. |
| 2 | `HELLO_ACK` | S → C | Accept the session. |
| 3 | `MSG` | C → S | Send an intent and a delta. |
| 4 | `REPLY` | S → C | Answer a `MSG`, with its own delta. |
| 5 | `RESYNC` | either | "My context does not match yours." |
| 6 | `SNAPSHOT` | either | Full context, sent in answer to `RESYNC`. |
| 7 | `ERROR` | either | Protocol error. |
| 8 | `BYE` | either | Close the session. |

### 4.1 HELLO (C → S)

| Key | Name | Type | Description |
|---|---|---|---|
| 0 | `agent_id` | str | Client identifier. |
| 1 | `dict` | [str] | Dictionary entries (section 6). |
| 2 | `ctx` | map | Full initial context (section 5.2). This is version 0. |
| 3 | `caps` | map | Optional capabilities (e.g. `{"zstd": true}`). |
| 4 | `resume` | [bytes, uint, bytes] | Optional: `[session_id, ctx_v, ctx_h]` to resume a previous session. |

`ctx_v` in the frame header is `0`.

### 4.2 HELLO_ACK (S → C)

| Key | Name | Type | Description |
|---|---|---|---|
| 0 | `agent_id` | str | Server identifier. |
| 1 | `session_id` | bytes(8) | Random session identifier. |
| 2 | `ctx_h` | bytes(8) | Hash of the context the server stored. Client must compare it with its own. |
| 3 | `resumed` | bool | `true` if a resume request was accepted. |

### 4.3 MSG (C → S)

| Key | Name | Type | Description |
|---|---|---|---|
| 0 | `intent` | uint | Intent code (section 7). |
| 1 | `content` | any | The new message itself (text, structured args, tool call). |
| 2 | `delta` | [op] | Context changes other than the new message (section 5.3). May be empty. |
| 3 | `ctx_h` | bytes(8) | Hash of the context **after** applying this frame. |
| 4 | `task_id` | uint | Optional correlation id for a multi-round task. |

### 4.4 REPLY (S → C)

| Key | Name | Type | Description |
|---|---|---|---|
| 0 | `status` | uint | `0` OK, `1` PARTIAL, `2` FAILED, `3` REJECTED. |
| 1 | `content` | any | The answer. |
| 2 | `delta` | [op] | Context changes made by the server. |
| 3 | `ctx_h` | bytes(8) | Hash of the context after applying this frame. |
| 4 | `in_reply_to` | uint | `seq` of the `MSG` being answered. |

### 4.5 RESYNC (either direction)

| Key | Name | Type | Description |
|---|---|---|---|
| 0 | `reason` | uint | `1` VERSION_MISMATCH, `2` HASH_MISMATCH, `3` UNKNOWN_SESSION, `4` APPLY_FAILED. |
| 1 | `my_ctx_v` | uint | Version the sender has. |
| 2 | `my_ctx_h` | bytes(8) | Hash the sender has. |

### 4.6 SNAPSHOT (either direction)

| Key | Name | Type | Description |
|---|---|---|---|
| 0 | `ctx_v` | uint | Version of the snapshot. |
| 1 | `ctx` | map | Full context. |
| 2 | `ctx_h` | bytes(8) | Hash of the snapshot. |

### 4.7 ERROR and BYE

`ERROR` body: `{0: code (uint), 1: message (str)}`.
Codes: `1` BAD_FRAME, `2` UNSUPPORTED_VERSION, `3` UNKNOWN_TYPE, `4` FRAME_TOO_LARGE, `5` OUT_OF_ORDER.
`BYE` body: `{}`. The receiver closes the connection after reading it.

## 5. Shared context

### 5.1 Session rules

1. A session is **half-duplex**: the client sends one `MSG`, then waits for its `REPLY`
   (or `RESYNC`/`ERROR`) before sending the next `MSG`. This removes write conflicts:
   only one side changes the context at a time.
2. Every `MSG` and `REPLY` increases `ctx_v` by exactly **1**, even if `delta` is empty,
   because the new `content` is always appended to history (5.4).
3. Example: after HELLO both sides are at `v0`. `MSG(ctx_v=0)` moves both to `v1`.
   `REPLY(ctx_v=1)` moves both to `v2`, and so on.

### 5.2 Context model

The context is a CBOR map with these top-level segments:

| Key | Segment | Type | Typical change |
|---|---|---|---|
| `"sys"` | instructions | str | rarely |
| `"tools"` | tool definitions | map name → definition | rarely |
| `"hist"` | conversation history | list of turns | append every round |
| `"vars"` | shared variables / task state | map | set/delete |

Segment order (`sys`, `tools`, `hist`, `vars`) is fixed. This matters for
prompt caching (section 8.3): the parts that rarely change come first.

### 5.3 Delta operations

A delta is a list of operations. Each operation is a CBOR array:

| Op code | Name | Form | Effect |
|---|---|---|---|
| 1 | `SET` | `[1, path, value]` | Set the value at `path` (create if missing). |
| 2 | `DEL` | `[2, path]` | Delete the value at `path`. |
| 3 | `APPEND` | `[3, path, [items]]` | Append items to the list at `path`. |

`path` is a list of map keys and list indices, e.g. `["vars", "budget"]` or `["tools", "search"]`.
Operations are applied **in order**. If any operation fails (missing path, wrong type),
the whole frame is rejected and the receiver sends `RESYNC(APPLY_FAILED)`.

### 5.4 Implicit history append

The new message must not be sent twice (once as `content`, once inside a delta).
So both sides apply this rule automatically **before** the explicit delta:

```
MSG   → append {"r": "c", "i": intent, "c": content} to ctx["hist"]
REPLY → append {"r": "s", "s": status, "c": content} to ctx["hist"]
```

### 5.5 Context hash

`ctx_h` = first 8 bytes of BLAKE2b over the **canonical CBOR** encoding of the context
(RFC 8949 section 4.2.1: deterministic encoding, map keys sorted).

### 5.6 Receive procedure

When a `MSG` or `REPLY` arrives:

1. If header `ctx_v` ≠ local version → send `RESYNC(VERSION_MISMATCH)`.
2. Apply the implicit history append, then the delta operations, on a **copy** of the context.
   If this fails → send `RESYNC(APPLY_FAILED)`, keep the old context.
3. Compute the hash of the new context. If it ≠ body `ctx_h` → `RESYNC(HASH_MISMATCH)`.
4. Otherwise commit the new context and set local version = `ctx_v + 1`.

### 5.7 Resynchronization

- The side that receives a `RESYNC` answers with a `SNAPSHOT` of its own current context.
  The **server's** context is authoritative if both sides send `RESYNC` at the same time.
- After a `SNAPSHOT`, both sides use that version and hash, and the client re-sends its
  last `MSG` if it was not answered.

**When does desync happen?** TCP already retransmits lost packets, so packet loss
(`tc netem loss`) shows up as **extra latency**, not as lost frames. RESYNC is needed when:

- the connection drops and the client reconnects with `HELLO(resume=...)`,
- one agent restarts and loses its context store,
- a bug or a partial write corrupts one side's context.

The benchmark harness will test RESYNC with **fault injection** (dropping or corrupting a
frame on purpose) in addition to `tc netem` loss.

### 5.8 Session resume

A client that reconnects sends `HELLO` with `resume = [session_id, ctx_v, ctx_h]` and an
empty `ctx`. If the server still has that session at the same version and hash, it answers
`HELLO_ACK(resumed=true)` and the session continues without re-sending the context.
Otherwise it answers `HELLO_ACK(resumed=false)` and the client sends a `SNAPSHOT`.

## 6. Dictionary

The `HELLO` dictionary is a list of strings (tool names, common keys, role names, ...).
Index `i` refers to entry `i`.

**Where references are allowed:** map keys inside the context and inside deltas, path
elements, and tool names. In these positions a string is expected, so an **unsigned
integer** `i` unambiguously means "dictionary entry `i`". Indices 0–23 cost 1 byte in CBOR.

**Integers in paths.** A path element can be a list index (`["hist", 3]`) or a dictionary
reference (`["vars", 5]`). The receiver decides while walking the path: if the current
container is a **list**, the integer is an index; if it is a **map**, the integer is a
dictionary reference. Context map keys are always strings, so this is never ambiguous.

The context hash (5.5) is always computed on the expanded, string-keyed form, so the
dictionary changes only the bytes on the wire, never the meaning of the context.

References are **not** used inside arbitrary `content` values, because there an integer
could be a real integer.

The dictionary is fixed for the whole session in v0.1.

## 7. Intents

| Code | Intent | Meaning |
|---|---|---|
| 1 | `REQUEST` | Ask the other agent to do something and return a result. |
| 2 | `INFORM` | Share information. No result expected beyond an acknowledgement. |
| 3 | `DELEGATE` | Hand over a subtask; the receiver owns it until it replies. |
| 4 | `CANCEL` | Cancel an earlier task (`task_id`). |

## 8. Measurement methodology

This section defines how SayOnce is compared with the baselines, so the numbers are fair.

### 8.1 Systems compared

| ID | Encoding | Context per round | Purpose |
|---|---|---|---|
| B1 | JSON-RPC over HTTP (MCP/A2A style) | full | Main baseline |
| B2 | JSON + zstd (and gzip) | full | Is compression alone enough? |
| B3 | CBOR, no delta | full | Gain from binary encoding only |
| B4 | JSON, with delta | delta | Gain from delta only |
| S  | SayOnce (CBOR + dictionary + delta) | delta | Full protocol |

B3 and B4 form the **ablation**: they separate the effect of binary encoding from the
effect of delta updates.

### 8.2 Byte metrics

- `bytes_wire`: all application bytes sent in both directions, including framing.
  For B1, HTTP request/response headers are included.
- Reported per round and **cumulative** over rounds 1–50.

### 8.3 Token metrics

Bytes and tokens are not the same thing. An LLM reads text, so a binary frame saves bytes
but does not by itself save tokens. Two token metrics are therefore reported:

1. **`tokens_wire`**: tokens in the information that crosses the wire, rendered as
   canonical text (JSON) and counted with `tiktoken` (`o200k_base`). This shows how much
   less **information** SayOnce transmits.
2. **`tokens_llm`**: tokens the receiving agent's LLM must process each round.
   - Stateless receiver (B1–B3): the prompt is the full context rendered each round.
   - SayOnce receiver: keeps the context and renders it in fixed segment order
     (5.2), so the earlier part of the prompt stays identical across rounds and can be
     served from the provider's **prompt cache**. Only the new part is uncached.
   - We report `uncached_input`, `cached_input` and `output` tokens separately, and a cost
     `cost = uncached·p_in + cached·p_cache + output·p_out` with prices as parameters.

**Fairness note.** A JSON baseline receiver could also use prompt caching if it rendered
its prompt in a stable order. We will report B1 both **without** and **with** caching,
so the LLM-side gain that comes from SayOnce itself is not overstated. Measuring how large
that remaining gain is, is part of the research question.

A delta that changes an early segment (e.g. `sys` or `tools`) invalidates the cache from
that point on. The harness will count these cache breaks.

### 8.4 Other metrics

- `latency`: time from sending `MSG` to receiving `REPLY`, per round.
- `cpu`: process CPU time for encoding/decoding (`time.process_time`).
- `resync_count` and resync bytes under fault injection.

### 8.5 Parameters

| Parameter | Values |
|---|---|
| Rounds | 1, 5, 10, 20, 50 |
| Initial context size | 1, 10, 50, 100 KB |
| Delay (`tc netem`) | 0, 50, 100, 200 ms |
| Loss (`tc netem`) | 0, 1, 2, 5 % |
| LLM | mock (default), real API for a small validation run |

## 9. Example session

```
C → S  HELLO      ctx_v=0  {dict:["search","budget",...], ctx:{sys, tools, hist:[], vars:{}}}
S → C  HELLO_ACK  ctx_v=0  {session_id, ctx_h=h0}
C → S  MSG        ctx_v=0  {intent:REQUEST, content:"find flights IST→BER", delta:[], ctx_h=h1}
S → C  REPLY      ctx_v=1  {status:OK, content:[...results...], delta:[[1,["vars",1],500]], ctx_h=h2}
C → S  MSG        ctx_v=2  {intent:REQUEST, content:"cheapest one?", delta:[], ctx_h=h3}
...
```

In the third frame the client sends only the new request (about 30 bytes of content),
not the instructions, tools and history again. In the fourth frame `["vars", 1]` uses
dictionary entry 1 (`"budget"`) as a key.
