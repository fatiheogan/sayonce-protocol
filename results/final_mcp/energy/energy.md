# Radio energy per session (RRC model)

Model and parameters: Huang et al., MobiSys 2012 (see `sayonce/bench/energy.py`).
`gap` = time between rounds (agent thinking). Energy is for the whole session,
including the setup round and the final tail. Idle power is not included.

## 3g (3G), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 13.05 | 6.16 | 6.89 | 13.8 | – |
| jsonrpc-gzip | 10.85 | 3.96 | 6.89 | 12.8 | -17% |
| cbor-full | 12.56 | 5.68 | 6.89 | 13.6 | -4% |
| json-delta | 9.87 | 2.98 | 6.89 | 12.1 | -24% |
| sayonce | 9.66 | 2.77 | 6.89 | 12.0 | -26% |

## 3g (3G), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 43.60 | 6.16 | 37.43 | 51.8 | – |
| jsonrpc-gzip | 41.40 | 3.96 | 37.43 | 50.8 | -5% |
| cbor-full | 43.11 | 5.68 | 37.43 | 51.6 | -1% |
| json-delta | 40.41 | 2.98 | 37.43 | 50.1 | -7% |
| sayonce | 40.21 | 2.77 | 37.43 | 50.0 | -8% |

## 3g (3G), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 89.42 | 6.16 | 83.26 | 108.8 | – |
| jsonrpc-gzip | 87.22 | 3.96 | 83.26 | 107.8 | -2% |
| cbor-full | 88.93 | 5.68 | 83.26 | 108.6 | -1% |
| json-delta | 86.24 | 2.98 | 83.26 | 107.1 | -4% |
| sayonce | 86.03 | 2.77 | 83.26 | 107.0 | -4% |

## 3g (3G), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 143.88 | 6.16 | 137.72 | 178.6 | – |
| jsonrpc-gzip | 141.68 | 3.96 | 137.72 | 177.5 | -2% |
| cbor-full | 143.39 | 5.68 | 137.72 | 178.4 | -0% |
| json-delta | 140.70 | 2.98 | 137.72 | 176.8 | -2% |
| sayonce | 140.49 | 2.77 | 137.72 | 176.7 | -2% |

## 3g (3G), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 32.92 | 26.03 | 6.89 | 22.1 | – |
| jsonrpc-gzip | 15.10 | 8.22 | 6.89 | 15.2 | -54% |
| cbor-full | 29.27 | 22.38 | 6.89 | 20.8 | -11% |
| json-delta | 11.23 | 4.35 | 6.89 | 13.0 | -66% |
| sayonce | 9.96 | 3.07 | 6.89 | 12.2 | -70% |

## 3g (3G), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 63.46 | 26.03 | 37.43 | 60.1 | – |
| jsonrpc-gzip | 45.65 | 8.22 | 37.43 | 53.2 | -28% |
| cbor-full | 59.82 | 22.38 | 37.43 | 58.8 | -6% |
| json-delta | 41.78 | 4.35 | 37.43 | 51.0 | -34% |
| sayonce | 40.51 | 3.07 | 37.43 | 50.2 | -36% |

## 3g (3G), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 109.29 | 26.03 | 83.26 | 117.1 | – |
| jsonrpc-gzip | 91.47 | 8.22 | 83.26 | 110.2 | -16% |
| cbor-full | 105.64 | 22.38 | 83.26 | 115.8 | -3% |
| json-delta | 87.60 | 4.35 | 83.26 | 108.0 | -20% |
| sayonce | 86.33 | 3.07 | 83.26 | 107.2 | -21% |

## 3g (3G), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 163.75 | 26.03 | 137.72 | 186.8 | – |
| jsonrpc-gzip | 145.93 | 8.22 | 137.72 | 179.9 | -11% |
| cbor-full | 160.10 | 22.38 | 137.72 | 185.5 | -2% |
| json-delta | 142.06 | 4.35 | 137.72 | 177.7 | -13% |
| sayonce | 140.79 | 3.07 | 137.72 | 177.0 | -14% |

## 4g (LTE), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 15.95 | 3.37 | 12.59 | 13.7 | – |
| jsonrpc-gzip | 14.96 | 2.38 | 12.59 | 13.4 | -6% |
| cbor-full | 15.68 | 3.10 | 12.59 | 13.6 | -2% |
| json-delta | 14.49 | 1.90 | 12.59 | 13.2 | -9% |
| sayonce | 14.41 | 1.82 | 12.59 | 13.2 | -10% |

## 4g (LTE), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 56.23 | 3.37 | 52.87 | 51.7 | – |
| jsonrpc-gzip | 55.24 | 2.38 | 52.87 | 51.4 | -2% |
| cbor-full | 55.96 | 3.10 | 52.87 | 51.6 | -0% |
| json-delta | 54.77 | 1.90 | 52.87 | 51.2 | -3% |
| sayonce | 54.69 | 1.82 | 52.87 | 51.2 | -3% |

## 4g (LTE), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 116.65 | 3.37 | 113.29 | 108.7 | – |
| jsonrpc-gzip | 115.66 | 2.38 | 113.29 | 108.4 | -1% |
| cbor-full | 116.38 | 3.10 | 113.29 | 108.6 | -0% |
| json-delta | 115.19 | 1.90 | 113.29 | 108.2 | -1% |
| sayonce | 115.11 | 1.82 | 113.29 | 108.2 | -1% |

