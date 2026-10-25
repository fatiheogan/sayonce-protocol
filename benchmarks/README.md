# Benchmarks

Benchmark harness and baselines (to be implemented):

- `baseline_jsonrpc/`  JSON-RPC over HTTP (MCP/A2A style)
- `baseline_gzip/`     JSON + gzip/zstd
- `baseline_binary/`   binary encoding without delta
- `harness.py`         runs rounds 1–50, context 1–100 KB, records bytes/tokens/latency/CPU
