# SayOnce benchmark analysis

Source: `results/final/sweep.csv` (4284 rows), tokenizer `o200k_base`, up to 50 rounds.

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
| JSON-RPC | 406 | 2.89k | 7.84k | 23.8k | 121k |
| CBOR, no delta | 400 | 2.75k | 7.53k | 23.2k | 119k |
| JSON + delta | 480 | 1.21k | 2.15k | 4.02k | 9.63k |
| SayOnce, no zstd | 407 | 827 | 1.37k | 2.44k | 5.68k |
| SayOnce | 407 | 827 | 1.37k | 2.44k | 5.68k |

**10 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 2k | 10.9k | 23.8k | 55.7k | 200k |
| CBOR, no delta | 2.1k | 10.8k | 23.6k | 55.2k | 199k |
| JSON + delta | 2.08k | 2.81k | 3.75k | 5.62k | 11.2k |
| SayOnce, no zstd | 2.1k | 2.52k | 3.06k | 4.14k | 7.36k |
| SayOnce | 2.1k | 2.52k | 3.06k | 4.14k | 7.36k |

**50 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 9.18k | 46.8k | 95.6k | 199k | 560k |
| CBOR, no delta | 9.7k | 47.1k | 95.8k | 199k | 558k |
| JSON + delta | 9.26k | 9.99k | 10.9k | 12.8k | 18.4k |
| SayOnce, no zstd | 9.7k | 10.1k | 10.7k | 11.7k | 15k |
| SayOnce | 9.7k | 10.1k | 10.7k | 11.7k | 15k |

**100 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 18.2k | 91.6k | 185k | 379k | 1.01M |
| CBOR, no delta | 19.2k | 92.5k | 186k | 379k | 1.01M |
| JSON + delta | 18.2k | 19k | 19.9k | 21.8k | 27.4k |
| SayOnce, no zstd | 19.2k | 19.6k | 20.2k | 21.2k | 24.5k |
| SayOnce | 19.2k | 19.6k | 20.2k | 21.2k | 24.5k |

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
| LLM input tokens | 927k |
| of which not a repeated prefix | 26.3k |
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
| prompt re-read every round, no cache | $334.56 |
| with prefix caching | $72.43 |

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
| prompt re-read every round, no cache | $556.84 |
| with prefix caching | $99.41 |

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
| prompt re-read every round, no cache | $1,557.10 |
| with prefix caching | $222.35 |

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
| prompt re-read every round, no cache | $2,807.42 |
| with prefix caching | $375.03 |

LLM cost dominates data cost by orders of magnitude. The protocol's direct saving is in transfer (bytes, time on slow links). Its LLM-side contribution is indirect: a stable, versioned context makes prefix caching reliable.

## 6. Time over emulated links (20 rounds, setup included)

![](fig5_network_time.png)

Mean ± 95% confidence interval over 5 runs (Student t). Bytes are deterministic; time varies with emulated loss and scheduling.

**10 KB context**

| system | ideal | 4g | 3g | edge |
|---|---|---|---|---|
| JSON-RPC | 0.0106 ± 0.00062 s | 1.81 ± 0.26 s | 5.29 ± 0.29 s | 19.4 ± 0.5 s |
| JSON-RPC+gzip | 0.0194 ± 0.00096 s | 1.64 ± 0.29 s | 4.26 ± 0.42 s | 11.7 ± 0.75 s |
| CBOR, no delta | 0.0121 ± 0.0011 s | 1.71 ± 0.27 s | 5.08 ± 0.35 s | 17.5 ± 0.7 s |
| JSON + delta | 0.0109 ± 0.0036 s | 1.4 ± 0.14 s | 3.43 ± 0.19 s | 7.85 ± 0.33 s |
| SayOnce | 0.0103 ± 0.0008 s | 1.4 ± 0.15 s | 3.34 ± 0.19 s | 6.97 ± 0.33 s |
| **JSON-RPC / SayOnce** | **1.0x** | **1.3x** | **1.6x** | **2.8x** |

