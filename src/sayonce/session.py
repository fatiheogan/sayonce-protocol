"""SayOnce sessions: handshake, request/response, resync and resume (spec 4, 5.6-5.8).

Client side:

    client = await ClientSession.open("127.0.0.1", port, "agent-a", ctx, dictionary)
    result = await client.request(Intent.REQUEST, "find flights", delta=[...])
    await client.close()

Server side:

    async def handler(req: Request) -> Response: ...
    server = Server(handler, agent_id="agent-b")
    await server.start()
"""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Union

from .codec import DEFAULT_COMPRESS_THRESHOLD, Dictionary, ProtocolError
from .context import CLIENT, SERVER, ContextStore, DeltaError, ResyncRequired, empty_context
from .messages import (
    Bye,
    Error,
    ErrorCode,
    Hello,
    HelloAck,
    Intent,
    Message,
    MessageType,
    Msg,
    Reply,
    ReplyStatus,
    Resync,
    Snapshot,
    parse_message,
)
from .transport import ConnectionClosed, FramedConnection

NO_HASH = b"\x00" * 8
MAX_RESYNC_ATTEMPTS = 3


class SessionError(Exception):
    """The session cannot continue (peer error, protocol violation, too many resyncs)."""


# --------------------------------------------------------------------- shared


class _Endpoint:
    """Common send/receive helpers for both sides."""

    conn: FramedConnection
    store: ContextStore
    resync_count: int

    def __init__(self) -> None:
        self._seq = 0

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq += 1
        return seq

    async def _send(self, msg: Message, ctx_v: int | None = None) -> int:
        ctx_v = self.store.version if ctx_v is None else ctx_v
        return await self.conn.send(msg.to_frame(self._next_seq(), ctx_v, self.store.dictionary))

    async def _send_snapshot(self) -> None:
        v, ctx, h = self.store.snapshot()
        await self._send(Snapshot(ctx_v=v, ctx=ctx, ctx_h=h), ctx_v=v)

    async def _load_snapshot(self, snap: Snapshot) -> None:
        self.store.load_snapshot(snap.ctx_v, snap.ctx, snap.ctx_h)
        self.resync_count += 1


# --------------------------------------------------------------------- client


@dataclass
class ReplyResult:
    status: ReplyStatus
    content: Any
    latency_s: float
    bytes_sent: int
    bytes_received: int
    resyncs: int


