# SayOnce benchmark analysis

Source: `results/final_mcp/sweep.csv` (4284 rows), tokenizer `o200k_base`, up to 50 rounds.

## 1. Cumulative bytes on the wire

![](fig1_cumulative_bytes.png)

**1 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 2.78 KB | 17 KB | 41.5 KB | 113 KB | 507 KB |
| JSON-RPC+gzip | 1.6 KB | 9.17 KB | 21 KB | 50.9 KB | 182 KB |
| JSON-RPC+zstd | 1.63 KB | 9.36 KB | 21.5 KB | 52.3 KB | 188 KB |
| CBOR, no delta | 2.01 KB | 12.4 KB | 31.6 KB | 90.7 KB | 435 KB |
| JSON + delta | 3.52 KB | 7.86 KB | 13.4 KB | 24.5 KB | 57.8 KB |
| SayOnce, no zstd | 2.08 KB | 3.42 KB | 5.16 KB | 8.67 KB | 19.4 KB |
| SayOnce | 1.25 KB | 2.59 KB | 4.33 KB | 7.84 KB | 18.6 KB |

After 50 rounds SayOnce sends 27.3x fewer bytes than JSON-RPC and 9.8x fewer than JSON-RPC+gzip.

**10 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 11.6 KB | 60.9 KB | 129 KB | 288 KB | 946 KB |
| JSON-RPC+gzip | 3.79 KB | 20.1 KB | 42.9 KB | 94.6 KB | 291 KB |
| JSON-RPC+zstd | 3.96 KB | 21 KB | 44.8 KB | 98.7 KB | 303 KB |
| CBOR, no delta | 9.65 KB | 49.2 KB | 105 KB | 236 KB | 799 KB |
| JSON + delta | 12.3 KB | 16.6 KB | 22.2 KB | 33.3 KB | 66.6 KB |
| SayOnce, no zstd | 9.73 KB | 11.1 KB | 12.8 KB | 16.3 KB | 27 KB |
| SayOnce | 3.69 KB | 5.02 KB | 6.76 KB | 10.3 KB | 21 KB |

After 50 rounds SayOnce sends 45.1x fewer bytes than JSON-RPC and 13.9x fewer than JSON-RPC+gzip.

**50 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 56 KB | 283 KB | 574 KB | 1.18 MB | 3.17 MB |
| JSON-RPC+gzip | 13.6 KB | 68.9 KB | 141 KB | 290 KB | 778 KB |
| JSON-RPC+zstd | 14.4 KB | 73.3 KB | 149 KB | 307 KB | 824 KB |
| CBOR, no delta | 47.7 KB | 234 KB | 473 KB | 971 KB | 2.63 MB |
| JSON + delta | 56.8 KB | 61.1 KB | 66.6 KB | 77.7 KB | 111 KB |
| SayOnce, no zstd | 47.8 KB | 49.1 KB | 50.9 KB | 54.4 KB | 65.1 KB |
| SayOnce | 14.5 KB | 15.9 KB | 17.6 KB | 21.1 KB | 31.8 KB |

After 50 rounds SayOnce sends 99.6x fewer bytes than JSON-RPC and 24.5x fewer than JSON-RPC+gzip; it stays below gzip from round 2 on (the uncompressed HELLO costs more at first).

**100 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 106 KB | 533 KB | 1.07 MB | 2.18 MB | 5.67 MB |
| JSON-RPC+gzip | 20 KB | 101 KB | 205 KB | 420 KB | 1.11 MB |
| JSON-RPC+zstd | 21 KB | 106 KB | 215 KB | 440 KB | 1.16 MB |
| CBOR, no delta | 89.6 KB | 442 KB | 888 KB | 1.8 MB | 4.71 MB |
| JSON + delta | 107 KB | 111 KB | 117 KB | 128 KB | 161 KB |
| SayOnce, no zstd | 89.7 KB | 91 KB | 92.8 KB | 96.3 KB | 107 KB |
| SayOnce | 21.2 KB | 22.5 KB | 24.3 KB | 27.8 KB | 38.5 KB |

After 50 rounds SayOnce sends 147.1x fewer bytes than JSON-RPC and 28.7x fewer than JSON-RPC+gzip; it stays below gzip from round 2 on (the uncompressed HELLO costs more at first).

HTTP header share of all bytes:

| context | JSON-RPC | JSON + delta |
|---|---|---|
| 1 | 3.7 % | 35.1 % |
| 10 | 2.0 % | 30.4 % |
| 50 | 0.6 % | 18.3 % |
| 100 | 0.3 % | 12.6 % |

## 2. Tokens exchanged between the agents

