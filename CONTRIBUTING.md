# Contributing

## Workflow

1. Pull the latest `main`: `git checkout main && git pull`
2. Create a branch for your work: `git checkout -b <name>/<short-topic>`
   (e.g. `enes/cbor-codec`, `omer/benchmark-harness`)
3. Commit small, focused changes with clear messages.
4. Push and open a Pull Request into `main`. At least one teammate reviews before merging.
5. Do not push directly to `main`.

## Before opening a PR

```bash
pytest
```

All tests should pass.

## Code style

- Python 3.10+
- Type hints on public functions
- Keep protocol code in `src/sayonce/`, experiment code in `benchmarks/`
