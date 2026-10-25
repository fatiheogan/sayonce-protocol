# SayOnce benchmark analysis

Source: `results/preliminary/sweep.csv` (1428 rows), tokenizer `approx`, up to 50 rounds.

> **Preliminary:** token counts are approximate (tiktoken was not available). Re-run the harness with tiktoken before using token numbers in the report.

## 1. Cumulative bytes on the wire

![](fig1_cumulative_bytes.png)

**1 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 2.47 KB | 16 KB | 40.5 KB | 116 KB | 548 KB |
| JSON-RPC+gzip | 1.64 KB | 9.57 KB | 22.1 KB | 54.9 KB | 210 KB |
| JSON-RPC+zstd | 1.66 KB | 9.67 KB | 22.3 KB | 55.5 KB | 213 KB |
| CBOR, no delta | 1.81 KB | 12.1 KB | 32.1 KB | 96.3 KB | 483 KB |
| JSON + delta | 3.19 KB | 7.61 KB | 13.2 KB | 24.6 KB | 58.6 KB |
| SayOnce, no zstd | 1.87 KB | 3.31 KB | 5.17 KB | 9 KB | 20.5 KB |
| SayOnce | 1.3 KB | 2.73 KB | 4.6 KB | 8.42 KB | 19.9 KB |

After 50 rounds SayOnce sends 27.5x fewer bytes than JSON-RPC and 10.5x fewer than JSON-RPC+gzip.

**10 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 11.6 KB | 61.5 KB | 132 KB | 298 KB | 1 MB |
| JSON-RPC+gzip | 4.63 KB | 24.3 KB | 51.1 KB | 112 KB | 349 KB |
| JSON-RPC+zstd | 4.68 KB | 24.5 KB | 51.5 KB | 113 KB | 350 KB |
| CBOR, no delta | 9.98 KB | 52.2 KB | 112 KB | 256 KB | 882 KB |
| JSON + delta | 12.3 KB | 16.7 KB | 22.3 KB | 33.7 KB | 67.7 KB |
| SayOnce, no zstd | 10 KB | 11.5 KB | 13.3 KB | 17.2 KB | 28.7 KB |
| SayOnce | 4.44 KB | 5.87 KB | 7.74 KB | 11.6 KB | 23.1 KB |

After 50 rounds SayOnce sends 43.5x fewer bytes than JSON-RPC and 15.1x fewer than JSON-RPC+gzip.

**50 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 52.4 KB | 266 KB | 540 KB | 1.11 MB | 3.04 MB |
| JSON-RPC+gzip | 16.4 KB | 83.3 KB | 169 KB | 348 KB | 938 KB |
| JSON-RPC+zstd | 16.6 KB | 83.8 KB | 170 KB | 349 KB | 943 KB |
| CBOR, no delta | 46.9 KB | 233 KB | 473 KB | 978 KB | 2.69 MB |
| JSON + delta | 53.1 KB | 57.5 KB | 63.2 KB | 74.5 KB | 108 KB |
| SayOnce, no zstd | 47 KB | 48.4 KB | 50.3 KB | 54.1 KB | 65.6 KB |
| SayOnce | 16.7 KB | 18.1 KB | 20 KB | 23.8 KB | 35.3 KB |

After 50 rounds SayOnce sends 86.2x fewer bytes than JSON-RPC and 26.6x fewer than JSON-RPC+gzip; it stays below gzip from round 2 on (the uncompressed HELLO costs more at first).

**100 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 104 KB | 521 KB | 1.05 MB | 2.14 MB | 5.6 MB |
| JSON-RPC+gzip | 30.8 KB | 155 KB | 313 KB | 635 KB | 1.66 MB |
| JSON-RPC+zstd | 31.1 KB | 157 KB | 316 KB | 641 KB | 1.67 MB |
| CBOR, no delta | 93 KB | 459 KB | 924 KB | 1.88 MB | 4.93 MB |
| JSON + delta | 104 KB | 109 KB | 114 KB | 126 KB | 160 KB |
| SayOnce, no zstd | 93.1 KB | 94.5 KB | 96.4 KB | 100 KB | 112 KB |
| SayOnce | 31.7 KB | 33.1 KB | 35 KB | 38.8 KB | 50.3 KB |

