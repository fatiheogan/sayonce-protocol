"""Minimal HTTP/1.1 client and server for the JSON baselines.

Written by hand (instead of aiohttp) so that every byte is visible and counted,
with header bytes and body bytes tracked separately. Headers mimic what a
typical MCP-over-HTTP client and server send. Connections are kept alive,
which is the favourable case for HTTP.
"""

from __future__ import annotations

import asyncio
import gzip
from dataclasses import dataclass
from email.utils import formatdate
from typing import Awaitable, Callable

try:
    import zstandard
except ImportError:  # optional, only needed for the zstd baseline
    zstandard = None

CLIENT_HEADERS = {
    "User-Agent": "sayonce-bench/0.1 (python-httpx-like)",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "Mcp-Protocol-Version": "2025-06-18",
    "Connection": "keep-alive",
}
SERVER_HEADERS = {
    "Server": "uvicorn",
    "Content-Type": "application/json",
}


@dataclass
class HttpStats:
    header_bytes_sent: int = 0
    body_bytes_sent: int = 0
    header_bytes_received: int = 0
    body_bytes_received: int = 0

    @property
    def bytes_sent(self) -> int:
        return self.header_bytes_sent + self.body_bytes_sent

    @property
    def bytes_received(self) -> int:
        return self.header_bytes_received + self.body_bytes_received


# ----------------------------------------------------------------- compression


def compress(data: bytes, encoding: str | None) -> bytes:
    if encoding is None:
        return data
    if encoding == "gzip":
        return gzip.compress(data, compresslevel=6, mtime=0)
    if encoding == "zstd":
        if zstandard is None:
            raise RuntimeError("pip install zstandard to use the zstd baseline")
        return zstandard.ZstdCompressor(level=3).compress(data)
    raise ValueError(f"unknown encoding {encoding!r}")


def decompress(data: bytes, encoding: str | None) -> bytes:
    if not encoding or encoding == "identity":
        return data
    if encoding == "gzip":
        return gzip.decompress(data)
    if encoding == "zstd":
        if zstandard is None:
            raise RuntimeError("pip install zstandard to use the zstd baseline")
        return zstandard.ZstdDecompressor().decompress(data)
    raise ValueError(f"unknown encoding {encoding!r}")


# ----------------------------------------------------------------- wire helpers


async def _read_message(reader: asyncio.StreamReader) -> tuple[str, dict[str, str], bytes, int]:
    """Read one HTTP message. Returns (start line, headers, body, header byte count)."""
    head = await reader.readuntil(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    start = lines[0]
    headers = {}
    for line in lines[1:]:
        if line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    length = int(headers.get("content-length", "0"))
    body = await reader.readexactly(length) if length else b""
    return start, headers, body, len(head)


def _build(start: str, headers: dict[str, str], body: bytes) -> tuple[bytes, int]:
    lines = [start] + [f"{k}: {v}" for k, v in headers.items()] + [f"Content-Length: {len(body)}", "", ""]
    head = "\r\n".join(lines).encode("latin-1")
    return head + body, len(head)


# ----------------------------------------------------------------- client


class HttpClient:
    def __init__(self, host: str, port: int, encoding: str | None = None):
        self.host, self.port, self.encoding = host, port, encoding
        self.stats = HttpStats()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)

    async def post(self, path: str, body: bytes, extra_headers: dict[str, str] | None = None) -> tuple[int, bytes]:
        assert self._reader and self._writer, "call connect() first"
        headers = {"Host": f"{self.host}:{self.port}", **CLIENT_HEADERS, **(extra_headers or {})}
        if self.encoding:
            headers["Content-Encoding"] = self.encoding
            headers["Accept-Encoding"] = self.encoding
        payload = compress(body, self.encoding)
        data, head_len = _build(f"POST {path} HTTP/1.1", headers, payload)
        self._writer.write(data)
        await self._writer.drain()
        self.stats.header_bytes_sent += head_len
        self.stats.body_bytes_sent += len(payload)

        start, rheaders, rbody, rhead_len = await _read_message(self._reader)
        self.stats.header_bytes_received += rhead_len
        self.stats.body_bytes_received += len(rbody)
        status = int(start.split(" ", 2)[1])
        return status, decompress(rbody, rheaders.get("content-encoding"))

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError):
                pass


# ----------------------------------------------------------------- server

Route = Callable[[str, dict[str, str], bytes], Awaitable[tuple[int, bytes, dict[str, str]]]]


class HttpServer:
    """Calls route(path, headers, body) for every POST and returns its answer."""

    def __init__(self, route: Route, host: str = "127.0.0.1", port: int = 0):
        self.route, self.host, self.port = route, host, port
        self._server: asyncio.base_events.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> "HttpServer":
        self._server = await asyncio.start_server(self._on_connection, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def close(self) -> None:
        for w in list(self._writers):
            w.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        try:
            while True:
                try:
                    start, headers, body, _ = await _read_message(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    return
                path = start.split(" ")[1]
                encoding = headers.get("content-encoding")
                status, out, extra = await self.route(path, headers, decompress(body, encoding))
                rheaders = {"Date": formatdate(usegmt=True), **SERVER_HEADERS, **extra}
                if encoding:
                    rheaders["Content-Encoding"] = encoding
                    out = compress(out, encoding)
                reason = {200: "OK", 400: "Bad Request", 404: "Not Found", 409: "Conflict"}.get(status, "OK")
                data, _ = _build(f"HTTP/1.1 {status} {reason}", rheaders, out)
                writer.write(data)
                await writer.drain()
        finally:
            self._writers.discard(writer)
            writer.close()
