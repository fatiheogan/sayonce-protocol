# Discussion: positioning, related work, security and limitations

Draft text for the report's related-work, discussion and limitations
sections. Numbers come from `results/final_mcp/` (real MCP tool
definitions), `results/real/` (kernel netem) and
`results/final_mcp/energy/` (radio energy model).

## 1. Which link actually re-sends the context

An LLM agent system has (at least) three links. The claim "the same context
is sent in every round" is true for some of them and false for others, so the
report must say which one SayOnce targets.

| link | protocol today | is the context re-sent every round? |
|---|---|---|
| host ↔ MCP server | MCP: JSON-RPC 2.0 over stdio or Streamable HTTP | **No.** The client fetches tool definitions once with `tools/list`; a `tools/call` carries only the tool name and arguments. |
| host ↔ LLM provider | stateless HTTPS API (Messages, Chat Completions, Responses) | **Yes.** Every request carries the system prompt, every tool definition and the whole history. |
| agent ↔ agent | A2A: JSON-RPC 2.0 over HTTP (also gRPC, REST bindings) | **Depends.** A2A groups messages with a `contextId`, but defines no shared-state or delta mechanism; a stateless remote agent needs the context again. |

So SayOnce is not a replacement for MCP's tool-call link. Its targets are:

1. **agent ↔ agent** links (A2A-style delegation), where one agent repeatedly
   hands work and context to another;
2. **device ↔ gateway**: a phone or edge device talks SayOnce to a gateway
   that keeps the session and makes the (stateless) LLM API calls on the
   device's behalf. The expensive, slow, battery-powered link carries only
   deltas; the gateway-to-provider link is in a data centre.

The JSON-RPC baseline in our benchmark models exactly these links: the full
context in every request, as an LLM API call or a stateless A2A agent requires.

Recent MCP revisions point in the same direction from the other side: the
2026-07-28 specification asks servers to return `tools/list` in a
deterministic order "to enable client-side caching and improve LLM prompt
cache hit rates", and adds cache-freshness hints (`ttlMs`) to list results.
The same revision removed protocol-level sessions from Streamable HTTP, i.e.
MCP is moving towards stateless servers, while SayOnce deliberately keeps
per-session state (see section 4).

## 2. Bytes on the wire vs. LLM tokens

SayOnce reduces **bytes on the link**, not the **tokens the model reads**.
The receiving agent reconstructs the full prompt from its context store, so
LLM input tokens are identical for every protocol in our results
(`llm_prompt_tokens` column). Two provider features are relevant:

* **Server-side conversation state** (e.g. OpenAI Responses API
  `previous_response_id`, Conversations API) also avoids re-uploading the
  history, but OpenAI's documentation states that all previous input tokens
  in the chain are still billed as input tokens. Like SayOnce, it saves upload
  bytes, not tokens; unlike SayOnce, it only exists on the device ↔ provider
  link and is provider-specific.
* **Prompt caching** is what reduces token cost. Anthropic bills cache reads
  at 0.1x the base input price (less on some newer models) and 5-minute cache
  writes at 1.25x; OpenAI caches prompts of 1,024 tokens or more
  automatically. Caching needs a stable prompt prefix. SayOnce keeps the
  rarely-changing parts (system prompt, tools) first and only appends history,
  so 97% of the worker's input tokens at 100 KB are a cacheable prefix. A JSON
  sender that renders its prompt in a stable order gets the same cache hits:
  caching is complementary to SayOnce, not a result of it.

## 3. Related techniques

| technique | idea | relation to SayOnce |
|---|---|---|
| HPACK (RFC 7541, HTTP/2), QPACK (RFC 9204, HTTP/3) | both ends keep a dynamic table of previously sent headers and send indices instead of repeating them | the same principle (shared state, send references), applied to HTTP headers; SayOnce applies it to the application payload |
| Compression Dictionary Transport (RFC 9842, Sept 2025) | an earlier version of a resource is used as the compression dictionary for the next one (delta compression over HTTP, Brotli/Zstandard) | the closest standard alternative: a JSON-RPC sender using the previous request as dictionary would recover much of the delta gain without a new protocol. Not implemented here: **future work, and a stronger baseline than gzip** |
| CBOR (RFC 8949), Protocol Buffers / gRPC | compact binary encodings | our ablation: binary encoding alone saves only about 15%; the 9-35x gain comes from sending the context once |
| gzip / zstd per message | stateless compression | our `jsonrpc-gzip` baseline. Compresses each request well (5-6x on JSON schemas) but cannot exploit repetition across rounds; SayOnce still sends 28.7x fewer bytes after 50 rounds at 100 KB |
| prompt caching | provider reuses the processed prompt prefix | reduces token cost and time-to-first-token; does not reduce bytes; complementary (section 2) |

