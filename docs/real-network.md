# Measuring on real networks

The main network results come from an in-process emulator
(`sayonce.bench.netem`). This page describes two checks that do not rely on it:

1. **Kernel `tc netem`** on one Linux/WSL2 machine: the same delay, loss and
   bandwidth, applied by the operating system's network stack instead of our
   Python proxy. If the two agree, the emulator's results can be trusted.
2. **Two computers over a real link** (a phone's 4G connection): no emulation
   at all.

Both use the `mcp` workload (real MCP tool definitions) and write CSVs to
`results/real/`. `python -m sayonce.bench.validate` turns any set of these CSVs
into one comparison table.

## 1. Kernel tc netem (Linux or WSL2, about 25 minutes)

On Windows, use WSL2 (Ubuntu). In PowerShell, `wsl --install -d Ubuntu` if it
is not installed, and `wsl --update` so the kernel has netem. Then, inside
Ubuntu, work in the Linux home folder (not under `/mnt/c`, which is slow):

```bash
sudo apt update && sudo apt install -y iproute2 python3-venv git
git clone https://github.com/fatiheogan/sayonce-protocol.git
cd sayonce-protocol
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
scripts/netem_validate.sh          # QUICK=1 scripts/netem_validate.sh for a 10-minute run
```

The script asks for the sudo password (only `tc` needs it), runs the 4G, 3G,
EDGE and "100 ms delay, 2% loss" networks through both the emulator and
`tc netem`, always clears netem at the end, and writes
`results/real/validation.md`.

What to look for: the **JSON-RPC / SayOnce ratio** should be similar in both
columns. Absolute times can differ somewhat: the emulator models TCP loss
recovery with a simple rule (fast retransmit or a 200 ms timeout), while the
kernel runs real TCP. Note the differences in the report either way.

If you only want to shape the link by hand, see `scripts/netem.sh`.

### On macOS (Docker)

macOS has no `tc netem`, so the same script runs inside a Linux container.
Install and open Docker Desktop, then from the repository root:

```bash
scripts/netem_docker.sh            # QUICK=1 scripts/netem_docker.sh for a 10-minute run
```

The first run builds the image (`docker/netem.Dockerfile`, roughly 100 MB to
download). netem shapes the container's own loopback interface, so the Mac's
network is not touched, and the CSVs and `validation.md` appear in
`results/real/` on the Mac. Docker Desktop runs the container in a small Linux
VM, so note "Docker Desktop on macOS" next to the results in the report.

### Result (Docker Desktop on macOS, Apple silicon, 3 repeats)

Full tables: [`results/real/validation.md`](../results/real/validation.md).
How much longer a 20-round JSON-RPC conversation takes than SayOnce (median):

| network | context | emulator | kernel netem |
|---|---|---|---|
| 4G (30 ms, 1%, 20 Mbit/s) | 10 KB | 1.2x | 1.1x |
| 4G | 100 KB | 1.9x | 2.4x |
| 100 ms, 2% loss | 10 KB | 1.2x | 1.3x |
| 100 ms, 2% loss | 100 KB | 1.7x | 4.5x |
| EDGE (150 ms, 2%, 0.2 Mbit/s) | 10 KB | 2.7x | 2.9x |
| EDGE | 100 KB | 11.5x | 12.7x |

* Bytes and tokens are identical in both columns; only time depends on the
  network.
* SayOnce's own times agree within 1-10% between emulator and kernel.
* Where they differ, the kernel shows a **larger** SayOnce advantage: real
  TCP shrinks its congestion window and waits for timeouts after a loss, which
  hurts the 100 KB JSON-RPC messages far more than the emulator's simple loss
  rule does (JSON-RPC at 100 ms/2%/100 KB: 8.3 s emulated, 24.3 s kernel).
  The emulator results in `results/final*` are therefore a conservative
  (lower) estimate of the latency gain.
* A first quick run with loopback's default 64 KB MTU sent a 100 KB message in
  two packets, so netem loss hardly hit JSON-RPC and the two systems looked
  equal; `scripts/netem.sh` now sets a 1500-byte MTU, as on a real link.

## 2. Two computers over 4G

`sayonce.bench.remote` runs the same benchmark with the server on one computer
and the client on the other, so every request crosses the real link.

### Which link is actually measured

- **Both laptops on the same phone hotspot:** traffic goes laptop → phone →
  laptop over Wi-Fi and **never uses the 4G network**. This measures the
  phone's Wi-Fi tethering (a few ms RTT), not a mobile network. Label it
  `hotspot-local` if you run it.
- **Client on the phone hotspot, server somewhere else** (home or campus
  Wi-Fi): traffic crosses the 4G radio link and the internet. This is the
  mobile measurement. Both sides are behind NAT, so the client cannot reach
  the server directly; [Tailscale](https://tailscale.com) (free) connects the
  two laptops with a private `100.x.y.z` address. It adds a WireGuard header to
  every packet, the same for all systems.

### Steps (two laptops, about 15 minutes, roughly 30 MB of mobile data)

On **both** laptops: pull the latest `main`, activate `.venv`, and run
`pip install -e ".[dev]"`. Install Tailscale and sign in with the same account
(or share the device) so both appear in the Tailscale admin page.

**Server laptop** (home or campus Wi-Fi):

```bash
python -m sayonce.bench.remote serve
```

It prints its ports. Its Tailscale address is shown by `tailscale ip -4`.
Allow Python through the firewall on private networks if Windows asks.

**Client laptop** (connected to the phone's hotspot, phone on 4G/LTE mobile data):

```bash
python -m sayonce.bench.remote run --host <server's 100.x.y.z> --label 4g --out results/real/remote_4g.csv
```

Optionally repeat once with the client on ordinary Wi-Fi for a reference:

```bash
python -m sayonce.bench.remote run --host <server's 100.x.y.z> --label wifi --out results/real/remote_wifi.csv
```

Then compare everything:

```bash
python -m sayonce.bench.validate emulator='results/real/emu_*.csv' netem='results/real/netem_*.csv' \
    real='results/real/remote_*.csv' --out results/real/validation.md
```

The `.meta.json` next to each remote CSV records the measured RTT before and
after the run. Write down the phone model, operator, signal (bars or RSRP from
the phone's status page) and location in the report; mobile links vary a lot
from minute to minute, so run the comparison back to back and keep the 3
repeats.

### Wireshark

While the remote run is going, capture on the client laptop's **Tailscale**
interface (on the Wi-Fi interface the traffic is encrypted by WireGuard) with the filter
`tcp.port == <sayonce port>` (printed by the server) to show one large HELLO
followed by small messages, and `tcp.port == <jsonrpc port>` to show the full
context in every request. One screenshot of each is enough for the report.
