# Radio energy per session (RRC model)

Model and parameters: Huang et al., MobiSys 2012 (see `sayonce/bench/energy.py`).
`gap` = time between rounds (agent thinking). Energy is for the whole session,
including the setup round and the final tail. Idle power is not included.

## 3g (3G), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 13.23 | 6.35 | 6.89 | 14.0 | – |
| jsonrpc-gzip | 11.10 | 4.21 | 6.89 | 12.9 | -16% |
| cbor-full | 12.80 | 5.91 | 6.89 | 13.8 | -3% |
| json-delta | 9.87 | 2.98 | 6.89 | 12.1 | -25% |
| sayonce | 9.67 | 2.79 | 6.89 | 12.0 | -27% |

## 3g (3G), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 43.78 | 6.35 | 37.43 | 52.0 | – |
| jsonrpc-gzip | 41.64 | 4.21 | 37.43 | 50.9 | -5% |
| cbor-full | 43.35 | 5.91 | 37.43 | 51.8 | -1% |
| json-delta | 40.42 | 2.98 | 37.43 | 50.1 | -8% |
| sayonce | 40.22 | 2.79 | 37.43 | 50.0 | -8% |

## 3g (3G), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 89.60 | 6.35 | 83.26 | 109.0 | – |
| jsonrpc-gzip | 87.47 | 4.21 | 83.26 | 107.9 | -2% |
| cbor-full | 89.17 | 5.91 | 83.26 | 108.8 | -0% |
| json-delta | 86.24 | 2.98 | 83.26 | 107.1 | -4% |
| sayonce | 86.05 | 2.79 | 83.26 | 107.0 | -4% |

## 3g (3G), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 144.06 | 6.35 | 137.72 | 178.7 | – |
| jsonrpc-gzip | 141.93 | 4.21 | 137.72 | 177.7 | -1% |
| cbor-full | 143.63 | 5.91 | 137.72 | 178.5 | -0% |
| json-delta | 140.70 | 2.98 | 137.72 | 176.8 | -2% |
| sayonce | 140.50 | 2.79 | 137.72 | 176.7 | -2% |

## 3g (3G), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 32.59 | 25.71 | 6.89 | 22.0 | – |
| jsonrpc-gzip | 16.97 | 10.08 | 6.89 | 15.7 | -48% |
| cbor-full | 29.62 | 22.74 | 6.89 | 20.5 | -9% |
| json-delta | 11.18 | 4.30 | 6.89 | 12.9 | -66% |
| sayonce | 10.16 | 3.27 | 6.89 | 12.4 | -69% |

## 3g (3G), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 63.14 | 25.71 | 37.43 | 60.0 | – |
| jsonrpc-gzip | 47.51 | 10.08 | 37.43 | 53.7 | -25% |
| cbor-full | 60.17 | 22.74 | 37.43 | 58.5 | -5% |
| json-delta | 41.73 | 4.30 | 37.43 | 50.9 | -34% |
| sayonce | 40.70 | 3.27 | 37.43 | 50.4 | -36% |

## 3g (3G), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 108.96 | 25.71 | 83.26 | 117.0 | – |
| jsonrpc-gzip | 93.34 | 10.08 | 83.26 | 110.7 | -14% |
| cbor-full | 105.99 | 22.74 | 83.26 | 115.5 | -3% |
| json-delta | 87.55 | 4.30 | 83.26 | 107.9 | -20% |
| sayonce | 86.53 | 3.27 | 83.26 | 107.4 | -21% |

## 3g (3G), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 163.42 | 25.71 | 137.72 | 186.7 | – |
| jsonrpc-gzip | 147.80 | 10.08 | 137.72 | 180.4 | -10% |
| cbor-full | 160.45 | 22.74 | 137.72 | 185.3 | -2% |
| json-delta | 142.01 | 4.30 | 137.72 | 177.7 | -13% |
| sayonce | 140.98 | 3.27 | 137.72 | 177.1 | -14% |

## 4g (LTE), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 15.93 | 3.34 | 12.59 | 13.6 | – |
| jsonrpc-gzip | 15.06 | 2.48 | 12.59 | 13.5 | -5% |
| cbor-full | 15.68 | 3.09 | 12.59 | 13.5 | -2% |
| json-delta | 14.48 | 1.89 | 12.59 | 13.2 | -9% |
| sayonce | 14.41 | 1.83 | 12.59 | 13.2 | -9% |

## 4g (LTE), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 56.21 | 3.34 | 52.87 | 51.6 | – |
| jsonrpc-gzip | 55.34 | 2.48 | 52.87 | 51.5 | -2% |
| cbor-full | 55.96 | 3.09 | 52.87 | 51.5 | -0% |
| json-delta | 54.76 | 1.89 | 52.87 | 51.2 | -3% |
| sayonce | 54.69 | 1.83 | 52.87 | 51.2 | -3% |

## 4g (LTE), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 116.63 | 3.34 | 113.29 | 108.6 | – |
| jsonrpc-gzip | 115.76 | 2.48 | 113.29 | 108.5 | -1% |
| cbor-full | 116.38 | 3.09 | 113.29 | 108.5 | -0% |
| json-delta | 115.18 | 1.89 | 113.29 | 108.2 | -1% |
| sayonce | 115.11 | 1.83 | 113.29 | 108.2 | -1% |

## 4g (LTE), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 255.05 | 3.34 | 251.71 | 238.5 | – |
| jsonrpc-gzip | 254.19 | 2.48 | 251.71 | 238.4 | -0% |
| cbor-full | 254.80 | 3.09 | 251.71 | 238.4 | -0% |
| json-delta | 253.60 | 1.89 | 251.71 | 238.1 | -1% |
| sayonce | 253.54 | 1.83 | 251.71 | 238.1 | -1% |

