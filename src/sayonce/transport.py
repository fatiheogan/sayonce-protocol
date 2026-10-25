"""Framed connection over an asyncio byte stream (TCP), spec section 3.

Counts every byte that goes over the wire so benchmarks can read the numbers
directly. A fault hook lets tests drop or modify outgoing frames to exercise
RESYNC (spec 5.7).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from .codec import DEFAULT_COMPRESS_THRESHOLD, Frame, FrameDecoder, encode_frame

# A fault hook receives an outgoing frame and returns the frame to send,
# or None to drop it silently.
FaultHook = Callable[[Frame], "Frame | None"]


@dataclass
class WireStats:
    bytes_sent: int = 0
    bytes_received: int = 0
    frames_sent: int = 0
    frames_received: int = 0
    frames_dropped: int = 0

    @property
    def bytes_total(self) -> int:
        return self.bytes_sent + self.bytes_received


class ConnectionClosed(Exception):
    pass


class FramedConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, read_size: int = 65536):
        self._reader = reader
        self._writer = writer
        self._decoder = FrameDecoder()
        self._pending: list[Frame] = []
        self._read_size = read_size
        self.stats = WireStats()
        self.fault: FaultHook | None = None
        # Frames at least this large are zstd-compressed (spec 3.2). None disables it.
        self.compress_threshold: int | None = DEFAULT_COMPRESS_THRESHOLD

    @classmethod
    async def connect(cls, host: str, port: int) -> "FramedConnection":
        reader, writer = await asyncio.open_connection(host, port)
        return cls(reader, writer)

    async def send(self, frame: Frame) -> int:
        """Send one frame. Returns the number of bytes written (0 if dropped)."""
        if self.fault is not None:
            out = self.fault(frame)
            if out is None:
                self.stats.frames_dropped += 1
                return 0
            frame = out
        data = encode_frame(frame, self.compress_threshold)
        self._writer.write(data)
        await self._writer.drain()
        self.stats.bytes_sent += len(data)
        self.stats.frames_sent += 1
        return len(data)

    async def recv(self) -> Frame:
        """Wait for the next complete frame."""
        while not self._pending:
            data = await self._reader.read(self._read_size)
            if not data:
                raise ConnectionClosed("peer closed the connection")
            self.stats.bytes_received += len(data)
            self._pending.extend(self._decoder.feed(data))
        self.stats.frames_received += 1
        return self._pending.pop(0)

    async def close(self) -> None:
        if not self._writer.is_closing():
            self._writer.close()
        try:
            await self._writer.wait_closed()
        except (ConnectionError, OSError):
            pass