After 50 rounds SayOnce sends 111.3x fewer bytes than JSON-RPC and 32.9x fewer than JSON-RPC+gzip; it stays below gzip from round 2 on (the uncompressed HELLO costs more at first).

HTTP header share of all bytes:

| context | JSON-RPC | JSON + delta |
|---|---|---|
| 1 | 3.5 % | 34.6 % |
| 10 | 1.9 % | 30.0 % |
| 50 | 0.6 % | 18.7 % |
| 100 | 0.3 % | 12.7 % |

## 2. Tokens exchanged between the agents

![](fig2_cumulative_wire_tokens.png)

Tokens measure information, not encoding: compression does not change them (gzip/zstd are left out), and the CBOR full-context line lies on top of JSON-RPC because both carry the same information.

**1 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 470 | 3.28k | 8.78k | 26.5k | 133k |
| CBOR, no delta | 467 | 3.14k | 8.46k | 25.9k | 131k |
| JSON + delta | 550 | 1.31k | 2.28k | 4.26k | 10.1k |
| SayOnce, no zstd | 471 | 890 | 1.43k | 2.55k | 5.8k |
| SayOnce | 471 | 890 | 1.43k | 2.55k | 5.8k |

**10 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 2.4k | 12.9k | 28.1k | 65.1k | 228k |
| CBOR, no delta | 2.5k | 12.9k | 27.9k | 64.5k | 227k |
| JSON + delta | 2.48k | 3.24k | 4.22k | 6.17k | 12k |
| SayOnce, no zstd | 2.5k | 2.92k | 3.46k | 4.56k | 7.8k |
| SayOnce | 2.5k | 2.92k | 3.46k | 4.56k | 7.8k |

**50 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 11.1k | 56.4k | 115k | 239k | 663k |
| CBOR, no delta | 11.6k | 56.8k | 115k | 239k | 662k |
| JSON + delta | 11.2k | 11.9k | 12.9k | 14.9k | 20.7k |
| SayOnce, no zstd | 11.6k | 12k | 12.6k | 13.7k | 16.9k |
| SayOnce | 11.6k | 12k | 12.6k | 13.7k | 16.9k |

**100 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 21.9k | 110k | 223k | 455k | 1.2M |
| CBOR, no delta | 22.9k | 111k | 224k | 455k | 1.2M |
| JSON + delta | 22k | 22.7k | 23.7k | 25.7k | 31.5k |
| SayOnce, no zstd | 22.9k | 23.4k | 23.9k | 25k | 28.3k |
| SayOnce | 22.9k | 23.4k | 23.9k | 25k | 28.3k |

## 3. Ablation: what does each idea contribute? (50 rounds)

![](fig3_ablation.png)

| context | JSON / full | CBOR / full | JSON / delta | CBOR / delta | CBOR / delta + zstd |
|---|---|---|---|---|---|
| 1 KB | 548 KB | 483 KB | 58.6 KB | 20.5 KB | 19.9 KB |
| 10 KB | 1 MB | 882 KB | 67.7 KB | 28.7 KB | 23.1 KB |
| 50 KB | 3.04 MB | 2.69 MB | 108 KB | 65.6 KB | 35.3 KB |
| 100 KB | 5.6 MB | 4.93 MB | 160 KB | 112 KB | 50.3 KB |

Gain factors (bytes of the system before / after adding the idea):

| context | binary alone | delta alone | binary on top of delta | zstd for large frames on top | all together |
|---|---|---|---|---|---|
| 1 KB | 1.13x | 9.4x | 2.86x | 1.03x | 27.5x |
| 10 KB | 1.14x | 14.8x | 2.36x | 1.24x | 43.5x |
| 50 KB | 1.13x | 28.1x | 1.65x | 1.86x | 86.2x |
| 100 KB | 1.14x | 35.1x | 1.43x | 2.22x | 111.3x |