![](fig2_cumulative_wire_tokens.png)

Tokens measure information, not encoding: compression does not change them (gzip/zstd are left out), and the CBOR full-context line lies on top of JSON-RPC because both carry the same information.

**1 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 546 | 3.53k | 9.03k | 25.8k | 123k |
| CBOR, no delta | 545 | 3.4k | 8.73k | 25.1k | 121k |
| JSON + delta | 631 | 1.35k | 2.31k | 4.18k | 9.86k |
| SayOnce, no zstd | 557 | 976 | 1.53k | 2.62k | 5.92k |
| SayOnce | 557 | 976 | 1.53k | 2.62k | 5.92k |

**10 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 2.39k | 12.8k | 27.5k | 62.8k | 216k |
| CBOR, no delta | 2.46k | 12.7k | 27.3k | 62.3k | 214k |
| JSON + delta | 2.48k | 3.21k | 4.18k | 6.06k | 11.8k |
| SayOnce, no zstd | 2.47k | 2.9k | 3.46k | 4.56k | 7.88k |
| SayOnce | 2.47k | 2.9k | 3.46k | 4.56k | 7.88k |

**50 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 12.2k | 61.8k | 126k | 259k | 706k |
| CBOR, no delta | 12.6k | 62.1k | 126k | 259k | 705k |
| JSON + delta | 12.3k | 13k | 14k | 15.9k | 21.6k |
| SayOnce, no zstd | 12.6k | 13k | 13.6k | 14.7k | 18k |
| SayOnce | 12.6k | 13k | 13.6k | 14.7k | 18k |

**100 KB context**

| system | round 1 | round 5 | round 10 | round 20 | round 50 |
|---|---|---|---|---|---|
| JSON-RPC | 23.7k | 119k | 241k | 489k | 1.28M |
| CBOR, no delta | 24.3k | 120k | 241k | 489k | 1.28M |
| JSON + delta | 23.8k | 24.5k | 25.5k | 27.4k | 33.1k |
| SayOnce, no zstd | 24.3k | 24.7k | 25.3k | 26.4k | 29.7k |
| SayOnce | 24.3k | 24.7k | 25.3k | 26.4k | 29.7k |

## 3. Ablation: what does each idea contribute? (50 rounds)

![](fig3_ablation.png)

| context | JSON / full | CBOR / full | JSON / delta | CBOR / delta | CBOR / delta + zstd |
|---|---|---|---|---|---|
| 1 KB | 507 KB | 435 KB | 57.8 KB | 19.4 KB | 18.6 KB |
| 10 KB | 946 KB | 799 KB | 66.6 KB | 27 KB | 21 KB |
| 50 KB | 3.17 MB | 2.63 MB | 111 KB | 65.1 KB | 31.8 KB |
| 100 KB | 5.67 MB | 4.71 MB | 161 KB | 107 KB | 38.5 KB |

Gain factors (bytes of the system before / after adding the idea):

| context | binary alone | delta alone | binary on top of delta | zstd for large frames on top | all together |
|---|---|---|---|---|---|
| 1 KB | 1.17x | 8.8x | 2.98x | 1.04x | 27.3x |
| 10 KB | 1.18x | 14.2x | 2.46x | 1.29x | 45.1x |
| 50 KB | 1.20x | 28.5x | 1.71x | 2.05x | 99.6x |
| 100 KB | 1.20x | 35.2x | 1.51x | 2.78x | 147.1x |

Delta is the main gain. Binary encoding alone saves little when the full context is sent (the context text dominates), but on top of delta it matters more, because the remaining messages are small and their JSON keys, framing and HTTP headers become a large share of each message. Compressing large frames mainly shrinks the one-time HELLO, so its share of the total falls as conversations get longer.

## 4. What the worker's LLM reads (100 KB context)

![](fig4_llm_tokens.png)

The worker renders the whole shared context as its prompt every round, in every system, so LLM input tokens are identical across protocols. What changes is how much of that prompt is a repeated prefix that a provider prefix cache can serve.

|  | after 50 rounds |
|---|---|
| LLM input tokens | 1.19M |
| of which not a repeated prefix | 33k |
| cacheable share | 97.2 % |

## 5. Cost per 1,000 conversations of 50 rounds

Example prices (set with --price-*): input $3.0/M tokens, cached input $0.3/M, output $15.0/M, data $2.0/GB. **These are assumptions, not quotes.**

**1 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $1.01 |
| JSON-RPC+gzip | $0.36 |
| JSON-RPC+zstd | $0.38 |
| CBOR, no delta | $0.87 |
| JSON + delta | $0.12 |
| SayOnce, no zstd | $0.04 |
| SayOnce | $0.04 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $342.20 |
| with prefix caching | $74.32 |

