"""SayOnce live demo: two agents in two terminals, or on two computers.

Start it with no arguments for a menu:

    python examples/live.py

or go straight to one side:

    python examples/live.py server --port 7474
    python examples/live.py client --host 192.168.1.23 --port 7474 --context-kb 20

The server is Agent B (a worker with a mock LLM). The client is Agent A: it
opens a session, sends the shared context once (HELLO), and then sends tasks
you type. Each round the client also replays the same conversation over the
JSON-RPC/HTTP baseline on this machine, so you see both byte counts side by
side. `/drop` cuts the connection and resumes the session without sending the
context again.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import socket
import sys
import time
from pathlib import Path

try:
    from sayonce.agents import WorkerAgent, sample_context
    from sayonce.bench.systems import JsonRpcSystem
    from sayonce.bench.workload import MCP_FILES, MCP_REQUESTS, mcp_context
    from sayonce.messages import DeltaOp, Intent
    from sayonce.session import ClientSession, Server, ServerSession, SessionError
    from sayonce.transport import ConnectionClosed, FramedConnection
except ImportError:  # running from a fresh clone without `pip install -e .`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from sayonce.agents import WorkerAgent, sample_context
    from sayonce.bench.systems import JsonRpcSystem
    from sayonce.bench.workload import MCP_FILES, MCP_REQUESTS, mcp_context
    from sayonce.messages import DeltaOp, Intent
    from sayonce.session import ClientSession, Server, ServerSession, SessionError
    from sayonce.transport import ConnectionClosed, FramedConnection

DEFAULT_PORT = 7474

SAMPLE_TASKS = [
    "Find the cheapest flight from Istanbul to Berlin next Friday",
    "Book a hotel near the conference center for two nights",
    "Compare economy and premium fares for the return leg",
    "Check whether the layover in Vienna is long enough",
    "Add travel insurance to the booking",
    "Find a rental car at the destination airport",
    "Summarise the total cost of the trip",
    "Move the departure one day earlier if it is cheaper",
    "Check the visa requirements for the trip",
    "Send the final itinerary to the traveller",
]

CONTEXTS = {
    "mcp": "real MCP tool definitions (filesystem, git, playwright, notion, ...)",
    "travel": "generated travel-agent context",
}


def make_context(kind: str, size_kb: int) -> tuple[dict, list[str]]:
    return mcp_context(size_kb) if kind == "mcp" else sample_context(size_kb)


def describe_tools(tools: dict) -> str:
    """'31 tool definitions from 5 MCP servers (time, fetch, ...)' or '53 tool definitions'."""
    servers = list(dict.fromkeys(name.split("__")[0] for name in tools if "__" in name))
    text = f"{len(tools)} tool definitions"
    if servers:
        text += f" from {len(servers)} MCP servers ({', '.join(servers)})"
    return text


# ---------------------------------------------------------------------- output


class Style:
    on = True  # ANSI colours
    uni = True  # box drawing and block characters
    anim = True  # small start-up animation

    @classmethod
    def enable(cls, on: bool, anim: bool = True) -> None:
        cls.on = on
        cls.anim = on and anim
        if on and os.name == "nt":
            os.system("")  # turns on ANSI escape codes in the Windows console
        try:
            "\u2588\u2557\u2501\u25c9\u25b8\u256d\u0394".encode(sys.stdout.encoding or "ascii")
            cls.uni = True
        except (UnicodeEncodeError, LookupError):
            cls.uni = False


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if Style.on else text


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def red(t: str) -> str:
    return _c("31", t)


def fmt_bytes(n: float) -> str:
    if n < 1024:
        return f"{n:.0f} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def json_size(obj) -> int:
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode())


def short(text, n: int = 60) -> str:
    s = str(text).replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def stamp() -> str:
    return dim(time.strftime("[%H:%M:%S]"))


# ---------------------------------------------------------------------- look and feel

# Brand gradient: cyan -> blue -> violet.
GRADIENT = [(0, 214, 255), (64, 120, 255), (150, 80, 255)]

LOGO = [
    "███████╗ █████╗ ██╗   ██╗ ██████╗ ███╗   ██╗ ██████╗███████╗",
    "██╔════╝██╔══██╗╚██╗ ██╔╝██╔═══██╗████╗  ██║██╔════╝██╔════╝",
    "███████╗███████║ ╚████╔╝ ██║   ██║██╔██╗ ██║██║     █████╗  ",
    "╚════██║██╔══██║  ╚██╔╝  ██║   ██║██║╚██╗██║██║     ██╔══╝  ",
    "███████║██║  ██║   ██║   ╚██████╔╝██║ ╚████║╚██████╗███████╗",
    "╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚══════╝",
]
LOGO_SMALL = [
    "░█▀▀░█▀█░█░█░█▀█░█▀█░█▀▀░█▀▀",
    "░▀▀█░█▀█░░█░░█░█░█░█░█░░░█▀▀",
    "░▀▀▀░▀░▀░░▀░░▀▀▀░▀░▀░▀▀▀░▀▀▀",
]
MAX_WIDTH = 62  # inner width of boxes on a wide terminal


def layout_width() -> int:
    """Inner box width that fits the current terminal (re-read every time)."""
    return max(30, min(MAX_WIDTH, term_width() - 6))


def _lerp(stops: list[tuple[int, int, int]], t: float) -> tuple[int, int, int]:
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    a, b = stops[i], stops[i + 1]
    return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))  # type: ignore[return-value]


def fg(rgb: tuple[int, int, int], text: str) -> str:
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{text}\033[0m" if Style.on else text


def badge(rgb: tuple[int, int, int], text: str) -> str:
    """Dark text on a coloured background, like a key cap."""
    if not Style.on:
        return f"[{text}]"
    return f"\033[1;38;2;15;18;30;48;2;{rgb[0]};{rgb[1]};{rgb[2]}m {text} \033[0m"


def gradient(text: str, stops=GRADIENT, bold_text: bool = False) -> str:
    if not Style.on:
        return text
    n = max(len(text) - 1, 1)
    b = "1;" if bold_text else ""
    out = []
    for i, ch in enumerate(text):
        r, g, bl = _lerp(stops, i / n)
        out.append(f"\033[{b}38;2;{r};{g};{bl}m{ch}" if ch != " " else ch)
    return "".join(out) + "\033[0m"


def term_width() -> int:
    import shutil

    return shutil.get_terminal_size((80, 24)).columns


def clear_screen() -> None:
    if Style.on:
        print("\033[2J\033[H", end="")


def rule(char_uni: str = "━", char_ascii: str = "=") -> str:
    return gradient((char_uni if Style.uni else char_ascii) * (layout_width() + 2))


def banner(title: str, subtitle: str = "") -> None:
    print()
    print("  " + rule())
    if subtitle and len(title) + len(subtitle) + 4 <= layout_width():
        print("   " + gradient(title, bold_text=True) + "   " + dim(subtitle))
    else:
        print("   " + gradient(title, bold_text=True))
        if subtitle:
            print("   " + dim(subtitle))
    print("  " + rule())


def box(rows: list[tuple[str, int]]) -> list[str]:
    """Draw rows (coloured text, visible length) inside a rounded box."""
    if Style.uni:
        tl, tr, bl, br, h, v = "╭", "╮", "╰", "╯", "─", "│"
    else:
        tl, tr, bl, br, h, v = "+", "+", "+", "+", "-", "|"
    edge = lambda t: fg((70, 90, 150), t)  # noqa: E731
    w = layout_width()
    out = ["  " + edge(tl + h * w + tr)]
    for text, width in rows:
        out.append("  " + edge(v) + text + " " * max(w - width, 0) + edge(v))
    out.append("  " + edge(bl + h * w + br))
    return out


def strip_length() -> int:
    """Length of the link between the two agents so the whole line fits on one row."""
    # 5 indent + "◉ Agent A " (10) + link + " Agent B ◉" (10) + 1 spare column
    return max(8, min(34, term_width() - 26))


def network_strip(frame: int | None = None, packet: str = "", total: int = 34) -> str:
    """Agent A ━━━━ Agent B with an optional packet at position `frame`."""
    node = "◉" if Style.uni else "o"
    line = "━" if Style.uni else "-"
    left = fg((0, 214, 255), f"{node} Agent A ")
    right = fg((150, 80, 255), f" Agent B {node}")
    cells = []
    for i in range(total):
        if frame is not None and frame <= i < frame + len(packet):
            cells.append(packet[i - frame])
        else:
            cells.append(line)
    track = "".join(cells)
    if frame is None or not Style.on:
        track = fg((70, 90, 150), track)
    else:
        a, b = track[:frame], track[frame : frame + len(packet)]
        c = track[frame + len(packet) :]
        col = (255, 170, 60) if len(packet) > 2 else (120, 255, 170)
        track = fg((70, 90, 150), a) + fg(col, b) + fg((70, 90, 150), c)
    return "     " + left + track + right


def animate_link() -> None:
    """One big HELLO crosses the link, then a few tiny deltas."""
    total = strip_length()
    big = ("█HELLO█" if Style.uni else "[HELLO]") if total >= 14 else ("███" if Style.uni else "[H]")
    small = "•" if Style.uni else "*"
    if Style.anim and sys.stdout.isatty():
        step_big = max(1, total // 14)
        step_small = max(1, total // 11)
        for packet, step, delay in ((big, step_big, 0.03), (small, step_small, 0.012),
                                    (small, step_small, 0.012), (small, step_small, 0.012)):
            for f in range(0, total - len(packet) + 1, step):
                # \r goes back to the start of the row and \033[2K clears it, so frames overwrite each other
                print("\r\033[2K" + network_strip(f, packet, total), end="", flush=True)
                time.sleep(delay)
        print("\r\033[2K" + network_strip(None, "", total))
    else:
        print(network_strip(None, "", total))
    delta = "Δ" if Style.uni else "delta"
    first = dim("1x ") + fg((255, 170, 60), "HELLO") + dim(" = the context, once")
    then = dim("then ") + fg((120, 255, 170), delta) + dim(" = only changes")
    if term_width() >= 64:
        print("       " + first + "    " + then)
    else:
        print("       " + first)
        print("       " + then)


def print_logo() -> None:
    cols = term_width()
    delay = 0.025 if Style.anim and sys.stdout.isatty() else 0
    if Style.uni and cols >= len(LOGO[0]) + 5:
        rows = LOGO
    elif Style.uni and cols >= len(LOGO_SMALL[0]) + 5:
        rows = LOGO_SMALL
    else:
        rows = []
        print("   " + gradient("S A Y O N C E", bold_text=True))
    for row in rows:
        print("   " + gradient(row))
        time.sleep(delay)
    for tagline in ("a token- and bandwidth-efficient protocol for AI agents",
                    "token- and bandwidth-efficient agent protocol",
                    "efficient agent protocol"):
        if cols >= len(tagline) + 4:
            print("   " + dim(tagline))
            break


def local_ips() -> list[str]:
    """IPv4 addresses other computers can use to reach this one."""
    ips: list[str] = []
    try:  # the address of the default route; a UDP connect sends no packets
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


# ---------------------------------------------------------------------- server


def _vars_diff(old: dict, new: dict) -> list[str]:
    out = []
    for k in sorted(set(old) | set(new)):
        if k in ("status", "last_task"):  # bookkeeping written by the worker itself
            continue
        if old.get(k) != new.get(k):
            if k not in new:
                out.append(f"{k} removed")
            elif k not in old:
                out.append(f"{k} = {new[k]!r}")
            else:
                out.append(f"{k}: {old[k]!r} -> {new[k]!r}")
    return out


class LiveServerSession(ServerSession):
    """A ServerSession that prints what arrives. Protocol behaviour is unchanged."""

    def __init__(self, server: "LiveServer", conn):
        super().__init__(server, conn)
        self.peer = "?"
        try:
            host, port = conn._writer.get_extra_info("peername")[:2]
            self.peer = f"{host}:{port}"
        except Exception:
            pass
        self._recv_mark = 0
        self._sent_mark = 0

    def _take(self) -> tuple[int, int]:
        st = self.conn.stats
        r, s = st.bytes_received - self._recv_mark, st.bytes_sent - self._sent_mark
        self._recv_mark, self._sent_mark = st.bytes_received, st.bytes_sent
        return r, s

    def _sid(self) -> str:
        return self.session_id.hex()[:8] if self.session_id else "--------"

    async def _handshake(self) -> None:
        known = set(self.server.sessions)
        await super()._handshake()
        recv, sent = self._take()
        ctx_size = fmt_bytes(json_size(self.store.ctx))
        if self.session_id in known:
            print(f"{stamp()} {green('RESUME')}   from {self.peer}   session {self._sid()}")
            print(f"           received {bold(fmt_bytes(recv))}: session id, version {self.store.version}, hash and key dictionary")
            print(f"           context ({ctx_size}) is still here, {green('nothing re-sent')}")
        elif self.store.version == 0 and not self.store.ctx["tools"] and not self.store.ctx["sys"]:
            print(f"{stamp()} {yellow('RESUME?')}  from {self.peer}: this server does not know that session")
            print("           (it was restarted?) -> asking the client for its context (SNAPSHOT)")
        else:
            print(f"{stamp()} {cyan('HELLO')}    from {self.peer}   new session {self._sid()}")
            print(f"           received {bold(fmt_bytes(recv))} (compressed): the full shared context, {ctx_size} as JSON")
            print(f"           {describe_tools(self.store.ctx['tools'])}")
            print(f"           vars: {self.store.ctx['vars']}")
            print(f"           {dim('this is the only time the context crosses the network')}")
        print()

    async def _load_snapshot(self, snap) -> None:
        await super()._load_snapshot(snap)
        recv, _ = self._take()
        print(f"{stamp()} {yellow('SNAPSHOT')} received {bold(fmt_bytes(recv))}: full context re-sent once "
              f"(v{self.store.version}), session {self._sid()} continues")
        print()

    async def _send_snapshot(self) -> None:
        await super()._send_snapshot()
        print(f"{stamp()} {yellow('RESYNC')}   contexts disagreed, sent our snapshot to the client")

    async def _on_msg(self, seq, ctx_v, msg) -> None:
        v0 = self.store.version
        vars0 = dict(self.store.ctx["vars"])
        await super()._on_msg(seq, ctx_v, msg)
        recv, sent = self._take()
        self.server.rounds += 1
        changes = _vars_diff(vars0, self.store.ctx["vars"])
        print(f"{stamp()} {cyan('MSG')}      #{msg.task_id if msg.task_id is not None else '-'}   "
              f"received {bold(fmt_bytes(recv))}   context v{v0} -> v{self.store.version}")
        print(f"           task:    {short(msg.content, 70)!r}")
        if changes:
            print(f"           delta:   {yellow(', '.join(changes))}")
        print(f"           reply:   {fmt_bytes(sent)}   "
              f"{dim('context held here: ' + fmt_bytes(json_size(self.store.ctx)) + ', not re-sent')}")
        print()

    async def run(self) -> None:
        try:
            await super().run()
        finally:
            if self.session_id:
                print(f"{stamp()} {dim('connection from ' + self.peer + ' closed; session ' + self._sid() + ' kept for resume')}")
                print()


class LiveServer(Server):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rounds = 0

    async def _on_connection(self, reader, writer) -> None:
        conn = FramedConnection(reader, writer)
        conn.compress_threshold = self.compress_threshold
        session = LiveServerSession(self, conn)
        self.connections.append(session)
        try:
            await session.run()
        finally:
            self.connections.remove(session)
            await session.conn.close()


async def run_server(port: int) -> None:
    server = LiveServer(WorkerAgent(), agent_id="agent-b", host="0.0.0.0", port=port)
    try:
        await server.start()
    except OSError as exc:
        print(red(f"Could not listen on port {port}: {exc}"))
        print("Is another server already running? Try another port with --port.")
        return
    banner("SayOnce server", "Agent B  ·  worker with a mock LLM" if Style.uni else "Agent B - worker with a mock LLM")
    print(f"  Listening on port {bold(str(server.port))}")
    ips = local_ips()
    if ips:
        print("  Clients on other computers connect to:")
        for ip in ips:
            print(f"      {bold(ip)}  port {server.port}")
    print(f"  Clients on this computer connect to: {bold('127.0.0.1')}  port {server.port}")
    print(dim("  Windows may ask to allow Python through the firewall: allow it on private networks."))
    print(dim("  Press Ctrl+C to stop."))
    print()
    try:
        await asyncio.Event().wait()
    finally:
        await server.close()


# ---------------------------------------------------------------------- client


async def async_input(prompt: str) -> str:
    """input() in a daemon thread, so Ctrl+C never waits for a pending line."""
    import threading

    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    def reader() -> None:
        try:
            line = input(prompt)
        except BaseException as exc:  # EOFError, KeyboardInterrupt
            if not fut.done():
                loop.call_soon_threadsafe(fut.set_exception, EOFError(str(exc)))
            return
        if not fut.done():
            loop.call_soon_threadsafe(fut.set_result, line)

    threading.Thread(target=reader, daemon=True).start()
    return await fut


def parse_value(text: str):
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return text


class LiveClient:
    def __init__(self, host: str, port: int, context_kb: int, compare: bool = True, context: str = "mcp"):
        self.host, self.port, self.context_kb = host, port, context_kb
        self.context = context
        self.compare = compare
        self.session: ClientSession | None = None
        self.baseline: JsonRpcSystem | None = None
        self.task_id = 0
        self.so_total = 0  # SayOnce bytes, both directions, all connections
        self.rpc_total = 0
        self.so_conn_base = 0  # bytes of connections closed by /drop

    def _so_now(self) -> int:
        st = self.session.conn.stats if self.session else None
        return self.so_conn_base + (st.bytes_sent + st.bytes_received if st else 0)

    async def start(self) -> bool:
        try:
            ctx, dictionary = make_context(self.context, self.context_kb)
        except ValueError as exc:
            print(red(f"  {exc}"))
            return False
        banner("SayOnce client", "Agent A  ·  the requester" if Style.uni else "Agent A - the requester")
        print(f"  Connecting to {bold(f'{self.host}:{self.port}')} ...")
        try:
            self.session = await asyncio.wait_for(
                ClientSession.open(self.host, self.port, "agent-a", copy.deepcopy(ctx), dictionary), 10
            )
        except (OSError, asyncio.TimeoutError, SessionError) as exc:
            print(red(f"  Could not connect: {exc or type(exc).__name__}"))
            print("  Check that the server is running, the IP and port are right, both computers are on")
            print("  the same network, and the firewall on the server computer allows Python.")
            return False
        st = self.session.conn.stats
        print(f"  {cyan('HELLO')} sent {bold(fmt_bytes(st.bytes_sent))} (compressed): shared context of "
              f"{fmt_bytes(json_size(ctx))} as JSON")
        print(f"  {describe_tools(ctx['tools'])}")
        print(f"  Session {self.session.session_id.hex()[:8]} with {self.session.peer_id}. "
              f"{dim('From now on only new messages and deltas are sent.')}")

        if self.compare:
            # The same conversation over the JSON-RPC/HTTP baseline, run on this machine.
            self.baseline = JsonRpcSystem()
            await self.baseline.start(WorkerAgent())
            await self.baseline.open("agent-a", copy.deepcopy(ctx), dictionary)
            print(dim("  For comparison, every round is also replayed over JSON-RPC/HTTP (MCP-style) on this"))
            print(dim("  computer. JSON-RPC is stateless, so it carries the whole context in every request."))
        print()
        self.so_total = self._so_now()
        self.print_help()
        return True

    def print_help(self) -> None:
        print(bold("  Commands"))
        print("    <any text>         send it to Agent B as a task")
        example = "/set active_file src/app.py" if self.context == "mcp" else "/set budget 450"
        print(f"    /set KEY VALUE     change a shared variable, e.g. {example} (sent as a delta)")
        print("    /auto N            send N sample tasks, one per second (default 5)")
        print("    /drop              cut the connection and resume the session")
        print("    /stats             totals so far")
        print("    /help              this list")
        print("    /quit              close the session and exit")
        print()

    async def send(self, text: str, delta: list | None = None, intent: Intent = Intent.REQUEST) -> None:
        assert self.session
        tid = self.task_id + 1
        before = self.session.store.checkpoint()
        try:
            res = await self.session.request(intent, text, delta=delta, task_id=tid)
        except (SessionError, ConnectionClosed, ConnectionError, OSError):
            # The message never got an answer: take it back out of our context, so it does not
            # become shared history. If the server did apply it, the resume finds the hashes
            # differ and the client re-sends its context (SNAPSHOT), so both sides agree again.
            self.session.store.restore(before)
            print(yellow(f"  Message not delivered; it was not added to the shared context (still v{before.version})."))
            raise
        self.task_id = tid
        self.so_total = self._so_now()
        line = (f"  {cyan(f'#{tid}')} {short(text, 58)!r}\n"
                f"     {green('SayOnce ')}  sent {bold(f'{fmt_bytes(res.bytes_sent):>9}')}   "
                f"received {fmt_bytes(res.bytes_received):>9}   {res.latency_s * 1000:6.1f} ms   "
                f"total {fmt_bytes(self.so_total)}")
        if res.resyncs:
            line += yellow(f"   ({res.resyncs} resync)")
        print(line)
        if self.baseline:
            r = await self.baseline.request(intent, text, delta=copy.deepcopy(delta), task_id=tid)
            self.rpc_total += r.bytes_total
            print(f"     {red('JSON-RPC')}  sent {fmt_bytes(r.bytes_sent):>9}   received {fmt_bytes(r.bytes_received):>9}"
                  f"               total {fmt_bytes(self.rpc_total)}")
            ratio_round = r.bytes_sent / max(res.bytes_sent, 1)
            ratio_total = self.rpc_total / max(self.so_total, 1)
            print(f"     {dim(f'this round SayOnce sent {ratio_round:.0f}x less; so far {ratio_total:.1f}x less in total (setup included)')}")
        print(f"     reply: {dim(short(res.content, 70))}")
        print()

    async def set_var(self, key: str, value) -> None:
        delta = [[DeltaOp.SET, ["vars", key], value]]
        print(f"  {yellow('delta')}: vars.{key} = {value!r}")
        await self.send(f"{key} is now {value}", delta=delta, intent=Intent.INFORM)

    async def drop(self) -> None:
        assert self.session
        old = self.session
        self.so_conn_base += old.conn.stats.bytes_sent + old.conn.stats.bytes_received
        try:
            await old.close(bye=False)  # no BYE: looks like a lost connection to the server
        except (ConnectionClosed, ConnectionError, OSError):
            pass  # already broken
        self.session = None
        print(f"  {red('Connection dropped')} (no goodbye sent; to the server it looks like a lost link).")
        await asyncio.sleep(1.5)
        print(f"  Reconnecting to {self.host}:{self.port} and resuming session {old.session_id.hex()[:8]} ...")
        try:
            self.session = await asyncio.wait_for(ClientSession.resume(self.host, self.port, old), 10)
        except (OSError, asyncio.TimeoutError, SessionError, ConnectionClosed) as exc:
            print(red(f"  Resume failed: {exc or type(exc).__name__}. Is the server still running?"))
            self.session = old  # keep state so totals stay right; the next command will fail cleanly
            self.so_conn_base -= old.conn.stats.bytes_sent + old.conn.stats.bytes_received
            raise SessionError("not connected") from exc
        st = self.session.conn.stats
        self.so_total = self._so_now()
        if self.session.resumed:
            print(f"  {green('RESUMED')}: sent {bold(fmt_bytes(st.bytes_sent))} (session id, version "
                  f"{self.session.store.version}, hash, key dictionary). The context was {green('not')} sent again.")
        else:
            print(f"  {yellow('Server did not know the session')} (was it restarted?). Sent the context once "
                  f"as a SNAPSHOT: {bold(fmt_bytes(st.bytes_sent))}. The session continues at "
                  f"v{self.session.store.version}.")
        if self.baseline:
            print(dim("  JSON-RPC has nothing to resume: it is stateless, and pays for that by re-sending"))
            print(dim("  the whole context in every single request."))
        print()

    def stats(self) -> None:
        s = self.session
        print(bold("  Totals (both directions, setup included)"))
        print(f"    rounds:          {self.task_id}")
        print(f"    SayOnce:         {fmt_bytes(self.so_total)}")
        if self.baseline:
            print(f"    JSON-RPC:        {fmt_bytes(self.rpc_total)}   "
                  f"({self.rpc_total / max(self.so_total, 1):.1f}x more)")
        if s:
            print(f"    context:         v{s.store.version}, {fmt_bytes(json_size(s.store.ctx))} as JSON, "
                  f"hash {s.store.hash.hex()[:12]}")
            print(f"    session:         {s.session_id.hex()[:8]}, resyncs {s.resync_count}")
        print()

    async def close(self) -> None:
        if self.session:
            try:
                await self.session.close()
            except (ConnectionClosed, ConnectionError, OSError):
                pass
        if self.baseline:
            await self.baseline.close()

    async def handle(self, line: str) -> bool:
        """Run one command. Returns False to quit."""
        line = line.strip()
        if not line:
            return True
        if not line.startswith("/"):
            await self.send(line)
            return True
        cmd, *args = line.split(maxsplit=2)
        cmd = cmd.lower()
        if cmd in ("/quit", "/exit", "/q"):
            return False
        if cmd == "/help":
            self.print_help()
        elif cmd == "/stats":
            self.stats()
        elif cmd == "/set":
            if len(args) < 2:
                print("  usage: /set KEY VALUE   e.g. " + ("/set active_file src/app.py" if self.context == "mcp"
                                                       else "/set budget 450"))
            else:
                await self.set_var(args[0], parse_value(args[1]))
        elif cmd == "/auto":
            try:
                n = int(args[0]) if args else 5
            except ValueError:
                print("  usage: /auto N")
                return True
            await self.auto(n)
        elif cmd == "/drop":
            await self.drop()
        else:
            print(f"  unknown command {cmd}; type /help")
        return True

    async def auto(self, n: int, interval: float = 1.0) -> None:
        for i in range(n):
            k = self.task_id
            if self.context == "mcp":
                if k % 3 == 2:  # now and then the requester switches to another file
                    await self.set_var("active_file", MCP_FILES[k % len(MCP_FILES)])
                else:
                    await self.send(MCP_REQUESTS[k % len(MCP_REQUESTS)])
            elif k % 3 == 2:  # now and then the requester lowers the budget a little
                budget = self.session.store.ctx["vars"].get("budget") if self.session else None
                await self.set_var("budget", budget - 25 if isinstance(budget, (int, float)) else 500)
            else:
                await self.send(SAMPLE_TASKS[k % len(SAMPLE_TASKS)])
            if i < n - 1:
                await asyncio.sleep(interval)


async def run_client(host: str, port: int, context_kb: int, auto: int | None, compare: bool,
                     context: str = "mcp") -> None:
    client = LiveClient(host, port, context_kb, compare, context)
    if not await client.start():
        return
    try:
        if auto is not None:
            await client.auto(auto)
            client.stats()
            return
        while True:
            try:
                line = await async_input(green("agent-a> "))
            except EOFError:
                break
            try:
                if not await client.handle(line):
                    break
            except (SessionError, ConnectionClosed, ConnectionError, OSError) as exc:
                print(red(f"  Connection problem: {exc or type(exc).__name__}"))
                print("  Type /drop to reconnect, or /quit.")
                print()
    finally:
        await client.close()
        print(dim("  Session closed."))


# ---------------------------------------------------------------------- menu


def ask(prompt: str, default: str) -> str:
    value = input(f"  {prompt} [{default}]: ").strip()
    return value or default


def ask_host(default: str = "127.0.0.1") -> str:
    """An IP address or host name; anything with spaces is rejected."""
    import re

    while True:
        value = ask("Server IP address (press Enter for this computer)", default)
        if re.fullmatch(r"[A-Za-z0-9.\-:]+", value) and not value.endswith(":"):
            return value
        print(red(f"  {value!r} is not an address. Type an IP such as 192.168.1.23, or just press Enter."))


def ask_context() -> str:
    print("  Shared context:")
    print(f"      1  {CONTEXTS['mcp']}")
    print(f"      2  {CONTEXTS['travel']}")
    while True:
        value = ask("Choose", "1")
        if value in ("1", "mcp"):
            return "mcp"
        if value in ("2", "travel"):
            return "travel"
        print(red("  Please choose 1 or 2."))


def ask_int(prompt: str, default: int) -> int:
    while True:
        value = ask(prompt, str(default))
        try:
            return int(value)
        except ValueError:
            print(red("  Please enter a number."))


def network_help() -> None:
    print(bold("  Running on two computers"))
    print("   1. Put both computers on the same network. University Wi-Fi often blocks devices from")
    print("      reaching each other; a phone hotspot is the safest choice.")
    print("   2. On the server computer choose option 1 (server). It prints its IP address.")
    print("      If Windows asks about the firewall, allow Python on private networks.")
    print("   3. On the other computer choose option 2 (client) and enter that IP and port.")
    print("   4. Optional: in Wireshark, capture with the filter  tcp.port == 7474  to see the")
    print("      single large HELLO followed by small messages.")
    print()
    print(bold("  On one computer"))
    print("   Open two terminals (in VS Code: the split terminal button). Start the server in one and")
    print("   the client in the other with host 127.0.0.1.")
    print()


MENU = [  # key, badge colour, title, description, short description
    ("1", (0, 214, 255), "Start the server", "Agent B  ·  the worker", "Agent B"),
    ("2", (90, 230, 160), "Start the client", "Agent A  ·  the requester", "Agent A"),
    ("3", (255, 190, 80), "Network info", "this computer's IP addresses", "my IP"),
    ("4", (170, 120, 255), "Two-computer guide", "hotspot, firewall, Wireshark", "setup help"),
    ("q", (255, 95, 110), "Quit", "", ""),
]


def print_menu(first: bool) -> None:
    if first:
        clear_screen()
        print()
        print_logo()
        print()
        animate_link()
    else:
        banner("SayOnce live demo", "say the context once, then send only changes")
    print()
    rows: list[tuple[str, int]] = [("", 0)]
    sep = "·" if Style.uni else "-"
    room = layout_width() - 2 - 3 - 2 - 20 - 1  # left pad, badge, gap, title column, right margin
    long_fits = all(len(m[3]) <= room for m in MENU)
    for key, rgb, title, desc, short_desc in MENU:
        desc = desc.replace("·", sep) if long_fits else short_desc
        if len(desc) > room:
            desc = ""
        plain = f"  [{key}]  {title:<20}{desc}" if not Style.on else f"   {key}   {title:<20}{desc}"
        text = "  " + badge(rgb, key) + "  " + bold(f"{title:<20}") + dim(desc)
        rows.append((text, len(plain)))
    rows.append(("", 0))
    for line in box(rows):
        print(line)
    ips = local_ips()
    dot = "◦" if Style.uni else "-"
    info = f"   {dot} IP {ips[0] if ips else 'offline'}   {dot} port {DEFAULT_PORT}   {dot} host {socket.gethostname()}"
    info = info[: term_width() - 1]
    print(dim(info))
    print()


def menu() -> None:
    first = True
    while True:
        print_menu(first)
        first = False
        arrow = "❯" if Style.uni else ">"
        choice = input("  " + gradient(arrow, bold_text=True) + " " + bold("Choose an option: ")).strip().lower()
        print()
        if choice == "1":
            port = ask_int("Port", DEFAULT_PORT)
            print()
            _run(run_server(port))
        elif choice == "2":
            host = ask_host()
            port = ask_int("Port", DEFAULT_PORT)
            context = ask_context()
            kb = ask_int("Shared context size in KB", 20)
            print(dim("  After connecting, type your tasks and commands at the  agent-a>  prompt."))
            print()
            _run(run_client(host, port, kb, None, True, context))
        elif choice == "3":
            ips = local_ips()
            if ips:
                print("  This computer's addresses:")
                for ip in ips:
                    print(f"      {bold(ip)}")
            else:
                print("  No network address found. Is this computer connected to a network?")
        elif choice == "4":
            network_help()
        elif choice in ("q", "quit", "exit"):
            print(dim("  Bye."))
            return
        else:
            print(red("  Please choose 1, 2, 3, 4 or q."))


def _run(coro) -> None:
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        print()
        print(dim("  Stopped."))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--no-color", action="store_true", help="plain text output")
    p.add_argument("--no-anim", action="store_true", help="skip the start-up animation")
    sub = p.add_subparsers(dest="mode")
    ps = sub.add_parser("server", help="start Agent B")
    ps.add_argument("--port", type=int, default=DEFAULT_PORT)
    pc = sub.add_parser("client", help="start Agent A")
    pc.add_argument("--host", default="127.0.0.1")
    pc.add_argument("--port", type=int, default=DEFAULT_PORT)
    pc.add_argument("--context-kb", type=int, default=20)
    pc.add_argument("--context", choices=list(CONTEXTS), default="mcp",
                    help="real MCP tool definitions (default) or the generated travel context")
    pc.add_argument("--auto", type=int, metavar="N", help="send N sample tasks and exit")
    pc.add_argument("--no-compare", action="store_true", help="do not replay rounds over JSON-RPC")
    args = p.parse_args()

    Style.enable(not args.no_color and sys.stdout.isatty(), anim=not args.no_anim)
    if args.mode == "server":
        _run(run_server(args.port))
    elif args.mode == "client":
        _run(run_client(args.host, args.port, args.context_kb, args.auto, not args.no_compare, args.context))
    else:
        try:
            menu()
        except (KeyboardInterrupt, EOFError):
            print()


if __name__ == "__main__":
    main()
