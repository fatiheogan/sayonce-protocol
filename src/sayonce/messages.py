"""Message types, intents and constants of the SayOnce protocol.

See docs/protocol.md for the full specification.
"""

from enum import IntEnum

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
