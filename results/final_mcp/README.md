# Final results with real MCP tool definitions

Same experiments and settings as `results/final/`, but on the `mcp` workload:
the context holds the real tool definitions of 12 public MCP servers instead of
generated text (see [benchmarks/README.md](../../benchmarks/README.md#workloads)).
Tokenizer `o200k_base`, network results from the in-process emulator.

| File | Contents |
|---|---|
| `sweep.csv` | all 7 systems, contexts 1/10/50/100 KB, 50 rounds, 3 repeats, ideal network |
| `net.csv` | 5 systems, 10/100 KB, 20 rounds, profiles ideal/4g/3g/edge, 5 repeats |
| `net_grid.csv` | 5 systems, 10/100 KB, 20 rounds, the proposal's grid (delay 50/100/200 ms x loss 0/2/5 %), 3 repeats |
| `faults.csv` | SayOnce with a fault every 10 rounds, 6 fault kinds, 10/100 KB, ideal and 3g |
| `analysis/` | tables and figures for sweep + profiles + faults |
| `analysis_grid/` | the same, with the proposal's grid as network section |

## Compared with the generated workload

Bytes after 50 rounds, how many times fewer SayOnce sends:

| context | vs JSON-RPC, generated | vs JSON-RPC, real tools | vs JSON-RPC+gzip, generated | vs JSON-RPC+gzip, real tools |
|---|---|---|---|---|
| 1 KB | 27.5x | 27.3x | 10.5x | 9.8x |
| 10 KB | 43.5x | 45.1x | 15.1x | 13.9x |
| 50 KB | 86.2x | 99.6x | 26.6x | 24.5x |
| 100 KB | 111.3x | 147.1x | 32.9x | 28.7x |

- The conclusions do not depend on the generated data.
- Against plain JSON-RPC the gain is **larger** with real tools: SayOnce's
  one-time HELLO is compressed with zstd, and JSON schemas compress well.
- Against gzip-compressed JSON-RPC the gain is **slightly smaller**, for the
  same reason: real schemas compress about 5-6x instead of 3x, which helps the
  gzip baseline in every round.
- Ablation: binary encoding alone still saves only about 15 %; delta remains
  the main gain (9-35x).
- LLM input tokens are again identical across protocols. Real schemas are
  denser in tokens (1.19M input tokens over 50 rounds at 100 KB, vs 927k for
  generated text); 97 % of them are a repeated, cacheable prefix.

Time over emulated links (20 rounds, 100 KB, mean of 5 runs): JSON-RPC takes
2.1x longer than SayOnce on 4G, 3.8x on 3G and 12.3x on EDGE (generated data:
2.2x, 3.6x and 11.2x). On the proposal's grid, there is no
difference without loss (1.0x) and SayOnce is 1.7-2.1x faster with 2-5 % loss.

Recovery costs (section 7) behave as before: a RESYNC re-sends the compressed
context once (about 23 KB at 100 KB), resuming a dropped connection costs
under 1 KB.

The "ideal" network times (fractions of a second) were measured while other
work ran on the same 2-core machine; do not quote them.

## Regenerating

```bash
pip install -e ".[dev]"
python -m sayonce.bench.harness --workload mcp --context-kb 1 10 50 100 --rounds 50 --repeats 3 \
    --out results/final_mcp/sweep.csv
python -m sayonce.bench.harness --workload mcp --systems jsonrpc jsonrpc-gzip cbor-full json-delta sayonce \
    --context-kb 10 100 --rounds 20 --repeats 5 --network ideal 4g 3g edge --out results/final_mcp/net.csv
python -m sayonce.bench.harness --workload mcp --systems jsonrpc jsonrpc-gzip cbor-full json-delta sayonce \
    --context-kb 10 100 --rounds 20 --repeats 3 --out results/final_mcp/net_grid.csv \
    --network 50:0:0 50:2:0 50:5:0 100:0:0 100:2:0 100:5:0 200:0:0 200:2:0 200:5:0
python -m sayonce.bench.faults --workload mcp --context-kb 10 100 --rounds 50 --fault-every 10 \
    --network ideal 3g --out results/final_mcp/faults.csv
python -m sayonce.bench.analyze results/final_mcp/sweep.csv --network-csv results/final_mcp/net.csv \
    --faults-csv results/final_mcp/faults.csv --out results/final_mcp/analysis
python -m sayonce.bench.analyze results/final_mcp/sweep.csv --network-csv results/final_mcp/net_grid.csv \
    --faults-csv results/final_mcp/faults.csv --out results/final_mcp/analysis_grid
```
