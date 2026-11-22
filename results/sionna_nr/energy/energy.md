# Radio energy per session (RRC model)

Model and parameters: Huang et al., MobiSys 2012 (see `sayonce/bench/energy.py`).
`gap` = time between rounds (agent thinking). Energy is for the whole session,
including the setup round and the final tail. Idle power is not included.

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 65.55 | 52.96 | 12.59 | 52.2 | – |
| jsonrpc-gzip | 30.75 | 18.16 | 12.59 | 25.7 | -53% |
| cbor-full | 56.24 | 43.65 | 12.59 | 45.1 | -14% |
| json-delta | 19.77 | 7.19 | 12.59 | 17.3 | -70% |
| sayonce | 15.65 | 3.06 | 12.59 | 14.2 | -76% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 105.83 | 52.96 | 52.87 | 90.2 | – |
| jsonrpc-gzip | 71.03 | 18.16 | 52.87 | 63.7 | -33% |
| cbor-full | 96.52 | 43.65 | 52.87 | 83.1 | -9% |
| json-delta | 60.05 | 7.19 | 52.87 | 55.3 | -43% |
| sayonce | 55.93 | 3.06 | 52.87 | 52.2 | -47% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 166.25 | 52.96 | 113.29 | 147.2 | – |
| jsonrpc-gzip | 131.45 | 18.16 | 113.29 | 120.7 | -21% |
| cbor-full | 156.94 | 43.65 | 113.29 | 140.1 | -6% |
| json-delta | 120.47 | 7.19 | 113.29 | 112.3 | -28% |
| sayonce | 116.35 | 3.06 | 113.29 | 109.2 | -30% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 304.67 | 52.96 | 251.71 | 277.1 | – |
| jsonrpc-gzip | 269.87 | 18.16 | 251.71 | 250.6 | -11% |
| cbor-full | 295.36 | 43.65 | 251.71 | 270.0 | -3% |
| json-delta | 258.90 | 7.19 | 251.71 | 242.2 | -15% |
| sayonce | 254.77 | 3.06 | 251.71 | 239.1 | -16% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 404.90 | 392.31 | 12.59 | 310.5 | – |
| jsonrpc-gzip | 89.38 | 76.80 | 12.59 | 70.3 | -78% |
| cbor-full | 337.39 | 324.80 | 12.59 | 259.1 | -17% |
| json-delta | 36.83 | 24.24 | 12.59 | 30.3 | -91% |
| sayonce | 18.88 | 6.30 | 12.59 | 16.7 | -95% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 445.18 | 392.31 | 52.87 | 348.5 | – |
| jsonrpc-gzip | 129.66 | 76.80 | 52.87 | 108.3 | -71% |
| cbor-full | 377.67 | 324.80 | 52.87 | 297.1 | -15% |
| json-delta | 77.11 | 24.24 | 52.87 | 68.3 | -83% |
| sayonce | 59.16 | 6.30 | 52.87 | 54.7 | -87% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 505.60 | 392.31 | 113.29 | 405.5 | – |
| jsonrpc-gzip | 190.08 | 76.80 | 113.29 | 165.3 | -62% |
| cbor-full | 438.09 | 324.80 | 113.29 | 354.1 | -13% |
| json-delta | 137.53 | 24.24 | 113.29 | 125.3 | -73% |
| sayonce | 119.58 | 6.30 | 113.29 | 111.7 | -76% |

## nr-p10 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 644.02 | 392.31 | 251.71 | 535.4 | – |
| jsonrpc-gzip | 328.51 | 76.80 | 251.71 | 295.2 | -49% |
| cbor-full | 576.51 | 324.80 | 251.71 | 484.0 | -10% |
| json-delta | 275.95 | 24.24 | 251.71 | 255.2 | -57% |
| sayonce | 258.00 | 6.30 | 251.71 | 241.5 | -60% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 15.63 | 3.05 | 12.59 | 13.4 | – |
| jsonrpc-gzip | 14.38 | 1.79 | 12.59 | 13.0 | -8% |
| cbor-full | 15.33 | 2.74 | 12.59 | 13.3 | -2% |
| json-delta | 14.00 | 1.41 | 12.59 | 12.9 | -10% |
| sayonce | 13.89 | 1.30 | 12.59 | 12.8 | -11% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 55.91 | 3.05 | 52.87 | 51.4 | – |
| jsonrpc-gzip | 54.66 | 1.79 | 52.87 | 51.0 | -2% |
| cbor-full | 55.61 | 2.74 | 52.87 | 51.3 | -1% |
| json-delta | 54.28 | 1.41 | 52.87 | 50.9 | -3% |
| sayonce | 54.17 | 1.30 | 52.87 | 50.8 | -3% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 116.33 | 3.05 | 113.29 | 108.4 | – |
| jsonrpc-gzip | 115.08 | 1.79 | 113.29 | 108.0 | -1% |
| cbor-full | 116.03 | 2.74 | 113.29 | 108.3 | -0% |
| json-delta | 114.70 | 1.41 | 113.29 | 107.9 | -1% |
| sayonce | 114.59 | 1.30 | 113.29 | 107.8 | -2% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 254.76 | 3.05 | 251.71 | 238.3 | – |
| jsonrpc-gzip | 253.50 | 1.79 | 251.71 | 237.9 | -0% |
| cbor-full | 254.45 | 2.74 | 251.71 | 238.2 | -0% |
| json-delta | 253.12 | 1.41 | 251.71 | 237.8 | -1% |
| sayonce | 253.01 | 1.30 | 251.71 | 237.7 | -1% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 28.21 | 15.62 | 12.59 | 18.1 | – |
| jsonrpc-gzip | 16.70 | 4.11 | 12.59 | 13.9 | -41% |
| cbor-full | 25.86 | 13.28 | 12.59 | 17.3 | -8% |
| json-delta | 14.71 | 2.12 | 12.59 | 13.2 | -48% |
| sayonce | 14.09 | 1.50 | 12.59 | 12.9 | -50% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 68.49 | 15.62 | 52.87 | 56.1 | – |
| jsonrpc-gzip | 56.98 | 4.11 | 52.87 | 51.9 | -17% |
| cbor-full | 66.14 | 13.28 | 52.87 | 55.3 | -3% |
| json-delta | 54.99 | 2.12 | 52.87 | 51.2 | -20% |
| sayonce | 54.37 | 1.50 | 52.87 | 50.9 | -21% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 128.91 | 15.62 | 113.29 | 113.1 | – |
| jsonrpc-gzip | 117.40 | 4.11 | 113.29 | 108.9 | -9% |
| cbor-full | 126.56 | 13.28 | 113.29 | 112.3 | -2% |
| json-delta | 115.41 | 2.12 | 113.29 | 108.2 | -10% |
| sayonce | 114.79 | 1.50 | 113.29 | 107.9 | -11% |

