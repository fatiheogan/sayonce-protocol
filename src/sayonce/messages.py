"""Message types, intents and constants of the SayOnce protocol.

See docs/protocol.md for the full specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .codec import Dictionary, Frame

PROTOCOL_VERSION = 1
MAX_FRAME_SIZE = 16 * 1024 * 1024  # 16 MiB


class MessageType(IntEnum):
    HELLO = 1
    HELLO_ACK = 2
    MSG = 3
    REPLY = 4
    RESYNC = 5
    SNAPSHOT = 6
    ERROR = 7
    BYE = 8


class Intent(IntEnum):
    REQUEST = 1
    INFORM = 2
    DELEGATE = 3
    CANCEL = 4


class ReplyStatus(IntEnum):
    OK = 0
    PARTIAL = 1
    FAILED = 2
    REJECTED = 3


class ResyncReason(IntEnum):
    VERSION_MISMATCH = 1
    HASH_MISMATCH = 2
    UNKNOWN_SESSION = 3
    APPLY_FAILED = 4


class ErrorCode(IntEnum):
    BAD_FRAME = 1
    UNSUPPORTED_VERSION = 2
    UNKNOWN_TYPE = 3
    FRAME_TOO_LARGE = 4
    OUT_OF_ORDER = 5


class DeltaOp(IntEnum):
    SET = 1
    DEL = 2
    APPEND = 3


# ---------------------------------------------------------------------------
# Typed message bodies (spec section 4).
#
# Each class converts to/from a Frame. Body keys are small integers on the wire.
# Context maps and delta values are compressed with the session Dictionary.
# Delta *paths* are only compressed, not expanded, here: an integer path element
# can be a list index or a dictionary reference, and that is decided when the
# delta is applied to the context (see context.py).
# ---------------------------------------------------------------------------

HASH_SIZE = 8


def _err(msg: str):
    from .codec import ProtocolError

    return ProtocolError(ErrorCode.BAD_FRAME, msg)


def _req(body: dict, key: int, types: type | tuple, name: str) -> Any:
    if key not in body:
        raise _err(f"missing field {name} ({key})")
    return _check(body[key], types, name)


def _opt(body: dict, key: int, types: type | tuple, name: str, default: Any = None) -> Any:
    if key not in body:
        return default
    return _check(body[key], types, name)


def _check(value: Any, types: type | tuple, name: str) -> Any:
    if not isinstance(value, types) or (isinstance(value, bool) and bool not in _as_tuple(types)):
        raise _err(f"field {name} has wrong type {type(value).__name__}")
    return value


def _as_tuple(t: type | tuple) -> tuple:
    return t if isinstance(t, tuple) else (t,)


def _hash(body: dict, key: int, name: str) -> bytes:
    h = _req(body, key, bytes, name)
    if len(h) != HASH_SIZE:
        raise _err(f"{name} must be {HASH_SIZE} bytes")
    return h


def _encode_delta(delta: list, d: "Dictionary") -> list:
    out = []
    for op in delta:
        code, path, *rest = op
        out.append([int(code), d.compress_path(list(path)), *[d.compress(v) for v in rest]])
    return out


def _decode_delta(raw: Any, d: "Dictionary") -> list:
    if not isinstance(raw, list):
        raise _err("delta must be an array")
    ops = []
    for op in raw:
        if not isinstance(op, list) or len(op) < 2 or not isinstance(op[1], list):
            raise _err(f"bad delta operation {op!r}")
        try:
            code = DeltaOp(op[0])
        except ValueError as exc:
            raise _err(f"unknown delta op {op[0]!r}") from exc
        expected = 2 if code == DeltaOp.DEL else 3
        if len(op) != expected:
            raise _err(f"delta op {code.name} needs {expected} elements")
        ops.append([code, op[1], *[d.expand(v) for v in op[2:]]])
    return ops


@dataclass
class Message:
    TYPE: ClassVar[MessageType]

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        raise NotImplementedError

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Message":
        raise NotImplementedError

    def to_frame(self, seq: int, ctx_v: int, d: "Dictionary") -> "Frame":
        from .codec import Frame

        return Frame(type=self.TYPE, seq=seq, ctx_v=ctx_v, body=self.to_body(d))


@dataclass
class Hello(Message):
    TYPE: ClassVar[MessageType] = MessageType.HELLO
    agent_id: str
    dictionary: list[str]
    ctx: dict[str, Any]
    caps: dict[str, Any] = field(default_factory=dict)
    resume: tuple[bytes, int, bytes] | None = None

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        # HELLO carries the dictionary, so its own context is compressed with it.
        from .codec import Dictionary

        own = Dictionary(self.dictionary)
        body: dict[int, Any] = {0: self.agent_id, 1: list(self.dictionary), 2: own.compress(self.ctx)}
        if self.caps:
            body[3] = self.caps
        if self.resume is not None:
            body[4] = list(self.resume)
        return body

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Hello":
        from .codec import Dictionary

        entries = _req(body, 1, list, "dict")
        if not all(isinstance(e, str) for e in entries):
            raise _err("dict entries must be strings")
        own = Dictionary(entries)
        resume = _opt(body, 4, list, "resume")
        if resume is not None:
            if len(resume) != 3:
                raise _err("resume must be [session_id, ctx_v, ctx_h]")
            resume = (resume[0], resume[1], resume[2])
        return cls(
            agent_id=_req(body, 0, str, "agent_id"),
            dictionary=entries,
            ctx=own.expand(_req(body, 2, dict, "ctx")),
            caps=_opt(body, 3, dict, "caps", {}),
            resume=resume,
        )


@dataclass
class HelloAck(Message):
    TYPE: ClassVar[MessageType] = MessageType.HELLO_ACK
    agent_id: str
    session_id: bytes
    ctx_h: bytes
    resumed: bool = False

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        return {0: self.agent_id, 1: self.session_id, 2: self.ctx_h, 3: self.resumed}

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "HelloAck":
        return cls(
            agent_id=_req(body, 0, str, "agent_id"),
            session_id=_req(body, 1, bytes, "session_id"),
            ctx_h=_hash(body, 2, "ctx_h"),
            resumed=_opt(body, 3, bool, "resumed", False),
        )


@dataclass
class Msg(Message):
    TYPE: ClassVar[MessageType] = MessageType.MSG
    intent: Intent
    content: Any
    ctx_h: bytes
    delta: list = field(default_factory=list)
    task_id: int | None = None

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        body: dict[int, Any] = {0: int(self.intent), 1: self.content, 3: self.ctx_h}
        if self.delta:
            body[2] = _encode_delta(self.delta, d)
        if self.task_id is not None:
            body[4] = self.task_id
        return body

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Msg":
        try:
            intent = Intent(_req(body, 0, int, "intent"))
        except ValueError as exc:
            raise _err(f"unknown intent {body[0]!r}") from exc
        if 1 not in body:
            raise _err("missing field content (1)")
        return cls(
            intent=intent,
            content=body[1],
            ctx_h=_hash(body, 3, "ctx_h"),
            delta=_decode_delta(body.get(2, []), d),
            task_id=_opt(body, 4, int, "task_id"),
        )


@dataclass
class Reply(Message):
    TYPE: ClassVar[MessageType] = MessageType.REPLY
    status: ReplyStatus
    content: Any
    ctx_h: bytes
    in_reply_to: int
    delta: list = field(default_factory=list)

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        body: dict[int, Any] = {
            0: int(self.status),
            1: self.content,
            3: self.ctx_h,
            4: self.in_reply_to,
        }
        if self.delta:
            body[2] = _encode_delta(self.delta, d)
        return body

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Reply":
        try:
            status = ReplyStatus(_req(body, 0, int, "status"))
        except ValueError as exc:
            raise _err(f"unknown status {body[0]!r}") from exc
        if 1 not in body:
            raise _err("missing field content (1)")
        return cls(
            status=status,
            content=body[1],
            ctx_h=_hash(body, 3, "ctx_h"),
            in_reply_to=_req(body, 4, int, "in_reply_to"),
            delta=_decode_delta(body.get(2, []), d),
        )


@dataclass
class Resync(Message):
    TYPE: ClassVar[MessageType] = MessageType.RESYNC
    reason: ResyncReason
    my_ctx_v: int
    my_ctx_h: bytes

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        return {0: int(self.reason), 1: self.my_ctx_v, 2: self.my_ctx_h}

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Resync":
        try:
            reason = ResyncReason(_req(body, 0, int, "reason"))
        except ValueError as exc:
            raise _err(f"unknown resync reason {body[0]!r}") from exc
        return cls(
            reason=reason,
            my_ctx_v=_req(body, 1, int, "my_ctx_v"),
            my_ctx_h=_hash(body, 2, "my_ctx_h"),
        )


@dataclass
class Snapshot(Message):
    TYPE: ClassVar[MessageType] = MessageType.SNAPSHOT
    ctx_v: int
    ctx: dict[str, Any]
    ctx_h: bytes

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        return {0: self.ctx_v, 1: d.compress(self.ctx), 2: self.ctx_h}

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Snapshot":
        return cls(
            ctx_v=_req(body, 0, int, "ctx_v"),
            ctx=d.expand(_req(body, 1, dict, "ctx")),
            ctx_h=_hash(body, 2, "ctx_h"),
        )


@dataclass
class Error(Message):
    TYPE: ClassVar[MessageType] = MessageType.ERROR
    code: ErrorCode
    message: str = ""

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        return {0: int(self.code), 1: self.message}

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Error":
        try:
            code = ErrorCode(_req(body, 0, int, "code"))
        except ValueError as exc:
            raise _err(f"unknown error code {body[0]!r}") from exc
        return cls(code=code, message=_opt(body, 1, str, "message", ""))


@dataclass
class Bye(Message):
    TYPE: ClassVar[MessageType] = MessageType.BYE

    def to_body(self, d: "Dictionary") -> dict[int, Any]:
        return {}

    @classmethod
    def from_body(cls, body: dict, d: "Dictionary") -> "Bye":
        return cls()


MESSAGE_CLASSES: dict[MessageType, type[Message]] = {
    cls.TYPE: cls for cls in (Hello, HelloAck, Msg, Reply, Resync, Snapshot, Error, Bye)
}


def parse_message(frame: "Frame", d: "Dictionary") -> Message:
    """Turn a decoded Frame into its typed message."""
    return MESSAGE_CLASSES[frame.type].from_body(frame.body, d)