class ClientSession(_Endpoint):
    def __init__(self, conn: FramedConnection, agent_id: str, store: ContextStore):
        super().__init__()
        self.conn = conn
        self.agent_id = agent_id
        self.store = store
        self.session_id: bytes = b""
        self.peer_id: str = ""
        self.resumed = False
        self.resync_count = 0
        self.timeout: float | None = 30.0

    # -- opening -----------------------------------------------------------

    @classmethod
    async def open(
        cls,
        host: str,
        port: int,
        agent_id: str,
        ctx: dict | None = None,
        dictionary: list[str] | None = None,
        caps: dict | None = None,
        compress_threshold: int | None = DEFAULT_COMPRESS_THRESHOLD,
    ) -> "ClientSession":
        """Open a new session and send the full context once (HELLO).

        Frames of at least compress_threshold bytes (typically HELLO and
        SNAPSHOT) are zstd-compressed; None sends everything uncompressed.
        """
        conn = await FramedConnection.connect(host, port)
        conn.compress_threshold = compress_threshold
        store = ContextStore(ctx, Dictionary(dictionary or []))
        session = cls(conn, agent_id, store)
        hello = Hello(agent_id=agent_id, dictionary=store.dictionary.entries, ctx=store.ctx, caps=caps or {})
        await session._send(hello, ctx_v=0)
        await session._expect_ack()
        return session

    @classmethod
    async def resume(cls, host: str, port: int, previous: "ClientSession") -> "ClientSession":
        """Reconnect and continue a previous session without re-sending the context (spec 5.8)."""
        conn = await FramedConnection.connect(host, port)
        conn.compress_threshold = previous.conn.compress_threshold
        session = cls(conn, previous.agent_id, previous.store)
        session.resync_count = previous.resync_count
        st = session.store
        hello = Hello(
            agent_id=previous.agent_id,
            dictionary=st.dictionary.entries,
            ctx={},
            resume=(previous.session_id, st.version, st.hash),
        )
        await session._send(hello)
        ack = await session._expect_ack(check_hash=False)
        if not ack.resumed:
            # Server lost the session: send our context so it can continue.
            await session._send_snapshot()
            session.resync_count += 1
        return session

    async def _expect_ack(self, check_hash: bool = True) -> HelloAck:
        frame = await self._recv()
        msg = parse_message(frame, self.store.dictionary)
        if isinstance(msg, Error):
            raise SessionError(f"server refused session: {msg.code.name} {msg.message}")
        if not isinstance(msg, HelloAck):
            raise SessionError(f"expected HELLO_ACK, got {frame.type.name}")
        self.session_id, self.peer_id, self.resumed = msg.session_id, msg.agent_id, msg.resumed
        if (check_hash or msg.resumed) and msg.ctx_h != self.store.hash:
            raise SessionError("server stored a different context than we sent")
        return msg

    # -- request / reply ---------------------------------------------------

    async def request(
        self,
        intent: Intent,
        content: Any,
        delta: list | None = None,
        task_id: int | None = None,
    ) -> ReplyResult:
        """Send one MSG and wait for its REPLY, handling resync on the way."""
        stats = self.conn.stats
        sent0, recv0, resync0 = stats.bytes_sent, stats.bytes_received, self.resync_count
        t0 = time.perf_counter()

        before = self.store.checkpoint()  # O(1); to roll back if the server rejects this MSG
        msg_seq = await self._send_msg(intent, content, delta, task_id)

        attempts = 0
        while True:
            frame = await self._recv()
            msg = parse_message(frame, self.store.dictionary)

            if isinstance(msg, Reply):
                if msg.in_reply_to != msg_seq:
                    raise SessionError(f"reply to seq {msg.in_reply_to}, expected {msg_seq}")
                try:
                    self.store.receive(SERVER, msg.status, msg.content, msg.delta, frame.ctx_v, msg.ctx_h)
                except ResyncRequired as exc:
                    # The answer itself is fine; only our context is off. Ask for the server's.
                    await self._send(Resync(reason=exc.reason, my_ctx_v=self.store.version, my_ctx_h=self.store.hash))
                    await self._await_snapshot()
                return ReplyResult(
                    status=msg.status,
                    content=msg.content,
                    latency_s=time.perf_counter() - t0,
                    bytes_sent=stats.bytes_sent - sent0,
                    bytes_received=stats.bytes_received - recv0,
                    resyncs=self.resync_count - resync0,
                )

            if isinstance(msg, Resync):
                # Server could not apply our MSG. Roll it back, send our context, retry.
                attempts += 1
                if attempts > MAX_RESYNC_ATTEMPTS:
                    raise SessionError("too many resync attempts")
                self.store.restore(before)
                await self._send_snapshot()
                self.resync_count += 1
                msg_seq = await self._send_msg(intent, content, delta, task_id)
                continue

            if isinstance(msg, Snapshot):
                await self._load_snapshot(msg)
                continue
            if isinstance(msg, Error):
                raise SessionError(f"server error {msg.code.name}: {msg.message}")
            raise SessionError(f"unexpected {frame.type.name} while waiting for REPLY")

    async def _send_msg(self, intent: Intent, content: Any, delta: list | None, task_id: int | None) -> int:
        step = self.store.advance(CLIENT, intent, content, delta)
        seq = self._seq
        msg = Msg(intent=intent, content=content, ctx_h=step.new_hash, delta=delta or [], task_id=task_id)
        await self._send(msg, ctx_v=step.version)
        return seq

    async def _await_snapshot(self) -> None:
        while True:
            frame = await self._recv()
            msg = parse_message(frame, self.store.dictionary)
            if isinstance(msg, Snapshot):
                await self._load_snapshot(msg)
                return
            if isinstance(msg, Error):
                raise SessionError(f"server error {msg.code.name}: {msg.message}")
            raise SessionError(f"expected SNAPSHOT, got {frame.type.name}")

    async def _recv(self):
        if self.timeout is None:
            return await self.conn.recv()
        try:
            return await asyncio.wait_for(self.conn.recv(), self.timeout)
        except asyncio.TimeoutError as exc:
            raise SessionError(f"no answer within {self.timeout}s") from exc

    async def close(self, bye: bool = True) -> None:
        if bye:
            try:
                await self._send(Bye())
            except (ConnectionError, OSError):
                pass
        await self.conn.close()


# --------------------------------------------------------------------- server


@dataclass
class Request:
    intent: Intent
    content: Any
    ctx: dict  # shared context after this MSG was applied; read only
    task_id: int | None = None
    session_id: bytes = b""


@dataclass
class Response:
    content: Any
    status: ReplyStatus = ReplyStatus.OK
    delta: list = field(default_factory=list)


Handler = Callable[[Request], Union[Response, Awaitable[Response]]]