## nr-p50 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 267.33 | 15.62 | 251.71 | 242.9 | – |
| jsonrpc-gzip | 255.82 | 4.11 | 251.71 | 238.8 | -4% |
| cbor-full | 264.99 | 13.28 | 251.71 | 242.1 | -1% |
| json-delta | 253.83 | 2.12 | 251.71 | 238.0 | -5% |
| sayonce | 253.21 | 1.50 | 251.71 | 237.8 | -5% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 14.79 | 2.20 | 12.59 | 12.8 | – |
| jsonrpc-gzip | 14.09 | 1.51 | 12.59 | 12.8 | -5% |
| cbor-full | 14.61 | 2.03 | 12.59 | 12.8 | -1% |
| json-delta | 13.91 | 1.33 | 12.59 | 12.8 | -6% |
| sayonce | 13.85 | 1.27 | 12.59 | 12.8 | -6% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 55.07 | 2.20 | 52.87 | 50.8 | – |
| jsonrpc-gzip | 54.37 | 1.51 | 52.87 | 50.8 | -1% |
| cbor-full | 54.89 | 2.03 | 52.87 | 50.8 | -0% |
| json-delta | 54.19 | 1.33 | 52.87 | 50.8 | -2% |
| sayonce | 54.13 | 1.27 | 52.87 | 50.8 | -2% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 115.49 | 2.20 | 113.29 | 107.8 | – |
| jsonrpc-gzip | 114.79 | 1.51 | 113.29 | 107.8 | -1% |
| cbor-full | 115.31 | 2.03 | 113.29 | 107.8 | -0% |
| json-delta | 114.61 | 1.33 | 113.29 | 107.8 | -1% |
| sayonce | 114.55 | 1.27 | 113.29 | 107.8 | -1% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 253.91 | 2.20 | 251.71 | 237.7 | – |
| jsonrpc-gzip | 253.22 | 1.51 | 251.71 | 237.7 | -0% |
| cbor-full | 253.74 | 2.03 | 251.71 | 237.7 | -0% |
| json-delta | 253.04 | 1.33 | 251.71 | 237.7 | -0% |
| sayonce | 252.98 | 1.27 | 251.71 | 237.7 | -0% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 21.80 | 9.21 | 12.59 | 13.1 | – |
| jsonrpc-gzip | 15.43 | 2.85 | 12.59 | 12.9 | -29% |
| cbor-full | 20.52 | 7.94 | 12.59 | 13.1 | -6% |
| json-delta | 14.35 | 1.76 | 12.59 | 12.9 | -34% |
| sayonce | 14.01 | 1.42 | 12.59 | 12.9 | -36% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 62.08 | 9.21 | 52.87 | 51.1 | – |
| jsonrpc-gzip | 55.71 | 2.85 | 52.87 | 50.9 | -10% |
| cbor-full | 60.80 | 7.94 | 52.87 | 51.1 | -2% |
| json-delta | 54.63 | 1.76 | 52.87 | 50.9 | -12% |
| sayonce | 54.29 | 1.42 | 52.87 | 50.9 | -13% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 122.50 | 9.21 | 113.29 | 108.1 | – |
| jsonrpc-gzip | 116.13 | 2.85 | 113.29 | 107.9 | -5% |
| cbor-full | 121.22 | 7.94 | 113.29 | 108.1 | -1% |
| json-delta | 115.05 | 1.76 | 113.29 | 107.9 | -6% |
| sayonce | 114.71 | 1.42 | 113.29 | 107.9 | -6% |

## nr-p90 (LTE parameters (Huang 2012) on the NR link), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 260.92 | 9.21 | 251.71 | 238.0 | – |
| jsonrpc-gzip | 254.56 | 2.85 | 251.71 | 237.8 | -2% |
| cbor-full | 259.65 | 7.94 | 251.71 | 238.0 | -0% |
| json-delta | 253.47 | 1.76 | 251.71 | 237.8 | -3% |
| sayonce | 253.13 | 1.42 | 251.71 | 237.8 | -3% |