**10 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $1.89 |
| JSON-RPC+gzip | $0.58 |
| JSON-RPC+zstd | $0.61 |
| CBOR, no delta | $1.60 |
| JSON + delta | $0.13 |
| SayOnce, no zstd | $0.05 |
| SayOnce | $0.04 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $601.92 |
| with prefix caching | $106.75 |

**50 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $6.34 |
| JSON-RPC+gzip | $1.56 |
| JSON-RPC+zstd | $1.65 |
| CBOR, no delta | $5.27 |
| JSON + delta | $0.22 |
| SayOnce, no zstd | $0.13 |
| SayOnce | $0.06 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $1,953.01 |
| with prefix caching | $271.96 |

**100 KB context**

| system | data transfer cost |
|---|---|
| JSON-RPC | $11.33 |
| JSON-RPC+gzip | $2.21 |
| JSON-RPC+zstd | $2.31 |
| CBOR, no delta | $9.41 |
| JSON + delta | $0.32 |
| SayOnce, no zstd | $0.21 |
| SayOnce | $0.08 |

| LLM cost (same for every system) | per 1k conversations |
|---|---|
| prompt re-read every round, no cache | $3,596.51 |
| with prefix caching | $473.16 |

LLM cost dominates data cost by orders of magnitude. The protocol's direct saving is in transfer (bytes, time on slow links). Its LLM-side contribution is indirect: a stable, versioned context makes prefix caching reliable.

## 6. Time over emulated links (20 rounds, setup included)

![](fig5_network_time.png)

Mean ± 95% confidence interval over 3 runs (Student t). Bytes are deterministic; time varies with emulated loss and scheduling.

**10 KB context**

| system | d50ms_l0%_inf | d50ms_l2%_inf | d50ms_l5%_inf | d100ms_l0%_inf | d100ms_l2%_inf | d100ms_l5%_inf | d200ms_l0%_inf | d200ms_l2%_inf | d200ms_l5%_inf |
|---|---|---|---|---|---|---|---|---|---|
| JSON-RPC | 2.06 ± 0.014 s | 2.82 ± 0.38 s | 3.86 ± 1.3 s | 4.06 ± 0.0061 s | 5.33 ± 0.77 s | 6.8 ± 1.5 s | 8.06 ± 0.0084 s | 10.6 ± 1.5 s | 13.5 ± 3 s |
| JSON-RPC+gzip | 2.07 ± 0.0021 s | 2.73 ± 0.16 s | 3.14 ± 0.8 s | 4.06 ± 0.0098 s | 5.01 ± 0.28 s | 5.54 ± 1 s | 8.07 ± 0.0076 s | 9.95 ± 0.57 s | 11 ± 2.1 s |
| CBOR, no delta | 2.06 ± 0.0068 s | 2.73 ± 0.28 s | 3.67 ± 1.1 s | 4.06 ± 0.0072 s | 5.15 ± 0.81 s | 6.47 ± 1.3 s | 8.07 ± 0.00093 s | 10.2 ± 1.5 s | 12.9 ± 2.6 s |
| JSON + delta | 2.16 ± 0.012 s | 2.26 ± 0.44 s | 2.76 ± 1.5 s | 4.25 ± 0.0017 s | 4.4 ± 0.62 s | 5.06 ± 2 s | 8.46 ± 0.0045 s | 8.73 ± 1.1 s | 10.1 ± 4 s |
| SayOnce | 2.16 ± 0.009 s | 2.26 ± 0.43 s | 2.76 ± 1.5 s | 4.26 ± 0.014 s | 4.39 ± 0.57 s | 5.06 ± 2 s | 8.46 ± 0.0027 s | 8.73 ± 1.2 s | 10.1 ± 4 s |
| **JSON-RPC / SayOnce** | **1.0x** | **1.3x** | **1.4x** | **1.0x** | **1.2x** | **1.3x** | **1.0x** | **1.2x** | **1.3x** |

**100 KB context**

