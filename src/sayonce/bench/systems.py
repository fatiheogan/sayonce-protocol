"""The systems compared in the benchmark (spec section 8.1), behind one interface.

| name           | encoding          | transport | context per round |
|----------------|-------------------|-----------|-------------------|
| jsonrpc        | JSON-RPC          | HTTP      | full    (B1)      |
| jsonrpc-gzip   | JSON-RPC + gzip   | HTTP      | full    (B2)      |
| jsonrpc-zstd   | JSON-RPC + zstd   | HTTP      | full    (B2)      |
| cbor-full      | CBOR + dictionary | TCP       | full    (B3)      |
| json-delta     | JSON-RPC          | HTTP      | delta   (B4)      |
| sayonce-raw    | CBOR + dictionary | TCP       | delta   (S, no frame compression) |
| sayonce        | CBOR + dict + zstd for large frames | TCP | delta (S) |

Every system runs the same server-side handler (e.g. WorkerAgent) and keeps a
client-side ContextStore, so all of them end with the same shared context and
produce the same answers. Only what goes over the wire differs.

Full-context systems (B1-B3) model today's stateless agent APIs: the client
keeps the conversation and sends all of it (instructions, tools, history and
the new message as the last history turn) in every request.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..codec import DEFAULT_COMPRESS_THRESHOLD, Dictionary, Frame
from ..context import CLIENT, SERVER, ContextStore, ResyncRequired
from ..messages import DeltaOp, Intent, MessageType, ReplyStatus, _decode_delta, _encode_delta
from ..session import ClientSession, Handler, Request, Response, Server
from ..transport import FramedConnection
from .http import HttpClient, HttpServer

# ------------------------------------------------------------------ results


@dataclass
class RoundResult:
    status: ReplyStatus
    content: Any
    bytes_sent: int  # client -> server, all application bytes incl. framing / HTTP headers
    bytes_received: int  # server -> client
    header_bytes: int = 0  # part of the above that is HTTP headers (0 for TCP systems)
    info_sent: Any = None  # the information that crossed the wire, decoded (for token counting)
    info_received: Any = None
    latency_s: float = 0.0

    @property
    def bytes_total(self) -> int:
        return self.bytes_sent + self.bytes_received


@dataclass
class SetupResult:
    bytes_sent: int = 0
    bytes_received: int = 0
    header_bytes: int = 0
    info_sent: Any = None

    @property
    def bytes_total(self) -> int:
        return self.bytes_sent + self.bytes_received


class System(ABC):
    name: str = ""
    full_context: bool = True  # sends the whole context every round?
    connect_port: int | None = None  # set to a proxy port to route the client through a network emulator
    connect_host: str = "127.0.0.1"  # where the client connects (another computer in remote runs)
    listen_host: str = "127.0.0.1"  # where the server listens ("0.0.0.0" to accept other computers)

    @property
    @abstractmethod
    def server_port(self) -> int:
        """Port the server listens on (available after start)."""

    def _client_port(self) -> int:
        return self.connect_port or self.server_port

    @abstractmethod
    async def start(self, handler: Handler) -> None:
        """Start the server side with the given handler."""

    @abstractmethod
    async def open(self, agent_id: str, ctx: dict, dictionary: list[str]) -> SetupResult:
        """Connect the client and set up the session."""

    @abstractmethod
    async def request(
        self, intent: Intent, content: Any, delta: list | None = None, task_id: int | None = None
    ) -> RoundResult:
        """One round: send a message, wait for the reply."""

    @abstractmethod
    async def close(self) -> None:
        """Close client and server."""

    @property
    @abstractmethod
    def client_ctx(self) -> dict:
        """The client's view of the shared context (for checks)."""


async def _call(handler: Handler, req: Request) -> Response:
    resp = handler(req)
    if inspect.isawaitable(resp):
        resp = await resp
    return resp


def _now() -> float:
    return asyncio.get_running_loop().time()


# ------------------------------------------------------------------ JSON helpers