## 4g (LTE), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 255.08 | 3.37 | 251.71 | 238.6 | – |
| jsonrpc-gzip | 254.09 | 2.38 | 251.71 | 238.3 | -0% |
| cbor-full | 254.81 | 3.10 | 251.71 | 238.5 | -0% |
| json-delta | 253.61 | 1.90 | 251.71 | 238.1 | -1% |
| sayonce | 253.53 | 1.82 | 251.71 | 238.1 | -1% |

## 4g (LTE), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 24.23 | 11.64 | 12.59 | 15.0 | – |
| jsonrpc-gzip | 17.01 | 4.42 | 12.59 | 14.1 | -30% |
| cbor-full | 22.90 | 10.31 | 12.59 | 14.9 | -5% |
| json-delta | 15.16 | 2.57 | 12.59 | 13.5 | -37% |
| sayonce | 14.60 | 2.01 | 12.59 | 13.3 | -40% |

## 4g (LTE), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 64.51 | 11.64 | 52.87 | 53.0 | – |
| jsonrpc-gzip | 57.29 | 4.42 | 52.87 | 52.1 | -11% |
| cbor-full | 63.18 | 10.31 | 52.87 | 52.9 | -2% |
| json-delta | 55.44 | 2.57 | 52.87 | 51.5 | -14% |
| sayonce | 54.88 | 2.01 | 52.87 | 51.3 | -15% |

## 4g (LTE), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 124.93 | 11.64 | 113.29 | 110.0 | – |
| jsonrpc-gzip | 117.71 | 4.42 | 113.29 | 109.1 | -6% |
| cbor-full | 123.60 | 10.31 | 113.29 | 109.9 | -1% |
| json-delta | 115.86 | 2.57 | 113.29 | 108.5 | -7% |
| sayonce | 115.30 | 2.01 | 113.29 | 108.3 | -8% |

## 4g (LTE), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 263.35 | 11.64 | 251.71 | 239.9 | – |
| jsonrpc-gzip | 256.13 | 4.42 | 251.71 | 239.0 | -3% |
| cbor-full | 262.02 | 10.31 | 251.71 | 239.8 | -1% |
| json-delta | 254.28 | 2.57 | 251.71 | 238.4 | -3% |
| sayonce | 253.72 | 2.01 | 251.71 | 238.2 | -4% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 24.19 | 17.30 | 6.89 | 27.4 | – |
| jsonrpc-gzip | 16.40 | 9.52 | 6.89 | 19.6 | -32% |
| cbor-full | 22.16 | 15.28 | 6.89 | 25.4 | -8% |
| json-delta | 13.47 | 6.59 | 6.89 | 16.5 | -44% |
| sayonce | 12.58 | 5.69 | 6.89 | 15.6 | -48% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 54.74 | 17.30 | 37.43 | 65.4 | – |
| jsonrpc-gzip | 46.95 | 9.52 | 37.43 | 57.6 | -14% |
| cbor-full | 52.71 | 15.28 | 37.43 | 63.4 | -4% |
| json-delta | 44.02 | 6.59 | 37.43 | 54.5 | -20% |
| sayonce | 43.13 | 5.69 | 37.43 | 53.6 | -21% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 100.56 | 17.30 | 83.26 | 122.4 | – |
| jsonrpc-gzip | 92.77 | 9.52 | 83.26 | 114.6 | -8% |
| cbor-full | 98.53 | 15.28 | 83.26 | 120.4 | -2% |
| json-delta | 89.84 | 6.59 | 83.26 | 111.5 | -11% |
| sayonce | 88.95 | 5.69 | 83.26 | 110.6 | -12% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 155.02 | 17.30 | 137.72 | 192.2 | – |
| jsonrpc-gzip | 147.23 | 9.52 | 137.72 | 184.3 | -5% |
| cbor-full | 152.99 | 15.28 | 137.72 | 190.1 | -1% |
| json-delta | 144.30 | 6.59 | 137.72 | 181.2 | -7% |
| sayonce | 143.41 | 5.69 | 137.72 | 180.3 | -7% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 100.58 | 93.70 | 6.89 | 104.8 | – |
| jsonrpc-gzip | 30.45 | 23.56 | 6.89 | 34.0 | -70% |
| cbor-full | 85.26 | 78.37 | 6.89 | 89.2 | -15% |
| json-delta | 17.87 | 10.99 | 6.89 | 21.1 | -82% |
| sayonce | 13.45 | 6.56 | 6.89 | 16.5 | -87% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 131.13 | 93.70 | 37.43 | 142.8 | – |
| jsonrpc-gzip | 61.00 | 23.56 | 37.43 | 72.0 | -53% |
| cbor-full | 115.81 | 78.37 | 37.43 | 127.2 | -12% |
| json-delta | 48.42 | 10.99 | 37.43 | 59.1 | -63% |
| sayonce | 44.00 | 6.56 | 37.43 | 54.5 | -66% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 176.95 | 93.70 | 83.26 | 199.8 | – |
| jsonrpc-gzip | 106.82 | 23.56 | 83.26 | 129.0 | -40% |
| cbor-full | 161.63 | 78.37 | 83.26 | 184.2 | -9% |
| json-delta | 94.24 | 10.99 | 83.26 | 116.1 | -47% |
| sayonce | 89.82 | 6.56 | 83.26 | 111.5 | -49% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 231.41 | 93.70 | 137.72 | 269.5 | – |
| jsonrpc-gzip | 161.28 | 23.56 | 137.72 | 198.7 | -30% |
| cbor-full | 216.09 | 78.37 | 137.72 | 254.0 | -7% |
| json-delta | 148.70 | 10.99 | 137.72 | 185.8 | -36% |
| sayonce | 144.28 | 6.56 | 137.72 | 181.2 | -38% |