| system | d50ms_l0%_inf | d50ms_l2%_inf | d50ms_l5%_inf | d100ms_l0%_inf | d100ms_l2%_inf | d100ms_l5%_inf | d200ms_l0%_inf | d200ms_l2%_inf | d200ms_l5%_inf |
|---|---|---|---|---|---|---|---|---|---|
| JSON-RPC | 2.2 ± 0.02 s | 4.27 ± 0.51 s | 6.07 ± 1.5 s | 4.2 ± 0.024 s | 8.09 ± 1.2 s | 9.87 ± 2.4 s | 8.2 ± 0.04 s | 15.8 ± 3 s | 19.6 ± 4.9 s |
| JSON-RPC+gzip | 2.24 ± 0.023 s | 3.66 ± 1.5 s | 4.7 ± 1.5 s | 4.24 ± 0.034 s | 6.38 ± 2.3 s | 7.97 ± 1.8 s | 8.23 ± 0.063 s | 12.6 ± 4.4 s | 15.7 ± 3.5 s |
| CBOR, no delta | 2.3 ± 0.054 s | 4.37 ± 1.9 s | 5.46 ± 1.6 s | 4.28 ± 0.013 s | 7.93 ± 2.6 s | 9.49 ± 2.2 s | 8.27 ± 0.0052 s | 15.5 ± 5 s | 18.7 ± 4.4 s |
| JSON + delta | 2.23 ± 0.014 s | 2.64 ± 0.74 s | 3.05 ± 1.1 s | 4.34 ± 0.012 s | 4.93 ± 0.98 s | 5.48 ± 1.5 s | 8.54 ± 0.04 s | 9.75 ± 2 s | 10.8 ± 3 s |
| SayOnce | 2.24 ± 0.026 s | 2.45 ± 0.47 s | 2.93 ± 1.6 s | 4.34 ± 0.0064 s | 4.6 ± 0.56 s | 5.27 ± 2.1 s | 8.54 ± 0.022 s | 9.09 ± 1.1 s | 10.4 ± 4.1 s |
| **JSON-RPC / SayOnce** | **1.0x** | **1.7x** | **2.1x** | **1.0x** | **1.8x** | **1.9x** | **1.0x** | **1.7x** | **1.9x** |

The slower the link, the larger the gain. Time savings come from delta; binary encoding changes little once messages are small.

## 7. Cost of recovery (SayOnce, 50 rounds, fault before rounds [10, 20, 30, 40, 50])

Extra cost of one fault compared with the same round of a fault-free run. A RESYNC re-sends the whole context once (compressed); resuming a session the server still has costs only a new connection.

**ideal**

| fault | context | setup (HELLO) | extra bytes / fault | extra time / fault | resyncs |
|---|---|---|---|---|---|
| corrupt_msg | 10 KB | 3.29 KB | 5.71 KB | 2.6 ms | 5 |
| server_diverge | 10 KB | 3.29 KB | 5.78 KB | 4.1 ms | 5 |
| client_diverge | 10 KB | 3.29 KB | 5.67 KB | 4.0 ms | 5 |
| drop_resume | 10 KB | 3.29 KB | 572 B | 0.7 ms | 0 |
| server_restart | 10 KB | 3.29 KB | 6.16 KB | 3.5 ms | 5 |
| corrupt_msg | 100 KB | 20.8 KB | 22.7 KB | 20.6 ms | 5 |
| server_diverge | 100 KB | 20.8 KB | 22.8 KB | 32.4 ms | 5 |
| client_diverge | 100 KB | 20.8 KB | 22.7 KB | 32.0 ms | 5 |
| drop_resume | 100 KB | 20.8 KB | 933 B | 1.0 ms | 0 |
| server_restart | 100 KB | 20.8 KB | 23.5 KB | 16.7 ms | 5 |

**3g**

| fault | context | setup (HELLO) | extra bytes / fault | extra time / fault | resyncs |
|---|---|---|---|---|---|
| corrupt_msg | 10 KB | 3.29 KB | 5.71 KB | 205.4 ms | 5 |
| server_diverge | 10 KB | 3.29 KB | 5.78 KB | 208.2 ms | 5 |
| client_diverge | 10 KB | 3.29 KB | 5.67 KB | 321.7 ms | 5 |
| drop_resume | 10 KB | 3.29 KB | 572 B | 156.6 ms | 0 |
| server_restart | 10 KB | 3.29 KB | 6.16 KB | 253.4 ms | 5 |
| corrupt_msg | 100 KB | 20.8 KB | 22.7 KB | 297.9 ms | 5 |
| server_diverge | 100 KB | 20.8 KB | 22.8 KB | 304.9 ms | 5 |
| client_diverge | 100 KB | 20.8 KB | 22.7 KB | 406.0 ms | 5 |
| drop_resume | 100 KB | 20.8 KB | 929 B | 159.7 ms | 0 |
| server_restart | 100 KB | 20.8 KB | 23.5 KB | 355.5 ms | 5 |

Stateless baselines have no state to recover, but they also cannot detect a corrupted message: it simply produces a wrong answer. SayOnce detects it with the context hash.