Delta is the main gain. Binary encoding alone saves little when the full context is sent (the context text dominates), but on top of delta it matters more, because the remaining messages are small and their JSON keys, framing and HTTP headers become a large share of each message. Compressing large frames mainly shrinks the one-time HELLO, so its share of the total falls as conversations get longer.

## 4. What the worker's LLM reads (100 KB context)

![](fig4_llm_tokens.png)

The worker renders the whole shared context as its prompt every round, in every system, so LLM input tokens are identical across protocols. What changes is how much of that prompt is a repeated prefix that a provider prefix cache can serve.

|  | after 50 rounds |
|---|---|
| LLM input tokens | 1.08M |
| of which not a repeated prefix | 30.3k |
| cacheable share | 97.2 % |

## 5. Cost per 1,000 conversations of 50 rounds

Example prices (set with --price-*): input $3.0/M tokens, cached input $0.3/M, output $15.0/M, data $2.0/GB. **These are assumptions, not quotes.**

**1 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $1.10 |
| JSON-RPC+gzip | $0.42 |
| JSON-RPC+zstd | $0.43 |
| CBOR, no delta | $0.97 |
| JSON + delta | $0.12 |
| SayOnce, no zstd | $0.04 |
| SayOnce | $0.04 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $363.53 |
| with prefix caching | $78.81 |

**10 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $2.01 |
| JSON-RPC+gzip | $0.70 |
| JSON-RPC+zstd | $0.70 |
| CBOR, no delta | $1.76 |
| JSON + delta | $0.14 |
| SayOnce, no zstd | $0.06 |
| SayOnce | $0.05 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $624.51 |
| with prefix caching | $110.39 |

**50 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $6.09 |
| JSON-RPC+gzip | $1.88 |
| JSON-RPC+zstd | $1.89 |
| CBOR, no delta | $5.37 |
| JSON + delta | $0.22 |
| SayOnce, no zstd | $0.13 |
| SayOnce | $0.07 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $1,805.88 |
| with prefix caching | $255.37 |

**100 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $11.20 |
| JSON-RPC+gzip | $3.31 |
| JSON-RPC+zstd | $3.34 |
| CBOR, no delta | $9.87 |
| JSON + delta | $0.32 |
| SayOnce, no zstd | $0.22 |
| SayOnce | $0.10 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $3,275.44 |
| with prefix caching | $435.19 |

LLM cost dominates data cost by orders of magnitude. The protocol's direct saving is in transfer (bytes, time on slow links). Its LLM-side contribution is indirect: a stable, versioned context makes prefix caching reliable.

## 6. Time over emulated links (20 rounds, setup included)

![](fig5_network_time.png)

Mean ± 95% confidence interval over 3 runs (Student t). Bytes are deterministic; time varies with emulated loss and scheduling.

**10 KB context**

| system | ideal | 4g | 3g | edge |
|---|---|---|---|---|
| JSON-RPC | 0.0207 ± 0.016 s | 1.75 ± 0.5 s | 5.3 ± 0.82 s | 19.4 ± 1.4 s |
| JSON-RPC+gzip | 0.0328 ± 0.023 s | 1.68 ± 0.73 s | 4.38 ± 0.79 s | 11.9 ± 1.3 s |
| CBOR, no delta | 0.0296 ± 0.017 s | 1.64 ± 0.34 s | 5.14 ± 0.78 s | 17.6 ± 1.4 s |
| JSON + delta | 0.0181 ± 0.016 s | 1.45 ± 0.37 s | 3.49 ± 0.48 s | 7.93 ± 0.85 s |
| SayOnce | 0.0186 ± 0.017 s | 1.44 ± 0.37 s | 3.38 ± 0.5 s | 7.04 ± 0.86 s |
| **JSON-RPC / SayOnce** | **1.1x** | **1.2x** | **1.6x** | **2.8x** |