class Server:
    """Accepts SayOnce sessions and answers MSGs with a handler."""

    def __init__(self, handler: Handler, agent_id: str = "server", host: str = "127.0.0.1", port: int = 0,
                 compress_threshold: int | None = DEFAULT_COMPRESS_THRESHOLD):
        self.handler = handler
        self.compress_threshold = compress_threshold
        self.agent_id = agent_id
        self.host = host
        self.port = port
        self.sessions: dict[bytes, ContextStore] = {}
        self.connections: list[ServerSession] = []
        self._server: asyncio.base_events.Server | None = None

    async def start(self) -> "Server":
        self._server = await asyncio.start_server(self._on_connection, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def close(self) -> None:
        # Close open connections first; wait_closed() waits for them on Python 3.12+.
        for s in list(self.connections):
            await s.conn.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def __aenter__(self) -> "Server":
        return await self.start()

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        conn = FramedConnection(reader, writer)
        conn.compress_threshold = self.compress_threshold
        session = ServerSession(self, conn)
        self.connections.append(session)
        try:
            await session.run()
        finally:
            self.connections.remove(session)
            await session.conn.close()


class ServerSession(_Endpoint):
    def __init__(self, server: Server, conn: FramedConnection):
        super().__init__()
        self.server = server
        self.conn = conn
        self.store = ContextStore()
        self.session_id = b""
        self.resync_count = 0

    async def run(self) -> None:
        try:
            await self._handshake()
            while True:
                frame = await self.conn.recv()
                msg = parse_message(frame, self.store.dictionary)
                if isinstance(msg, Msg):
                    await self._on_msg(frame.seq, frame.ctx_v, msg)
                elif isinstance(msg, Resync):
                    await self._send_snapshot()
                elif isinstance(msg, Snapshot):
                    await self._load_snapshot(msg)
                elif isinstance(msg, Bye):
                    return
                else:
                    await self._send(Error(code=ErrorCode.OUT_OF_ORDER, message=f"unexpected {frame.type.name}"))
        except ProtocolError as exc:
            try:
                await self._send(Error(code=exc.code, message=str(exc)))
            except (ConnectionError, OSError):
                pass
        except (ConnectionClosed, ConnectionError, OSError):
            pass

    async def _handshake(self) -> None:
        frame = await self.conn.recv()
        if frame.type != MessageType.HELLO:
            raise ProtocolError(ErrorCode.OUT_OF_ORDER, f"expected HELLO, got {frame.type.name}")
        hello = parse_message(frame, Dictionary())
        assert isinstance(hello, Hello)
        d = Dictionary(hello.dictionary)

        if hello.resume is not None:
            sid, v, h = hello.resume
            existing = self.server.sessions.get(sid)
            if existing is not None and existing.version == v and existing.hash == h:
                self.session_id, self.store = sid, existing
                await self._send(HelloAck(agent_id=self.server.agent_id, session_id=sid, ctx_h=h, resumed=True))
                return
            # Unknown or out-of-date session: start a fresh one, client will send a SNAPSHOT.
            self.store = ContextStore(empty_context(), d)
            self.session_id = os.urandom(8)
            self.server.sessions[self.session_id] = self.store
            await self._send(HelloAck(agent_id=self.server.agent_id, session_id=self.session_id, ctx_h=NO_HASH))
            return

        try:
            self.store = ContextStore(hello.ctx, d)
        except DeltaError as exc:
            raise ProtocolError(ErrorCode.BAD_FRAME, f"bad initial context: {exc}") from exc
        self.session_id = os.urandom(8)
        self.server.sessions[self.session_id] = self.store
        await self._send(HelloAck(agent_id=self.server.agent_id, session_id=self.session_id, ctx_h=self.store.hash))

    async def _on_msg(self, seq: int, ctx_v: int, msg: Msg) -> None:
        try:
            self.store.receive(CLIENT, msg.intent, msg.content, msg.delta, ctx_v, msg.ctx_h)
        except ResyncRequired as exc:
            self.resync_count += 1
            await self._send(Resync(reason=exc.reason, my_ctx_v=self.store.version, my_ctx_h=self.store.hash))
            return  # client sends a SNAPSHOT and repeats the MSG

        req = Request(
            intent=msg.intent, content=msg.content, ctx=self.store.ctx, task_id=msg.task_id, session_id=self.session_id
        )
        try:
            resp = self.server.handler(req)
            if inspect.isawaitable(resp):
                resp = await resp
        except Exception as exc:  # handler bug: answer FAILED instead of killing the session
            resp = Response(content=f"handler error: {exc}", status=ReplyStatus.FAILED)

        try:
            step = self.store.advance(SERVER, resp.status, resp.content, resp.delta)
        except DeltaError as exc:
            resp = Response(content=f"invalid delta from handler: {exc}", status=ReplyStatus.FAILED)
            step = self.store.advance(SERVER, resp.status, resp.content, [])

        reply = Reply(status=resp.status, content=resp.content, ctx_h=step.new_hash, in_reply_to=seq, delta=resp.delta)
        await self._send(reply, ctx_v=step.version)