**100 KB context**

| system | ideal | 4g | 3g | edge |
|---|---|---|---|---|
| JSON-RPC | 0.0563 ± 0.014 s | 3.31 ± 0.44 s | 13.3 ± 0.49 s | 94.7 ± 0.84 s |
| JSON-RPC+gzip | 0.135 ± 0.023 s | 2.25 ± 0.54 s | 6.99 ± 0.71 s | 33 ± 1.3 s |
| CBOR, no delta | 0.0757 ± 0.015 s | 2.86 ± 0.29 s | 11.9 ± 0.46 s | 83.7 ± 0.47 s |
| JSON + delta | 0.0395 ± 0.0077 s | 1.67 ± 0.29 s | 4.26 ± 0.57 s | 12.3 ± 0.89 s |
| SayOnce | 0.0438 ± 0.0096 s | 1.49 ± 0.3 s | 3.7 ± 0.57 s | 8.47 ± 0.97 s |
| **JSON-RPC / SayOnce** | **1.3x** | **2.2x** | **3.6x** | **11.2x** |

The slower the link, the larger the gain. Time savings come from delta; binary encoding changes little once messages are small.

## 7. Cost of recovery (SayOnce, 50 rounds, fault before rounds [10, 20, 30, 40, 50])

Extra cost of one fault compared with the same round of a fault-free run. A RESYNC re-sends the whole context once (compressed); resuming a session the server still has costs only a new connection.

**ideal**

| fault | context | setup (HELLO) | extra bytes / fault | extra time / fault | resyncs |
|---|---|---|---|---|---|
| corrupt_msg | 10 KB | 4 KB | 6.79 KB | 1.8 ms | 5 |
| server_diverge | 10 KB | 4 KB | 6.85 KB | 2.5 ms | 5 |
| client_diverge | 10 KB | 4 KB | 6.76 KB | 2.4 ms | 5 |
| drop_resume | 10 KB | 4 KB | 356 B | 0.5 ms | 0 |
| server_restart | 10 KB | 4 KB | 7.06 KB | 3.1 ms | 5 |
| corrupt_msg | 100 KB | 31.3 KB | 33.4 KB | 8.3 ms | 5 |
| server_diverge | 100 KB | 31.3 KB | 33.5 KB | 12.2 ms | 5 |
| client_diverge | 100 KB | 31.3 KB | 33.4 KB | 15.3 ms | 5 |
| drop_resume | 100 KB | 31.3 KB | 436 B | 1.0 ms | 0 |
| server_restart | 100 KB | 31.3 KB | 33.8 KB | 8.1 ms | 5 |

**3g**

| fault | context | setup (HELLO) | extra bytes / fault | extra time / fault | resyncs |
|---|---|---|---|---|---|
| corrupt_msg | 10 KB | 4 KB | 6.79 KB | 181.2 ms | 5 |
| server_diverge | 10 KB | 4 KB | 6.85 KB | 182.5 ms | 5 |
| client_diverge | 10 KB | 4 KB | 6.76 KB | 328.0 ms | 5 |
| drop_resume | 10 KB | 4 KB | 356 B | 154.8 ms | 0 |
| server_restart | 10 KB | 4 KB | 7.06 KB | 252.7 ms | 5 |
| corrupt_msg | 100 KB | 31.3 KB | 33.4 KB | 381.2 ms | 5 |
| server_diverge | 100 KB | 31.3 KB | 33.5 KB | 391.2 ms | 5 |
| client_diverge | 100 KB | 31.3 KB | 33.4 KB | 377.0 ms | 5 |
| drop_resume | 100 KB | 31.3 KB | 439 B | 163.6 ms | 0 |
| server_restart | 100 KB | 31.3 KB | 33.8 KB | 332.7 ms | 5 |

Stateless baselines have no state to recover, but they also cannot detect a corrupted message: it simply produces a wrong answer. SayOnce detects it with the context hash.
