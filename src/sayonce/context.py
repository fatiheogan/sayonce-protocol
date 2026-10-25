"""Shared context store with versioned delta updates (spec section 5).

Both agents keep a ContextStore. Every MSG and REPLY moves both stores from
version n to n+1 in the same way:

1. append the new message to "hist" (implicit, spec 5.4),
2. apply the explicit delta operations in order (spec 5.3),
3. check that the resulting hash matches the sender's hash (spec 5.6).

If anything does not match, the receiver raises ResyncRequired and the
session layer answers with RESYNC / SNAPSHOT (spec 5.7).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .codec import Dictionary, context_hash
from .messages import DeltaOp, ResyncReason

SEGMENTS = ("sys", "tools", "hist", "vars")
_SEGMENT_TYPES: dict[str, type] = {"sys": str, "tools": dict, "hist": list, "vars": dict}

CLIENT = "c"
SERVER = "s"


class DeltaError(Exception):
    """A delta operation could not be applied (bad path, wrong type, ...)."""


class ResyncRequired(Exception):
    """The local context does not match the sender's. Carries the RESYNC reason."""

    def __init__(self, reason: ResyncReason, detail: str = ""):
        super().__init__(f"{reason.name}: {detail}" if detail else reason.name)
        self.reason = reason


def empty_context() -> dict[str, Any]:
    return {"sys": "", "tools": {}, "hist": [], "vars": {}}


def validate_context(ctx: Any) -> None:
    """Check the top-level shape of a context (spec 5.2)."""
    if not isinstance(ctx, dict):
        raise DeltaError("context must be a map")
    if set(ctx) != set(SEGMENTS):
        raise DeltaError(f"context must have exactly the segments {SEGMENTS}, got {sorted(ctx)}")
    for name, typ in _SEGMENT_TYPES.items():
        if not isinstance(ctx[name], typ):
            raise DeltaError(f"segment {name!r} must be {typ.__name__}")


def history_turn(role: str, code: int, content: Any) -> dict[str, Any]:
    """The turn that is appended to "hist" for a MSG (role c) or REPLY (role s)."""
    if role == CLIENT:
        return {"r": CLIENT, "i": int(code), "c": content}
    if role == SERVER:
        return {"r": SERVER, "s": int(code), "c": content}
    raise ValueError(f"unknown role {role!r}")


# ---------------------------------------------------------------- delta logic


def _resolve_key(container: Any, key: Any, d: Dictionary) -> Any:
    """Turn a wire path element into a real key, based on the container type."""
    if isinstance(container, list):
        if not isinstance(key, int) or isinstance(key, bool):
            raise DeltaError(f"list index must be an integer, got {key!r}")
        if not 0 <= key < len(container):
            raise DeltaError(f"list index {key} out of range (len {len(container)})")
        return key
    if isinstance(container, dict):
        if isinstance(key, str):
            return key
        if isinstance(key, int) and not isinstance(key, bool):
            try:
                return d.lookup(key)
            except Exception as exc:
                raise DeltaError(str(exc)) from exc
        raise DeltaError(f"map key must be a string or dictionary reference, got {key!r}")
    raise DeltaError(f"cannot index into {type(container).__name__}")


def _walk(ctx: dict, path: list, d: Dictionary, create: bool) -> tuple[Any, Any]:
    """Return (parent container, resolved last key) for a path."""
    if not path:
        raise DeltaError("path must not be empty")
    node: Any = ctx
    for raw in path[:-1]:
        key = _resolve_key(node, raw, d)
        if isinstance(node, dict) and key not in node:
            if not create:
                raise DeltaError(f"path element {key!r} not found")
            node[key] = {}
        node = node[key]
    last = path[-1]
    if isinstance(node, list):
        return node, _resolve_key(node, last, d)
    if isinstance(node, dict):
        return node, _resolve_key(node, last, d)
    raise DeltaError(f"cannot index into {type(node).__name__}")


def _check_top_level(path: list, d: Dictionary, op: DeltaOp) -> None:
    if len(path) == 1 and op != DeltaOp.APPEND:
        seg = _resolve_key({}, path[0], d)
        if op == DeltaOp.DEL:
            raise DeltaError(f"cannot delete segment {seg!r}")
        if op == DeltaOp.SET and seg not in SEGMENTS:
            raise DeltaError(f"unknown segment {seg!r}")


