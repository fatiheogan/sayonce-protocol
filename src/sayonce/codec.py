"""Wire encoding for SayOnce: framing, CBOR, dictionary references and context hashing.

See docs/protocol.md sections 3, 5.5 and 6.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Any, Iterable

import cbor2
import zstandard

from .messages import MAX_FRAME_SIZE, PROTOCOL_VERSION, ErrorCode, MessageType

_LEN = struct.Struct(">I")
HASH_SIZE = 8

# Compressed frames (spec 3.2): CBOR tag wrapping the zstd-compressed frame bytes.
# Tag number from the CBOR first-come-first-served range; not registered (experimental).
TAG_ZSTD_FRAME = 4100
DEFAULT_COMPRESS_THRESHOLD = 1024  # bytes; smaller frames are sent as they are
_ZSTD_LEVEL = 3


class ProtocolError(Exception):
    """Raised when a frame cannot be decoded. Carries the ERROR code to send back."""

    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- frames


@dataclass
class Frame:
    """One protocol frame: [ver, type, seq, ctx_v, body]."""

    type: MessageType
    seq: int
    ctx_v: int
    body: dict[int, Any] = field(default_factory=dict)
    ver: int = PROTOCOL_VERSION

    def to_cbor(self) -> bytes:
        return cbor2.dumps([self.ver, int(self.type), self.seq, self.ctx_v, self.body])

    @classmethod
    def from_cbor(cls, data: bytes) -> "Frame":
        try:
            obj = cbor2.loads(data)
        except Exception as exc:  # cbor2 raises several error types
            raise ProtocolError(ErrorCode.BAD_FRAME, f"invalid CBOR: {exc}") from exc

        if isinstance(obj, cbor2.CBORTag) and obj.tag == TAG_ZSTD_FRAME:
            inner = _decompress(obj.value)
            try:
                obj = cbor2.loads(inner)
            except Exception as exc:
                raise ProtocolError(ErrorCode.BAD_FRAME, f"invalid CBOR inside compressed frame: {exc}") from exc
            if isinstance(obj, cbor2.CBORTag):
                raise ProtocolError(ErrorCode.BAD_FRAME, "compressed frames must not be nested")

        if not isinstance(obj, list) or len(obj) != 5:
            raise ProtocolError(ErrorCode.BAD_FRAME, "frame must be a 5-element array")
        ver, type_, seq, ctx_v, body = obj

        if ver != PROTOCOL_VERSION:
            raise ProtocolError(ErrorCode.UNSUPPORTED_VERSION, f"unsupported version {ver}")
        if not all(isinstance(x, int) and x >= 0 for x in (type_, seq, ctx_v)):
            raise ProtocolError(ErrorCode.BAD_FRAME, "type, seq and ctx_v must be uints")
        if not isinstance(body, dict):
            raise ProtocolError(ErrorCode.BAD_FRAME, "body must be a map")
        try:
            mtype = MessageType(type_)
        except ValueError as exc:
            raise ProtocolError(ErrorCode.UNKNOWN_TYPE, f"unknown message type {type_}") from exc

        return cls(type=mtype, seq=seq, ctx_v=ctx_v, body=body, ver=ver)


def encode_frame(frame: Frame, compress_threshold: int | None = None) -> bytes:
    """Encode a frame with its 4-byte big-endian length prefix.

    If compress_threshold is set and the encoded frame is at least that large,
    it is sent zstd-compressed (spec 3.2), but only if that is actually smaller.
    """
    payload = frame.to_cbor()
    if len(payload) > MAX_FRAME_SIZE:
        raise ProtocolError(ErrorCode.FRAME_TOO_LARGE, f"frame is {len(payload)} bytes")
    if compress_threshold is not None and len(payload) >= compress_threshold:
        packed = cbor2.dumps(cbor2.CBORTag(TAG_ZSTD_FRAME, _compressor().compress(payload)))
        if len(packed) < len(payload):
            payload = packed
    return _LEN.pack(len(payload)) + payload


_cctx: zstandard.ZstdCompressor | None = None


def _compressor() -> zstandard.ZstdCompressor:
    global _cctx
    if _cctx is None:
        _cctx = zstandard.ZstdCompressor(level=_ZSTD_LEVEL, write_content_size=True)
    return _cctx


def _decompress(data: Any) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise ProtocolError(ErrorCode.BAD_FRAME, "compressed frame must wrap a byte string")
    try:
        params = zstandard.get_frame_parameters(data)
    except zstandard.ZstdError as exc:
        raise ProtocolError(ErrorCode.BAD_FRAME, f"invalid zstd data: {exc}") from exc
    # Refuse decompression bombs: the declared size must be known and within the limit.
    if params.content_size in (0, zstandard.CONTENTSIZE_UNKNOWN) or params.content_size > MAX_FRAME_SIZE:
        raise ProtocolError(ErrorCode.FRAME_TOO_LARGE, "compressed frame has unknown or too large size")
    try:
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=MAX_FRAME_SIZE)
    except zstandard.ZstdError as exc:
        raise ProtocolError(ErrorCode.BAD_FRAME, f"invalid zstd data: {exc}") from exc


class FrameDecoder:
    """Incremental decoder for a byte stream. Feed it bytes, get complete frames back.

    TCP delivers a stream, not messages, so one read may contain half a frame
    or several frames. This class buffers until frames are complete.
    """

    def __init__(self, max_frame_size: int = MAX_FRAME_SIZE):
        self._buf = bytearray()
        self._max = max_frame_size

    def feed(self, data: bytes) -> list[Frame]:
        self._buf.extend(data)
        frames: list[Frame] = []
        while len(self._buf) >= _LEN.size:
            (length,) = _LEN.unpack_from(self._buf)
            if length > self._max:
                raise ProtocolError(ErrorCode.FRAME_TOO_LARGE, f"frame is {length} bytes")
            end = _LEN.size + length
            if len(self._buf) < end:
                break
            payload = bytes(self._buf[_LEN.size:end])
            del self._buf[:end]
            frames.append(Frame.from_cbor(payload))
        return frames

    @property
    def buffered(self) -> int:
        return len(self._buf)


# ----------------------------------------------------------------------- dictionary


class Dictionary:
    """Session dictionary (spec section 6).

    Context map keys are always strings, so on the wire an integer map key means
    "dictionary entry i". Values that are not map keys are never replaced.
    Hashing is always done on the expanded (string-keyed) form, so the dictionary
    only affects bytes on the wire, never the meaning of the context.
    """

    def __init__(self, entries: Iterable[str] = ()):
        self.entries: list[str] = list(entries)
        if len(set(self.entries)) != len(self.entries):
            raise ValueError("dictionary entries must be unique")
        self._index = {s: i for i, s in enumerate(self.entries)}

    def __len__(self) -> int:
        return len(self.entries)

    def ref(self, s: str) -> int | str:
        """Return the index of s if it is in the dictionary, else s itself."""
        return self._index.get(s, s)

    def lookup(self, key: int | str) -> str:
        if isinstance(key, str):
            return key
        if isinstance(key, int) and not isinstance(key, bool) and 0 <= key < len(self.entries):
            return self.entries[key]
        raise ProtocolError(ErrorCode.BAD_FRAME, f"invalid dictionary reference {key!r}")

    def compress(self, value: Any) -> Any:
        """Recursively replace string map keys with dictionary references."""
        if isinstance(value, dict):
            return {self._ckey(k): self.compress(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.compress(v) for v in value]
        return value

    def expand(self, value: Any) -> Any:
        """Inverse of compress: turn integer map keys back into strings."""
        if isinstance(value, dict):
            return {self.lookup(k): self.expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.expand(v) for v in value]
        return value

    def compress_path(self, path: list[str | int]) -> list[str | int]:
        """Replace string path elements with references.

        Integer path elements that are list indices stay as they are. Which integers
        are indices and which are references is decided when the path is applied,
        by looking at the container type (see context.py).
        """
        return [self.ref(p) if isinstance(p, str) else p for p in path]

    def _ckey(self, k: Any) -> Any:
        if not isinstance(k, str):
            raise ValueError(f"context map keys must be strings, got {k!r}")
        return self.ref(k)


# --------------------------------------------------------------------------- hashing


def canonical_cbor(value: Any) -> bytes:
    """Deterministic CBOR encoding (RFC 8949 section 4.2.1)."""
    return cbor2.dumps(value, canonical=True)


# The context hash is built from per-segment hashes (spec 5.5), so a store only
# has to re-hash the segments a message changed. History is hashed as a chain,
# so appending a turn costs one small hash instead of re-hashing the whole list.

SEGMENT_HASH_SIZE = 16
HIST_SEED = hashlib.blake2b(b"sayonce-hist-v1", digest_size=SEGMENT_HASH_SIZE).digest()


def _h16(data: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=SEGMENT_HASH_SIZE).digest()


def chain_hist(prev: bytes, turn: Any) -> bytes:
    """Hash of the history after appending one turn."""
    return _h16(prev + canonical_cbor(turn))


def segment_hash(name: str, value: Any) -> bytes:
    """16-byte hash of one context segment. "hist" is a chain over its turns."""
    if name == "hist" and isinstance(value, list):
        h = HIST_SEED
        for turn in value:
            h = chain_hist(h, turn)
        return h
    return _h16(canonical_cbor(value))


def combine_segment_hashes(seg: dict[str, bytes]) -> bytes:
    """8-byte context hash from segment hashes, in sorted segment-name order."""
    return hashlib.blake2b(
        b"".join(name.encode() + b"\x00" + seg[name] for name in sorted(seg)), digest_size=HASH_SIZE
    ).digest()


def context_hash(ctx: Any) -> bytes:
    """8-byte fingerprint of an (expanded) context, computed from scratch.

    Equal to what ContextStore maintains incrementally.
    """
    if isinstance(ctx, dict) and all(isinstance(k, str) for k in ctx):
        return combine_segment_hashes({k: segment_hash(k, v) for k, v in ctx.items()})
    return hashlib.blake2b(canonical_cbor(ctx), digest_size=HASH_SIZE).digest()