## 4g (LTE), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 24.31 | 11.73 | 12.59 | 15.1 | – |
| jsonrpc-gzip | 17.68 | 5.10 | 12.59 | 14.1 | -27% |
| cbor-full | 22.84 | 10.26 | 12.59 | 14.7 | -6% |
| json-delta | 15.14 | 2.56 | 12.59 | 13.5 | -38% |
| sayonce | 14.63 | 2.05 | 12.59 | 13.3 | -40% |

## 4g (LTE), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 64.59 | 11.73 | 52.87 | 53.1 | – |
| jsonrpc-gzip | 57.96 | 5.10 | 52.87 | 52.1 | -10% |
| cbor-full | 63.12 | 10.26 | 52.87 | 52.7 | -2% |
| json-delta | 55.42 | 2.56 | 52.87 | 51.5 | -14% |
| sayonce | 54.91 | 2.05 | 52.87 | 51.3 | -15% |

## 4g (LTE), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 125.01 | 11.73 | 113.29 | 110.1 | – |
| jsonrpc-gzip | 118.38 | 5.10 | 113.29 | 109.1 | -5% |
| cbor-full | 123.54 | 10.26 | 113.29 | 109.7 | -1% |
| json-delta | 115.84 | 2.56 | 113.29 | 108.5 | -7% |
| sayonce | 115.33 | 2.05 | 113.29 | 108.3 | -8% |

## 4g (LTE), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 263.44 | 11.73 | 251.71 | 240.0 | – |
| jsonrpc-gzip | 256.80 | 5.10 | 251.71 | 239.0 | -3% |
| cbor-full | 261.97 | 10.26 | 251.71 | 239.6 | -1% |
| json-delta | 254.27 | 2.56 | 251.71 | 238.4 | -3% |
| sayonce | 253.76 | 2.05 | 251.71 | 238.2 | -4% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 24.75 | 17.86 | 6.89 | 28.0 | – |
| jsonrpc-gzip | 17.20 | 10.32 | 6.89 | 20.4 | -30% |
| cbor-full | 22.95 | 16.06 | 6.89 | 26.2 | -7% |
| json-delta | 13.48 | 6.60 | 6.89 | 16.5 | -46% |
| sayonce | 12.64 | 5.75 | 6.89 | 15.6 | -49% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 55.30 | 17.86 | 37.43 | 66.0 | – |
| jsonrpc-gzip | 47.75 | 10.32 | 37.43 | 58.4 | -14% |
| cbor-full | 53.50 | 16.06 | 37.43 | 64.2 | -3% |
| json-delta | 44.03 | 6.60 | 37.43 | 54.5 | -20% |
| sayonce | 43.19 | 5.75 | 37.43 | 53.6 | -22% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 101.12 | 17.86 | 83.26 | 123.0 | – |
| jsonrpc-gzip | 93.57 | 10.32 | 83.26 | 115.4 | -7% |
| cbor-full | 99.32 | 16.06 | 83.26 | 121.2 | -2% |
| json-delta | 89.85 | 6.60 | 83.26 | 111.5 | -11% |
| sayonce | 89.01 | 5.75 | 83.26 | 110.6 | -12% |

## edge (3G (3G values)), 10 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 155.58 | 17.86 | 137.72 | 192.8 | – |
| jsonrpc-gzip | 148.03 | 10.32 | 137.72 | 185.1 | -5% |
| cbor-full | 153.78 | 16.06 | 137.72 | 190.9 | -1% |
| json-delta | 144.31 | 6.60 | 137.72 | 181.3 | -7% |
| sayonce | 143.47 | 5.75 | 137.72 | 180.4 | -8% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 0 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 99.13 | 92.25 | 6.89 | 103.4 | – |
| jsonrpc-gzip | 38.27 | 31.38 | 6.89 | 41.7 | -61% |
| cbor-full | 88.34 | 81.46 | 6.89 | 92.3 | -11% |
| json-delta | 17.74 | 10.85 | 6.89 | 20.9 | -82% |
| sayonce | 14.06 | 7.17 | 6.89 | 17.1 | -86% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 2 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 129.68 | 92.25 | 37.43 | 141.4 | – |
| jsonrpc-gzip | 68.82 | 31.38 | 37.43 | 79.7 | -47% |
| cbor-full | 118.89 | 81.46 | 37.43 | 130.3 | -8% |
| json-delta | 48.29 | 10.85 | 37.43 | 58.9 | -63% |
| sayonce | 44.61 | 7.17 | 37.43 | 55.1 | -66% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 5 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 175.50 | 92.25 | 83.26 | 198.4 | – |
| jsonrpc-gzip | 114.64 | 31.38 | 83.26 | 136.7 | -35% |
| cbor-full | 164.71 | 81.46 | 83.26 | 187.3 | -6% |
| json-delta | 94.11 | 10.85 | 83.26 | 115.9 | -46% |
| sayonce | 90.43 | 7.17 | 83.26 | 112.1 | -48% |

## edge (3G (3G values)), 100 KB context, 20 rounds, gap 15 s

| system | energy (J) | transfer (J) | promotion + tail (J) | radio on (s) | vs JSON-RPC |
|---|---|---|---|---|---|
| jsonrpc | 229.96 | 92.25 | 137.72 | 268.1 | – |
| jsonrpc-gzip | 169.10 | 31.38 | 137.72 | 206.4 | -26% |
| cbor-full | 219.17 | 81.46 | 137.72 | 257.1 | -5% |
| json-delta | 148.57 | 10.85 | 137.72 | 185.7 | -35% |
| sayonce | 144.89 | 7.17 | 137.72 | 181.9 | -37% |