def apply_delta(ctx: dict, delta: list, d: Dictionary) -> None:
    """Apply delta operations to ctx in place. Raises DeltaError on failure.

    Callers that need all-or-nothing behaviour should pass a copy.
    """
    for op in delta:
        if not isinstance(op, (list, tuple)) or len(op) < 2:
            raise DeltaError(f"bad operation {op!r}")
        try:
            code = DeltaOp(op[0])
        except ValueError as exc:
            raise DeltaError(f"unknown op {op[0]!r}") from exc
        path = list(op[1])
        _check_top_level(path, d, code)

        if code == DeltaOp.SET:
            if len(op) != 3:
                raise DeltaError("SET needs [1, path, value]")
            parent, key = _walk(ctx, path, d, create=True)
            parent[key] = copy.deepcopy(op[2])
        elif code == DeltaOp.DEL:
            if len(op) != 2:
                raise DeltaError("DEL needs [2, path]")
            parent, key = _walk(ctx, path, d, create=False)
            if isinstance(parent, dict) and key not in parent:
                raise DeltaError(f"key {key!r} not found")
            del parent[key]
        elif code == DeltaOp.APPEND:
            if len(op) != 3 or not isinstance(op[2], list):
                raise DeltaError("APPEND needs [3, path, [items]]")
            parent, key = _walk(ctx, path, d, create=False)
            if isinstance(parent, dict) and key not in parent:
                raise DeltaError(f"key {key!r} not found")
            target = parent[key]
            if not isinstance(target, list):
                raise DeltaError(f"APPEND target is {type(target).__name__}, not a list")
            target.extend(copy.deepcopy(op[2]))

    validate_context(ctx)


# ---------------------------------------------------------------- the store


@dataclass(frozen=True)
class Step:
    """Result of advancing the context by one frame."""

    version: int  # version before the frame (goes into the frame header)
    new_version: int
    new_hash: bytes  # goes into the frame body


class ContextStore:
    """One agent's copy of the shared context."""

    def __init__(self, ctx: dict | None = None, dictionary: Dictionary | None = None, version: int = 0):
        self.dictionary = dictionary or Dictionary()
        ctx = copy.deepcopy(ctx) if ctx is not None else empty_context()
        validate_context(ctx)
        self._ctx = ctx
        self.version = version
        self.hash = context_hash(ctx)

    @property
    def ctx(self) -> dict:
        """Read-only view. Do not modify; use advance/receive."""
        return self._ctx

    # -- sending side ------------------------------------------------------

    def advance(self, role: str, code: int, content: Any, delta: list | None = None) -> Step:
        """Apply our own outgoing MSG/REPLY and return what to put in the frame.

        Raises DeltaError if our own delta is invalid (a programming error);
        the store is left unchanged in that case.
        """
        new_ctx = self._next(role, code, content, delta or [])
        return self._commit(new_ctx)

    # -- receiving side ----------------------------------------------------

    def receive(
        self,
        role: str,
        code: int,
        content: Any,
        delta: list,
        frame_ctx_v: int,
        frame_ctx_h: bytes,
    ) -> Step:
        """Apply an incoming MSG/REPLY following spec 5.6.

        Raises ResyncRequired and leaves the store unchanged if the version,
        the delta or the resulting hash does not match.
        """
        if frame_ctx_v != self.version:
            raise ResyncRequired(
                ResyncReason.VERSION_MISMATCH, f"frame at v{frame_ctx_v}, local at v{self.version}"
            )
        try:
            new_ctx = self._next(role, code, content, delta)
        except DeltaError as exc:
            raise ResyncRequired(ResyncReason.APPLY_FAILED, str(exc)) from exc
        new_hash = context_hash(new_ctx)
        if new_hash != frame_ctx_h:
            raise ResyncRequired(ResyncReason.HASH_MISMATCH, "context differs after applying delta")
        return self._commit(new_ctx, new_hash)

    # -- resync --------------------------------------------------------------

    def snapshot(self) -> tuple[int, dict, bytes]:
        """(version, full context copy, hash), for a SNAPSHOT frame."""
        return self.version, copy.deepcopy(self._ctx), self.hash

    def load_snapshot(self, version: int, ctx: dict, ctx_h: bytes) -> None:
        """Replace the local context with a received SNAPSHOT."""
        validate_context(ctx)
        if context_hash(ctx) != ctx_h:
            raise ResyncRequired(ResyncReason.HASH_MISMATCH, "snapshot hash does not match its content")
        self._ctx = copy.deepcopy(ctx)
        self.version = version
        self.hash = ctx_h

    # -- internals -----------------------------------------------------------

    def _next(self, role: str, code: int, content: Any, delta: list) -> dict:
        new_ctx = copy.deepcopy(self._ctx)
        new_ctx["hist"].append(history_turn(role, code, copy.deepcopy(content)))
        apply_delta(new_ctx, delta, self.dictionary)
        return new_ctx

    def _commit(self, new_ctx: dict, new_hash: bytes | None = None) -> Step:
        old = self.version
        self._ctx = new_ctx
        self.version = old + 1
        self.hash = new_hash if new_hash is not None else context_hash(new_ctx)
        return Step(version=old, new_version=self.version, new_hash=self.hash)


__all__ = [
    "CLIENT",
    "SERVER",
    "SEGMENTS",
    "ContextStore",
    "DeltaError",
    "ResyncRequired",
    "Step",
    "apply_delta",
    "empty_context",
    "history_turn",
    "validate_context",
]