**100 KB context**

| system | ideal | 4g | 3g | edge |
|---|---|---|---|---|
| JSON-RPC | 0.0721 ± 0.025 s | 3.53 ± 0.8 s | 13.6 ± 0.84 s | 95 ± 1.8 s |
| JSON-RPC+gzip | 0.179 ± 0.031 s | 2.14 ± 0.76 s | 6.79 ± 0.88 s | 32.7 ± 1.8 s |
| CBOR, no delta | 0.125 ± 0.093 s | 2.89 ± 0.77 s | 12 ± 1.1 s | 83.7 ± 1.3 s |
| JSON + delta | 0.0558 ± 0.003 s | 1.63 ± 0.44 s | 4.15 ± 0.78 s | 12.1 ± 1.4 s |
| SayOnce | 0.0513 ± 0.011 s | 1.59 ± 0.78 s | 3.89 ± 1.3 s | 8.78 ± 2.3 s |
| **JSON-RPC / SayOnce** | **1.4x** | **2.2x** | **3.5x** | **10.8x** |

The slower the link, the larger the gain. Time savings come from delta; binary encoding changes little once messages are small.

## 7. Cost of recovery (SayOnce, 50 rounds, fault before rounds [10, 20, 30, 40, 50])

Extra cost of one fault compared with the same round of a fault-free run. A RESYNC re-sends the whole context once (compressed); resuming a session the server still has costs only a new connection.

**ideal**

| fault | context | setup (HELLO) | extra bytes / fault | extra time / fault | resyncs |
|---|---|---|---|---|---|
| corrupt_msg | 10 KB | 4 KB | 6.79 KB | 2.6 ms | 5 |
| server_diverge | 10 KB | 4 KB | 6.85 KB | 3.8 ms | 5 |
| client_diverge | 10 KB | 4 KB | 6.76 KB | 4.5 ms | 5 |
| drop_resume | 10 KB | 4 KB | 356 B | 1.2 ms | 0 |
| server_restart | 10 KB | 4 KB | 7.06 KB | 5.8 ms | 5 |
| corrupt_msg | 100 KB | 31.3 KB | 33.4 KB | 8.8 ms | 5 |
| server_diverge | 100 KB | 31.3 KB | 33.5 KB | 18.8 ms | 5 |
| client_diverge | 100 KB | 31.3 KB | 33.4 KB | 17.7 ms | 5 |
| drop_resume | 100 KB | 31.3 KB | 437 B | 1.1 ms | 0 |
| server_restart | 100 KB | 31.3 KB | 33.8 KB | 12.3 ms | 5 |

**3g**

| fault | context | setup (HELLO) | extra bytes / fault | extra time / fault | resyncs |
|---|---|---|---|---|---|
| corrupt_msg | 10 KB | 4 KB | 6.79 KB | 182.4 ms | 5 |
| server_diverge | 10 KB | 4 KB | 6.85 KB | 184.4 ms | 5 |
| client_diverge | 10 KB | 4 KB | 6.76 KB | 323.0 ms | 5 |
| drop_resume | 10 KB | 4 KB | 356 B | 155.4 ms | 0 |
| server_restart | 10 KB | 4 KB | 7.06 KB | 254.7 ms | 5 |
| corrupt_msg | 100 KB | 31.3 KB | 33.4 KB | 383.8 ms | 5 |
| server_diverge | 100 KB | 31.3 KB | 33.5 KB | 396.6 ms | 5 |
| client_diverge | 100 KB | 31.3 KB | 33.4 KB | 378.6 ms | 5 |
| drop_resume | 100 KB | 31.3 KB | 435 B | 156.3 ms | 0 |
| server_restart | 100 KB | 31.3 KB | 33.8 KB | 329.1 ms | 5 |

Stateless baselines have no state to recover, but they also cannot detect a corrupted message: it simply produces a wrong answer. SayOnce detects it with the context hash.
