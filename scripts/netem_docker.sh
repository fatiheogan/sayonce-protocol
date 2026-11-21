#!/usr/bin/env bash
# Run the kernel tc netem validation inside a Linux container.
# For macOS (and any machine with Docker but no netem). Needs Docker Desktop running.
#
#   scripts/netem_docker.sh            # about 25 minutes
#   QUICK=1 scripts/netem_docker.sh    # 1 repeat, about 10 minutes
#
# netem shapes the container's own loopback interface, so nothing on the host
# is affected. Results are written to results/real/ on the host, the same files
# scripts/netem_validate.sh writes on Linux/WSL2.

set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=sayonce-netem

command -v docker >/dev/null || { echo "docker not found: install Docker Desktop"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker is not running: open Docker Desktop and wait for it to start"; exit 1; }

docker build -t "$IMAGE" -f docker/netem.Dockerfile .

mkdir -p results/real
# NET_ADMIN lets tc change the container's network settings.
docker run --rm --cap-add=NET_ADMIN \
  -e QUICK="${QUICK:-0}" \
  -v "$PWD/results/real:/app/results/real" \
  "$IMAGE"

echo "Done: results/real/validation.md"
