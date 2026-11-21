#!/usr/bin/env bash
# Validate the in-process network emulator against kernel tc netem.
# Linux or WSL2 only. Run as a normal user from the repository root with the
# virtual environment active; the script calls sudo only for tc.
#
#   scripts/netem_validate.sh            # about 25 minutes
#   QUICK=1 scripts/netem_validate.sh    # 1 repeat, about 10 minutes
#
# For each network below it runs the same benchmark twice: once through the
# Python emulator and once over loopback shaped by tc netem (the harness's
# --external-netem mode). Results go to results/real/ and the comparison to
# results/real/validation.md.

set -euo pipefail
cd "$(dirname "$0")/.."

OUT=results/real
SYSTEMS=(jsonrpc jsonrpc-gzip json-delta sayonce)
REPEATS=3; [[ "${QUICK:-0}" == "1" ]] && REPEATS=1
# name  harness network spec   netem.sh arguments
POINTS=(
  "4g     4g          profile 4g"
  "3g     3g          profile 3g"
  "edge   edge        profile edge"
  "d100l2 100:2:0     apply 100 2 0"
)

command -v tc >/dev/null || { echo "tc not found: sudo apt install iproute2"; exit 1; }
python -c "import sayonce" 2>/dev/null || { echo "activate the virtual environment first (source .venv/bin/activate)"; exit 1; }
if ! sudo tc qdisc replace dev lo root netem delay 1ms 2>/dev/null; then
  echo "This kernel has no netem support (sch_netem). On WSL2 run 'wsl --update' in Windows and try again."
  exit 1
fi
sudo tc qdisc del dev lo root 2>/dev/null || true
trap 'sudo tc qdisc del dev lo root 2>/dev/null || true; sudo ip link set dev lo mtu 65536 2>/dev/null || true; echo "netem cleared on lo"' EXIT

mkdir -p "$OUT"
for point in "${POINTS[@]}"; do
  read -r name spec netem_args <<<"$point"
  echo "== $name: emulator"
  python -m sayonce.bench.harness --workload mcp --systems "${SYSTEMS[@]}" --context-kb 10 100 --rounds 20 \
      --repeats "$REPEATS" --network "$spec" --out "$OUT/emu_$name.csv"
  echo "== $name: tc netem"
  # shellcheck disable=SC2086
  sudo DEV=lo scripts/netem.sh $netem_args
  python -m sayonce.bench.harness --workload mcp --systems "${SYSTEMS[@]}" --context-kb 10 100 --rounds 20 \
      --repeats "$REPEATS" --network "$spec" --external-netem --out "$OUT/netem_$name.csv"
  sudo scripts/netem.sh clear
done

python -m sayonce.bench.validate emulator="$OUT/emu_*.csv" netem="$OUT/netem_*.csv" --out "$OUT/validation.md"
