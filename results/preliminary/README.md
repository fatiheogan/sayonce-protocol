# Preliminary results

Generated in a sandbox **without network access**, so:

- **Token counts are approximate** (`tokenizer=approx`): tiktoken could not
  download its encoding. Do not quote token numbers from here in the report.
- Bytes and times do not depend on the tokenizer and are valid for the setup
  described below.
- Network results use the in-process emulator, not kernel `tc netem`.

Files:

| File | Contents |
|---|---|
| `sweep.csv` | all 6 systems, contexts 1/10/50/100 KB, 50 rounds, ideal network |
| `net.csv` | 5 systems, contexts 10/100 KB, 20 rounds, profiles ideal/4g/3g/edge |
| `analysis/analysis.md` | tables and findings, with figures `analysis/fig*.png` |

## Regenerating the final results

On a machine with internet access (for tiktoken), from the repository root:

```bash
pip install -e ".[dev]"
python -m sayonce.bench.harness --context-kb 1 10 50 100 --rounds 50 --repeats 3 --out results/final/sweep.csv
python -m sayonce.bench.harness --systems jsonrpc jsonrpc-gzip cbor-full json-delta sayonce \
    --context-kb 10 100 --rounds 20 --network ideal 4g 3g edge --out results/final/net.csv
python -m sayonce.bench.analyze results/final/sweep.csv --network-csv results/final/net.csv --out results/final/analysis
```

Check that `results/final/analysis/analysis.md` does **not** start with the
"Preliminary" warning; that confirms tiktoken was used. The network sweep
takes several minutes because full-context systems are slow on the EDGE
profile (that is the point of the experiment).