## 4. Security considerations

SayOnce as implemented has **no authentication or encryption**
(`docs/protocol.md`, non-goals). A deployment would need the following.

* **Run over TLS 1.3 (or QUIC).** The handshake is paid once per connection,
  which a long SayOnce session amortises. Each TLS 1.3 record adds about
  22 bytes (5-byte header, 1-byte content type, 16-byte AEAD tag). That is a
  large *relative* overhead on SayOnce's 60-250 byte messages, but small in
  absolute terms and the same for every protocol; it does not change the
  comparison.
* **Compression side channels.** CRIME (2012) and BREACH (2013) showed that
  compressing secret data together with attacker-influenced data, then
  encrypting it, leaks the secret through the ciphertext length. SayOnce
  compresses the HELLO context with zstd, and the size of every delta reveals
  how much the context changed. If a context mixes secrets (keys, personal
  data) with text an attacker can influence (web pages, user input, tool
  output), compression should be disabled for those segments or messages
  padded.
* **Per-session state.** The receiver stores every session's context
  (100 KB+ per session). An unauthenticated client could open many sessions
  and exhaust memory, so a server needs authentication before HELLO, a per-
  client session limit, a maximum context size and eviction (an evicted
  session recovers through RESYNC/SNAPSHOT). Stateful sessions also need
  sticky load balancing or a shared session store; this is the opposite trade-
  off to MCP's recent move to stateless servers.
* **Integrity.** Deltas are checked against a context hash, so a lost or
  reordered delta is detected and repaired by RESYNC. The hash detects
  accidents, not attacks; with TLS the transport provides integrity.

## 5. Limitations of the evaluation

* **Mock LLM.** Replies are generated, not produced by a real model; token
  counts use the `o200k_base` tokenizer. Byte and token counts are exact for
  the messages we send; a real model's replies would be longer and vary.
* **Emulated networks.** Main network results come from an in-process
  emulator. Kernel `tc netem` (Docker Desktop on macOS, 1500-byte MTU, 3
  repeats) agrees for SayOnce within 1-18%, and shows a larger JSON-RPC
  penalty under loss (100 ms / 2% / 100 KB: 8.3 s emulated vs 24.3 s kernel),
  so the emulated latency gains are conservative. A real two-computer 4G
  measurement is still to be done (`docs/real-network.md`, section 2).
* **Energy model.** Radio energy is computed from measured bytes and times
  with LTE/3G state-machine parameters from Huang et al. (MobiSys 2012), not
  measured with a power meter; 5G NR has different (and network-configured)
  timers. The time between rounds is a parameter, not a measurement. Result:
  40% less radio energy than JSON-RPC on LTE with back-to-back rounds, but
  only 4-8% with 5-15 s between rounds, because the radio tail dominates.
* **Baselines.** All compressed baselines are stateless. A stateful
  JSON baseline (RFC 9842 dictionary compression, or zstd with the previous
  request as dictionary) was not implemented.
* **Transport.** TCP only; QUIC (no head-of-line blocking across streams,
  0-RTT resumption) was not evaluated.
* **Workloads.** Two workloads (generated text, real tool definitions of 12
  MCP servers) and one task shape (repeated requests to one worker). Contexts
  that change heavily every round would shrink the delta advantage.

## References

* Model Context Protocol specification, revision 2026-07-28: tools,
  Streamable HTTP transport, changelog. https://modelcontextprotocol.io/specification/latest
* Agent2Agent (A2A) protocol specification. https://github.com/a2aproject/A2A
* OpenAI, Conversation state (Responses API). https://developers.openai.com/api/docs/guides/conversation-state
* OpenAI, Prompt caching. https://developers.openai.com/api/docs/guides/prompt-caching
* Anthropic, Prompt caching. https://docs.claude.com/en/docs/build-with-claude/prompt-caching
* RFC 7541, HPACK: Header Compression for HTTP/2 (2015).
* RFC 9204, QPACK: Field Compression for HTTP/3 (2022).
* RFC 9842, Compression Dictionary Transport (2025).
* RFC 8949, Concise Binary Object Representation (CBOR) (2020).
* RFC 8446, The Transport Layer Security (TLS) Protocol Version 1.3 (2018).
* J. Rizzo, T. Duong, "The CRIME attack", Ekoparty 2012; Y. Gluck, N. Harris,
  A. Prado, "BREACH: Reviving the CRIME attack", Black Hat USA 2013.
* J. Huang et al., "A Close Examination of Performance and Power
  Characteristics of 4G LTE Networks", ACM MobiSys 2012.
