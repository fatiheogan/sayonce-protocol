# Wireshark screenshots (loopback capture)

Capture: `results/real/capture.pcapng`, made with `scripts/capture_lo0.sh`
(macOS lo0, `mcp` workload, 10 KB context, 5 rounds). Ports:
`results/real/capture_ports.txt` (JSON-RPC 51409, SayOnce 51410; 7480 is the
benchmark control port).

| file | what it shows |
|---|---|
| `1_jsonrpc_tcp_stream.png` / `.txt` | Follow TCP Stream on port 51409. Every POST carries the system prompt and all 13 tool definitions again; Content-Length grows 10,801 → 11,155 → 11,492 → 11,834 → 12,148 bytes while each reply is 376 bytes. Entire conversation: 60 kB. |
| `2_sayonce_tcp_stream.png` / `.txt` | Follow TCP Stream on port 51410. One zstd-compressed HELLO (the unreadable block) carries the context once; after that each message holds only the new step and the changed variable. Entire conversation: 5,028 bytes. |
| `2b_sayonce_packets.png` | SayOnce packet list: HELLO `Len=3247`, then requests of 142-153 bytes and replies of 245 bytes; hex view of one 148-byte request. |
| `3_tcp_conversations.png` | Statistics → Conversations → TCP: port 51409 (JSON-RPC) 28 packets, 63 kB; port 51410 (SayOnce) 34 packets, 7 kB, including TCP/IP headers. |

Wire bytes (Conversations) include TCP/IP headers, so they are slightly
larger than the application bytes in `capture_run.csv`.
