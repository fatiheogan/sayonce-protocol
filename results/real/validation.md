# Network validation

Median total time of one conversation (setup + all rounds) over the repeats, with the range in brackets. Lower is better.

## 3g, 10 KB context

| system | emulator | netem | difference |
|---|---|---|---|
| jsonrpc | 5.25 s (4.96-5.34) | 6.60 s (4.61-6.72) | +26% |
| jsonrpc-gzip | 4.40 s (4.27-4.40) | 4.33 s (4.25-4.40) | -2% |
| json-delta | 3.54 s (3.53-3.87) | 3.66 s (3.64-4.02) | +3% |
| sayonce | 3.45 s (3.43-3.78) | 3.57 s (3.56-4.34) | +4% |

JSON-RPC takes longer than SayOnce by emulator: 1.5x, netem: 1.8x.

## 3g, 100 KB context

| system | emulator | netem | difference |
|---|---|---|---|
| jsonrpc | 13.62 s (13.27-13.82) | 22.21 s (21.27-26.14) | +63% |
| jsonrpc-gzip | 6.58 s (6.03-7.54) | 7.89 s (6.89-8.05) | +20% |
| json-delta | 4.35 s (4.08-4.84) | 4.42 s (4.39-4.43) | +2% |
| sayonce | 3.90 s (3.60-3.92) | 4.62 s (4.21-5.16) | +18% |

JSON-RPC takes longer than SayOnce by emulator: 3.5x, netem: 4.8x.

## 4g, 10 KB context

| system | emulator | netem | real |
|---|---|---|---|
| jsonrpc | 1.87 s (1.80-2.05) | 1.90 s (1.81-2.56) | 3.09 s (2.61-4.71) |
| jsonrpc-gzip | 1.78 s (1.48-1.99) | 1.49 s (1.48-1.62) | 2.71 s (2.61-5.33) |
| cbor-full | - | - | 6.60 s (3.10-7.00) |
| json-delta | 1.52 s (1.51-1.77) | 1.55 s (1.53-1.82) | 3.11 s (2.32-3.35) |
| sayonce | 1.53 s (1.49-1.75) | 1.79 s (1.51-2.06) | 4.09 s (3.08-4.19) |

JSON-RPC takes longer than SayOnce by emulator: 1.2x, netem: 1.1x, real: 0.8x.

## 4g, 100 KB context

| system | emulator | netem | real |
|---|---|---|---|
| jsonrpc | 3.07 s (3.02-3.56) | 4.12 s (3.46-6.36) | 15.64 s (13.78-23.71) |
| jsonrpc-gzip | 2.43 s (2.06-2.63) | 1.95 s (1.88-3.17) | 7.81 s (4.05-8.79) |
| cbor-full | - | - | 14.80 s (12.56-17.52) |
| json-delta | 1.69 s (1.65-1.94) | 2.08 s (1.82-2.10) | 3.95 s (3.07-4.22) |
| sayonce | 1.62 s (1.60-1.85) | 1.71 s (1.69-1.97) | 3.81 s (3.55-4.90) |

JSON-RPC takes longer than SayOnce by emulator: 1.9x, netem: 2.4x, real: 4.1x.

## d100ms_l2%_inf, 10 KB context

| system | emulator | netem | difference |
|---|---|---|---|
| jsonrpc | 5.49 s (5.32-5.93) | 6.11 s (5.19-6.76) | +11% |
| jsonrpc-gzip | 5.31 s (5.09-5.31) | 5.23 s (4.56-6.24) | -1% |
| json-delta | 4.52 s (4.49-4.95) | 5.22 s (4.96-5.69) | +15% |
| sayonce | 4.52 s (4.46-4.90) | 4.78 s (4.77-5.64) | +6% |

JSON-RPC takes longer than SayOnce by emulator: 1.2x, netem: 1.3x.

## d100ms_l2%_inf, 100 KB context

| system | emulator | netem | difference |
|---|---|---|---|
| jsonrpc | 8.31 s (7.70-8.90) | 24.34 s (18.02-32.06) | +193% |
| jsonrpc-gzip | 6.54 s (5.67-7.58) | 7.77 s (4.92-10.79) | +19% |
| json-delta | 5.14 s (4.75-5.55) | 6.60 s (6.16-7.55) | +28% |
| sayonce | 4.96 s (4.55-4.96) | 5.46 s (5.07-5.50) | +10% |

JSON-RPC takes longer than SayOnce by emulator: 1.7x, netem: 4.5x.

## edge, 10 KB context

| system | emulator | netem | difference |
|---|---|---|---|
| jsonrpc | 18.78 s (18.45-19.16) | 21.37 s (20.92-23.24) | +14% |
| jsonrpc-gzip | 11.33 s (11.24-11.39) | 10.61 s (10.60-11.32) | -6% |
| json-delta | 7.89 s (7.88-8.49) | 8.30 s (8.29-9.53) | +5% |
| sayonce | 6.96 s (6.95-7.55) | 7.34 s (7.33-7.36) | +6% |

JSON-RPC takes longer than SayOnce by emulator: 2.7x, netem: 2.9x.

## edge, 100 KB context

| system | emulator | netem | difference |
|---|---|---|---|
| jsonrpc | 96.27 s (95.61-97.42) | 107.11 s (104.33-112.39) | +11% |
| jsonrpc-gzip | 25.46 s (24.54-26.84) | 26.68 s (26.35-27.79) | +5% |
| json-delta | 12.48 s (11.91-13.20) | 14.12 s (13.23-16.49) | +13% |
| sayonce | 8.37 s (7.76-8.37) | 8.44 s (8.29-9.18) | +1% |

JSON-RPC takes longer than SayOnce by emulator: 11.5x, netem: 12.7x.

