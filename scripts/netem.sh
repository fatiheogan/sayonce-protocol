#!/usr/bin/env bash
# Kernel-level network emulation on the loopback interface with tc netem.
# Linux only (on Windows: run inside WSL2). Needs root (sudo).
#
#   sudo scripts/netem.sh apply DELAY_MS LOSS_PERCENT RATE_MBIT   # e.g. 75 2 2
#   sudo scripts/netem.sh profile 3g                              # same profiles as the Python emulator
#   sudo scripts/netem.sh show
#   sudo scripts/netem.sh clear
#
# Then run the harness with --external-netem so it records the conditions
# without starting its own proxy, e.g.:
#
#   sudo scripts/netem.sh profile 3g
#   python -m sayonce.bench.harness --network 3g --external-netem --out results/netem_3g.csv
#   sudo scripts/netem.sh clear
#
# Notes
# * netem on "lo" delays every packet, in both directions, so the delay is
#   one-way and RTT = 2 x DELAY_MS (same meaning as the Python emulator).
# * It affects ALL loopback traffic on the machine while active. Always clear it.
# * Loss here is real packet loss; Linux TCP retransmits, so it shows up as delay.

set -euo pipefail
DEV="${DEV:-lo}"

usage() { sed -n '2,23p' "$0"; exit 1; }

apply() {
  local delay="$1" loss="$2" rate="$3"
  tc qdisc del dev "$DEV" root 2>/dev/null || true
  local args=(delay "${delay}ms")
  [[ "$loss" != "0" ]] && args+=(loss "${loss}%")
  [[ "$rate" != "0" ]] && args+=(rate "${rate}mbit")
  tc qdisc add dev "$DEV" root netem "${args[@]}"
  echo "netem on $DEV: delay ${delay}ms loss ${loss}% rate ${rate}mbit (0 = unlimited)"
}

# keep in sync with sayonce/bench/netem.py PROFILES (delay_ms loss_% rate_mbit)
profile() {
  case "$1" in
    lan)       apply 1 0 1000 ;;
    wifi)      apply 10 0.5 50 ;;
    4g)        apply 30 1 20 ;;
    3g)        apply 75 2 2 ;;
    edge)      apply 150 2 0.2 ;;
    satellite) apply 300 0.5 10 ;;
    *) echo "unknown profile $1 (lan wifi 4g 3g edge satellite)"; exit 1 ;;
  esac
}

[[ $# -ge 1 ]] || usage
case "$1" in
  apply)   [[ $# -eq 4 ]] || usage; apply "$2" "$3" "$4" ;;
  profile) [[ $# -eq 2 ]] || usage; profile "$2" ;;
  show)    tc qdisc show dev "$DEV" ;;
  clear)   tc qdisc del dev "$DEV" root 2>/dev/null || true; echo "netem cleared on $DEV" ;;
  *)       usage ;;
esac