_OP_NAMES = {DeltaOp.SET: "set", DeltaOp.DEL: "del", DeltaOp.APPEND: "append"}
_OP_CODES = {v: k for k, v in _OP_NAMES.items()}


def delta_to_json(delta: list) -> list[dict]:
    out = []
    for op in delta:
        item = {"op": _OP_NAMES[DeltaOp(op[0])], "path": list(op[1])}
        if len(op) > 2:
            item["value"] = op[2]
        out.append(item)
    return out


def delta_from_json(items: list[dict]) -> list:
    return [[_OP_CODES[i["op"]], i["path"], *([i["value"]] if "value" in i else [])] for i in items]


def dumps(obj: Any) -> bytes:
    """Compact JSON, the favourable case for the baselines."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()


# ------------------------------------------------------------------ S: SayOnce


class SayOnceSystem(System):
    """The full protocol. compress=False gives the 'sayonce-raw' ablation (no frame compression)."""

    full_context = False

    def __init__(self, compress: bool = True) -> None:
        self.name = "sayonce" if compress else "sayonce-raw"
        self.compress_threshold = DEFAULT_COMPRESS_THRESHOLD if compress else None
        self.server: Server | None = None
        self.client: ClientSession | None = None
        self._reply_delta: list = []

    async def start(self, handler: Handler) -> None:
        async def recording(req: Request) -> Response:
            resp = await _call(handler, req)
            self._reply_delta = list(resp.delta)  # for token accounting only
            return resp

        self.server = await Server(recording, agent_id="agent-b", host=self.listen_host,
                                   compress_threshold=self.compress_threshold).start()

    async def open(self, agent_id: str, ctx: dict, dictionary: list[str]) -> SetupResult:
        assert self.server or self.connect_port
        self.client = await ClientSession.open(self.connect_host, self._client_port(), agent_id, ctx, dictionary,
                                               compress_threshold=self.compress_threshold)
        st = self.client.conn.stats
        return SetupResult(st.bytes_sent, st.bytes_received, info_sent={"context": ctx, "dictionary": dictionary})

    async def request(self, intent, content, delta=None, task_id=None) -> RoundResult:
        assert self.client
        r = await self.client.request(intent, content, delta=delta, task_id=task_id)
        return RoundResult(
            status=r.status,
            content=r.content,
            bytes_sent=r.bytes_sent,
            bytes_received=r.bytes_received,
            info_sent={"intent": int(intent), "content": content, "delta": delta or []},
            info_received={"status": int(r.status), "content": r.content, "delta": self._reply_delta},
            latency_s=r.latency_s,
        )

    async def close(self) -> None:
        if self.client:
            await self.client.close()
        if self.server:
            await self.server.close()

    @property
    def client_ctx(self) -> dict:
        assert self.client
        return self.client.store.ctx

    @property
    def server_port(self) -> int:
        assert self.server
        return self.server.port


# ------------------------------------------------------------------ B1/B2: JSON-RPC over HTTP, full context


class JsonRpcSystem(System):
    full_context = True

    def __init__(self, encoding: str | None = None):
        self.encoding = encoding
        self.name = "jsonrpc" if encoding is None else f"jsonrpc-{encoding}"
        self.http_server: HttpServer | None = None
        self.http: HttpClient | None = None
        self.store: ContextStore | None = None
        self._ids = itertools.count(1)
        self.handler: Handler | None = None

    async def start(self, handler: Handler) -> None:
        self.handler = handler
        self.http_server = await HttpServer(self._route, host=self.listen_host).start()

    async def _route(self, path: str, headers: dict, body: bytes) -> tuple[int, bytes, dict]:
        req = json.loads(body)
        p = req["params"]
        ctx = p["context"]
        content = ctx["hist"][-1]["c"]  # the new message is the last history turn
        resp = await _call(
            self.handler, Request(intent=Intent[p["intent"].upper()], content=content, ctx=ctx, task_id=p.get("task_id"))
        )
        result = {"status": resp.status.name.lower(), "content": resp.content, "delta": delta_to_json(resp.delta)}
        return 200, dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), {}

    async def open(self, agent_id: str, ctx: dict, dictionary: list[str]) -> SetupResult:
        assert self.http_server or self.connect_port
        self.store = ContextStore(ctx, Dictionary())
        self.http = HttpClient(self.connect_host, self._client_port(), self.encoding)
        await self.http.connect()
        return SetupResult()  # stateless: nothing to set up

    async def request(self, intent, content, delta=None, task_id=None) -> RoundResult:
        assert self.http and self.store
        st = self.http.stats
        s0, r0, h0 = st.bytes_sent, st.bytes_received, st.header_bytes_sent + st.header_bytes_received
        t0 = _now()

        self.store.advance(CLIENT, intent, content, delta)
        params: dict[str, Any] = {"intent": intent.name.lower(), "context": self.store.ctx}
        if task_id is not None:
            params["task_id"] = task_id
        body = {"jsonrpc": "2.0", "id": next(self._ids), "method": "agent/message", "params": params}
        status, raw = await self.http.post("/mcp", dumps(body))
        if status != 200:
            raise RuntimeError(f"HTTP {status}: {raw[:200]!r}")
        result = json.loads(raw)["result"]

        rstatus = ReplyStatus[result["status"].upper()]
        rdelta = delta_from_json(result["delta"])
        self.store.advance(SERVER, rstatus, result["content"], rdelta)
        return RoundResult(
            status=rstatus,
            content=result["content"],
            bytes_sent=st.bytes_sent - s0,
            bytes_received=st.bytes_received - r0,
            header_bytes=st.header_bytes_sent + st.header_bytes_received - h0,
            info_sent=body,
            info_received=result,
            latency_s=_now() - t0,
        )

    async def close(self) -> None:
        if self.http:
            await self.http.close()
        if self.http_server:
            await self.http_server.close()

    @property
    def client_ctx(self) -> dict:
        assert self.store
        return self.store.ctx

    @property
    def server_port(self) -> int:
        return self.http_server.port  # type: ignore[union-attr]


# ------------------------------------------------------------------ B3: CBOR, full context


class CborFullSystem(System):
    """SayOnce's encoding (CBOR + dictionary, TCP framing) without shared context.

    The dictionary is exchanged once on connect, as codec configuration;
    every request then carries the full context.
    """

    name = "cbor-full"
    full_context = True

    def __init__(self) -> None:
        self.handler: Handler | None = None
        self._server: asyncio.base_events.Server | None = None
        self._server_conns: list[FramedConnection] = []
        self.port = 0
        self.conn: FramedConnection | None = None
        self.store: ContextStore | None = None
        self._seq = 0

    async def start(self, handler: Handler) -> None:
        self.handler = handler
        self._server = await asyncio.start_server(self._on_connection, self.listen_host, 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def _on_connection(self, reader, writer) -> None:
        conn = FramedConnection(reader, writer)
        conn.compress_threshold = None  # B3 isolates binary encoding: no compression
        self._server_conns.append(conn)
        try:
            setup = await conn.recv()
            d = Dictionary(setup.body[1])
            seq = 0
            while True:
                frame = await conn.recv()
                if frame.type == MessageType.BYE:
                    return
                ctx = d.expand(frame.body[2])
                req = Request(
                    intent=Intent(frame.body[0]), content=ctx["hist"][-1]["c"], ctx=ctx, task_id=frame.body.get(4)
                )
                resp = await _call(self.handler, req)
                body = {0: int(resp.status), 1: resp.content, 4: frame.seq}
                if resp.delta:
                    body[2] = _encode_delta(resp.delta, d)
                await conn.send(Frame(type=MessageType.REPLY, seq=seq, ctx_v=0, body=body))
                seq += 1
        except Exception:
            return
        finally:
            await conn.close()

    async def open(self, agent_id: str, ctx: dict, dictionary: list[str]) -> SetupResult:
        self.store = ContextStore(ctx, Dictionary(dictionary))
        self.conn = await FramedConnection.connect(self.connect_host, self._client_port())
        self.conn.compress_threshold = None
        await self.conn.send(Frame(type=MessageType.HELLO, seq=0, ctx_v=0, body={0: agent_id, 1: dictionary}))
        self._seq = 1
        st = self.conn.stats
        return SetupResult(st.bytes_sent, st.bytes_received, info_sent={"dictionary": dictionary})

    async def request(self, intent, content, delta=None, task_id=None) -> RoundResult:
        assert self.conn and self.store
        st = self.conn.stats
        s0, r0 = st.bytes_sent, st.bytes_received
        t0 = _now()

        self.store.advance(CLIENT, intent, content, delta)
        sent_ctx = self.store.ctx  # ContextStore replaces its dict on each step, so this stays as sent
        d = self.store.dictionary
        body: dict[int, Any] = {0: int(intent), 2: d.compress(sent_ctx)}
        if task_id is not None:
            body[4] = task_id
        await self.conn.send(Frame(type=MessageType.MSG, seq=self._seq, ctx_v=0, body=body))
        self._seq += 1

        frame = await self.conn.recv()
        rstatus = ReplyStatus(frame.body[0])
        rdelta = _decode_delta(frame.body.get(2, []), d)
        self.store.advance(SERVER, rstatus, frame.body[1], rdelta)
        return RoundResult(
            status=rstatus,
            content=frame.body[1],
            bytes_sent=st.bytes_sent - s0,
            bytes_received=st.bytes_received - r0,
            info_sent={"intent": int(intent), "context": sent_ctx},
            info_received={"status": int(rstatus), "content": frame.body[1], "delta": rdelta},
            latency_s=_now() - t0,
        )

    async def close(self) -> None:
        if self.conn:
            try:
                await self.conn.send(Frame(type=MessageType.BYE, seq=self._seq, ctx_v=0, body={}))
            except (ConnectionError, OSError):
                pass
            await self.conn.close()
        for c in list(self._server_conns):
            await c.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    @property
    def client_ctx(self) -> dict:
        assert self.store
        return self.store.ctx

    @property
    def server_port(self) -> int:
        return self.port


# ------------------------------------------------------------------ B4: JSON-RPC over HTTP, with delta


class JsonDeltaSystem(System):
    """SayOnce's shared-context idea, but with JSON over HTTP instead of CBOR over TCP."""

    name = "json-delta"
    full_context = False

    def __init__(self) -> None:
        self.handler: Handler | None = None
        self.http_server: HttpServer | None = None
        self.http: HttpClient | None = None
        self.store: ContextStore | None = None
        self.sessions: dict[str, ContextStore] = {}
        self._ids = itertools.count(1)
        self.session_id = ""

    async def start(self, handler: Handler) -> None:
        self.handler = handler
        self.http_server = await HttpServer(self._route, host=self.listen_host).start()

    async def _route(self, path: str, headers: dict, body: bytes) -> tuple[int, bytes, dict]:
        req = json.loads(body)
        p = req["params"]
        if req["method"] == "session/open":
            sid = f"s{len(self.sessions) + 1}"
            store = ContextStore(p["context"], Dictionary())
            self.sessions[sid] = store
            result = {"session_id": sid, "ctx_hash": store.hash.hex()}
            return 200, dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), {}

        store = self.sessions[p["session_id"]]
        intent = Intent[p["intent"].upper()]
        try:
            store.receive(CLIENT, intent, p["content"], delta_from_json(p["delta"]), p["ctx_version"],
                          bytes.fromhex(p["ctx_hash"]))
        except ResyncRequired as exc:
            err = {"code": -32000, "message": f"resync required: {exc.reason.name}"}
            return 409, dumps({"jsonrpc": "2.0", "id": req["id"], "error": err}), {}
        resp = await _call(self.handler, Request(intent=intent, content=p["content"], ctx=store.ctx, task_id=p.get("task_id")))
        step = store.advance(SERVER, resp.status, resp.content, resp.delta)
        result = {
            "status": resp.status.name.lower(),
            "content": resp.content,
            "delta": delta_to_json(resp.delta),
            "ctx_version": step.version,
            "ctx_hash": step.new_hash.hex(),
        }
        return 200, dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), {}

    async def open(self, agent_id: str, ctx: dict, dictionary: list[str]) -> SetupResult:
        assert self.http_server or self.connect_port
        self.store = ContextStore(ctx, Dictionary())
        self.http = HttpClient(self.connect_host, self._client_port())
        await self.http.connect()
        body = {"jsonrpc": "2.0", "id": next(self._ids), "method": "session/open",
                "params": {"agent_id": agent_id, "context": ctx}}
        status, raw = await self.http.post("/mcp", dumps(body))
        result = json.loads(raw)["result"]
        if bytes.fromhex(result["ctx_hash"]) != self.store.hash:
            raise RuntimeError("server stored a different context")
        self.session_id = result["session_id"]
        st = self.http.stats
        return SetupResult(st.bytes_sent, st.bytes_received, st.header_bytes_sent + st.header_bytes_received, body)

    async def request(self, intent, content, delta=None, task_id=None) -> RoundResult:
        assert self.http and self.store
        st = self.http.stats
        s0, r0, h0 = st.bytes_sent, st.bytes_received, st.header_bytes_sent + st.header_bytes_received
        t0 = _now()

        step = self.store.advance(CLIENT, intent, content, delta)
        params: dict[str, Any] = {
            "session_id": self.session_id,
            "intent": intent.name.lower(),
            "content": content,
            "delta": delta_to_json(delta or []),
            "ctx_version": step.version,
            "ctx_hash": step.new_hash.hex(),
        }
        if task_id is not None:
            params["task_id"] = task_id
        body = {"jsonrpc": "2.0", "id": next(self._ids), "method": "agent/message", "params": params}
        status, raw = await self.http.post("/mcp", dumps(body), {"Mcp-Session-Id": self.session_id})
        if status != 200:
            raise RuntimeError(f"HTTP {status}: {raw[:200]!r}")
        result = json.loads(raw)["result"]

        rstatus = ReplyStatus[result["status"].upper()]
        self.store.receive(SERVER, rstatus, result["content"], delta_from_json(result["delta"]),
                           result["ctx_version"], bytes.fromhex(result["ctx_hash"]))
        return RoundResult(
            status=rstatus,
            content=result["content"],
            bytes_sent=st.bytes_sent - s0,
            bytes_received=st.bytes_received - r0,
            header_bytes=st.header_bytes_sent + st.header_bytes_received - h0,
            info_sent=body,
            info_received=result,
            latency_s=_now() - t0,
        )

    async def close(self) -> None:
        if self.http:
            await self.http.close()
        if self.http_server:
            await self.http_server.close()

    @property
    def client_ctx(self) -> dict:
        assert self.store
        return self.store.ctx

    @property
    def server_port(self) -> int:
        return self.http_server.port  # type: ignore[union-attr]


# ------------------------------------------------------------------ registry

SYSTEMS = {
    "jsonrpc": lambda: JsonRpcSystem(),
    "jsonrpc-gzip": lambda: JsonRpcSystem("gzip"),
    "jsonrpc-zstd": lambda: JsonRpcSystem("zstd"),
    "cbor-full": CborFullSystem,
    "json-delta": JsonDeltaSystem,
    "sayonce-raw": lambda: SayOnceSystem(compress=False),
    "sayonce": SayOnceSystem,
}


def make_system(name: str) -> System:
    try:
        return SYSTEMS[name]()
    except KeyError:
        raise ValueError(f"unknown system {name!r}, choose from {sorted(SYSTEMS)}") from None


__all__ = [
    "SYSTEMS",
    "CborFullSystem",
    "JsonDeltaSystem",
    "JsonRpcSystem",
    "RoundResult",
    "SayOnceSystem",
    "SetupResult",
    "System",
    "make_system",
]
