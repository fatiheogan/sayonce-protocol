"""Message types and intents of the SayOnce protocol (to be implemented)."""

from enum import IntEnum


class MessageType(IntEnum):
    HELLO = 1
    MSG = 2
    REPLY = 3
    RESYNC = 4


class Intent(IntEnum):
    REQUEST = 1
    INFORM = 2
    DELEGATE = 3
