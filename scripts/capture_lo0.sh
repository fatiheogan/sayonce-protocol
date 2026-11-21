#!/usr/bin/env bash
# Capture JSON-RPC and SayOnce on the wire (loopback) with tshark, for Wireshark
# screenshots and per-connection byte counts in the report.
# macOS (lo0) or Linux (lo). Needs Wireshark/tshark; on macOS the ChmodBPF
# helper that comes with Wireshark must be installed (log out and in once if
# tshark says "permission denied").
#
#   scripts/capture_lo0.sh                 # 10 KB context, 5 rounds
#   CTX=100 ROUNDS=10 scripts/capture_lo0.sh
#
# Writes results/real/capture.pcapng, capture_ports.txt (which port is which
# system) and capture_conversations.txt (tshark's TCP conversation table).

set -euo pipefail
cd "$(dirname "$0")/.."

OUT=results/real
CTX="${CTX:-10}"
ROUNDS="${ROUNDS:-5}"
SYSTEMS=(jsonrpc sayonce)
IFACE=lo0; [[ "$(uname)" == "Linux" ]] && IFACE=lo
PCAP="$OUT/capture.pcapng"

command -v tshark >/dev/null || { echo "tshark not found: install Wireshark"; exit 1; }
python -c "import sayonce" 2>/dev/null || { echo "activate the virtual environment first (source .venv/bin/activate)"; exit 1; }
mkdir -p "$OUT"

LOG=$(mktemp)
cleanup() {
  [[ -n "${TSHARK_PID:-}" ]] && kill "$TSHARK_PID" 2>/dev/null || true
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -f "$LOG"
}
trap cleanup EXIT

python -u -m sayonce.bench.remote serve --systems "${SYSTEMS[@]}" >"$LOG" 2>&1 &
SERVER_PID=$!
for _ in $(seq 50); do grep -q "port" "$LOG" 2>/dev/null && [[ $(grep -c " port " "$LOG") -ge ${#SYSTEMS[@]} ]] && break; sleep 0.2; done
grep " port " "$LOG" | sed 's/^ *//' >"$OUT/capture_ports.txt"
echo "server ports:"; cat "$OUT/capture_ports.txt"

tshark -i "$IFACE" -f "tcp" -w "$PCAP" -q 2>"$OUT/.tshark.log" &
TSHARK_PID=$!
sleep 2
if ! kill -0 "$TSHARK_PID" 2>/dev/null; then
  cat "$OUT/.tshark.log"; rm -f "$OUT/.tshark.log"
  echo "tshark could not capture on $IFACE (on macOS: open Wireshark once, allow ChmodBPF, log out and in)"; exit 1
fi

python -m sayonce.bench.remote run --host 127.0.0.1 --systems "${SYSTEMS[@]}" --context-kb "$CTX" \
    --rounds "$ROUNDS" --repeats 1 --label loopback-capture --out "$OUT/capture_run.csv"

sleep 1
kill "$TSHARK_PID"; wait "$TSHARK_PID" 2>/dev/null || true; TSHARK_PID=
rm -f "$OUT/.tshark.log"

tshark -r "$PCAP" -q -z conv,tcp >"$OUT/capture_conversations.txt"
echo
cat "$OUT/capture_conversations.txt"
echo "Done: $PCAP (open it in Wireshark), ports in $OUT/capture_ports.txt"
