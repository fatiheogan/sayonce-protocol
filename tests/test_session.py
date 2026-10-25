import asyncio

import cbor2

from sayonce.agents import MockLLM, WorkerAgent, render_prompt, sample_context
from sayonce.codec import Frame
from sayonce.messages import DeltaOp, ErrorCode, Intent, MessageType, ReplyStatus
from sayonce.session import ClientSession, Response, Server
from sayonce.transport import FramedConnection


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


async def open_pair(handler=None, size_kb=5):
    server = await Server(handler or WorkerAgent(), agent_id="B").start()
    ctx, d = sample_context(size_kb)
    client = await ClientSession.open("127.0.0.1", server.port, "A", ctx, d)
    return server, client


def server_store(server, client):
    return server.sessions[client.session_id]


# ---------------------------------------------------------------- happy path


def test_ten_rounds_stay_in_sync():
    async def main():
        server, client = await open_pair()
        try:
            for i in range(10):
                res = await client.request(Intent.REQUEST, f"task {i}", task_id=i,
                                           delta=[[DeltaOp.SET, ["vars", "round"], i]])
                assert res.status == ReplyStatus.OK and res.resyncs == 0
            s = server_store(server, client)
            assert client.store.version == s.version == 20
            assert client.store.hash == s.hash and client.store.ctx == s.ctx
            assert client.store.ctx["vars"]["last_task"] == 9
            assert client.peer_id == "B"
        finally:
            await client.close()
            await server.close()

    run(main())


def test_context_is_sent_only_once():
    async def main():
        server, client = await open_pair(size_kb=20)
        try:
            hello_bytes = client.conn.stats.bytes_sent
            res = await client.request(Intent.REQUEST, "short question")
            assert hello_bytes > 10_000
            assert res.bytes_sent < 200  # only the new message travels
        finally:
            await client.close()
            await server.close()

    run(main())


def test_inform_and_cancel_intents():
    async def main():
        server, client = await open_pair()
        try:
            assert (await client.request(Intent.INFORM, "fyi")).content == "ack"
            await client.request(Intent.CANCEL, None, task_id=1)
            assert client.store.ctx["vars"]["status"] == "cancelled"
        finally:
            await client.close()
            await server.close()

    run(main())


def test_async_handler():
    async def handler(req):
        await asyncio.sleep(0)
        return Response(content=len(req.ctx["hist"]))

    async def main():
        server, client = await open_pair(handler)
        try:
            assert (await client.request(Intent.REQUEST, "x")).content == 1
            assert (await client.request(Intent.REQUEST, "y")).content == 3
        finally:
            await client.close()
            await server.close()

    run(main())


# ---------------------------------------------------------------- resync


def test_resync_when_server_context_corrupted():
    """Server-side divergence: server sends RESYNC, client rolls back, sends SNAPSHOT, retries."""

    async def main():
        server, client = await open_pair()
        try:
            await client.request(Intent.REQUEST, "first")
            server_store(server, client)._ctx["vars"]["budget"] = -1  # simulate a bug / restart

            res = await client.request(Intent.REQUEST, "second")
            assert res.status == ReplyStatus.OK and res.resyncs == 1
            s = server_store(server, client)
            assert s.hash == client.store.hash and s.ctx["vars"]["budget"] == 500
            # "second" must be in history exactly once despite the retry
            assert [t["c"] for t in s.ctx["hist"] if t["r"] == "c"] == ["first", "second"]

            await client.request(Intent.REQUEST, "third")  # continues normally
            assert server_store(server, client).hash == client.store.hash
        finally:
            await client.close()
            await server.close()

    run(main())


def test_resync_when_client_context_corrupted():
    """Client-side divergence: REPLY hash fails, client sends RESYNC, server sends SNAPSHOT."""

    async def main():
        server, client = await open_pair()
        try:
            await client.request(Intent.REQUEST, "first")
            # Make the client diverge after its MSG was accepted, i.e. before the REPLY is applied.
            orig_send_msg = client._send_msg

            async def send_then_corrupt(*a, **kw):
                seq = await orig_send_msg(*a, **kw)
                client.store._ctx["vars"]["budget"] = -1
                return seq

            client._send_msg = send_then_corrupt
            res = await client.request(Intent.REQUEST, "second")
            client._send_msg = orig_send_msg

            assert res.resyncs == 1 and res.status == ReplyStatus.OK
            s = server_store(server, client)
            assert client.store.hash == s.hash and client.store.ctx["vars"]["budget"] == 500
        finally:
            await client.close()
            await server.close()

    run(main())


def test_resync_when_frame_corrupted_in_transit():
    async def main():
        server, client = await open_pair()
        corrupted = []

        def fault(frame: Frame):
            if frame.type == MessageType.MSG and not corrupted:
                corrupted.append(frame.seq)
                body = dict(frame.body)
                body[1] = "tampered"  # content changed, hash no longer matches
                return Frame(type=frame.type, seq=frame.seq, ctx_v=frame.ctx_v, body=body)
            return frame

        try:
            client.conn.fault = fault
            res = await client.request(Intent.REQUEST, "original")
            assert corrupted and res.resyncs == 1
            s = server_store(server, client)
            assert s.hash == client.store.hash
            assert "tampered" not in [t["c"] for t in s.ctx["hist"]]
        finally:
            await client.close()
            await server.close()

    run(main())


# ---------------------------------------------------------------- resume


def test_resume_after_connection_drop():
    async def main():
        server, client = await open_pair(size_kb=20)
        try:
            hello_bytes = client.conn.stats.bytes_sent
            await client.request(Intent.REQUEST, "before drop")
            await client.close(bye=False)  # connection lost, no BYE

            client2 = await ClientSession.resume("127.0.0.1", server.port, client)
            assert client2.resumed and client2.session_id == client.session_id
            # Only the dictionary and resume token travel again, not the context.
            assert client2.conn.stats.bytes_sent < hello_bytes * 0.1

            await client2.request(Intent.REQUEST, "after drop")
            assert server_store(server, client2).hash == client2.store.hash
            await client2.close()
        finally:
            await server.close()

    run(main())


def test_resume_on_server_that_lost_the_session():
    async def main():
        server, client = await open_pair()
        await client.request(Intent.REQUEST, "hello")
        await client.close(bye=False)
        await server.close()

        new_server = await Server(WorkerAgent(), agent_id="B2").start()  # fresh, knows nothing
        try:
            client2 = await ClientSession.resume("127.0.0.1", new_server.port, client)
            assert not client2.resumed
            res = await client2.request(Intent.REQUEST, "still there?")
            assert res.status == ReplyStatus.OK
            s = new_server.sessions[client2.session_id]
            assert s.hash == client2.store.hash and len(s.ctx["hist"]) == 4
            await client2.close()
        finally:
            await new_server.close()

    run(main())


# ---------------------------------------------------------------- errors


def test_handler_exception_returns_failed():
    def handler(req):
        if req.content == "boom":
            raise RuntimeError("bad")
        return Response(content="ok")

    async def main():
        server, client = await open_pair(handler)
        try:
            res = await client.request(Intent.REQUEST, "boom")
            assert res.status == ReplyStatus.FAILED and "bad" in res.content
            assert (await client.request(Intent.REQUEST, "fine")).content == "ok"
            assert server_store(server, client).hash == client.store.hash
        finally:
            await client.close()
            await server.close()

    run(main())


def test_handler_invalid_delta_returns_failed():
    async def main():
        server, client = await open_pair(lambda req: Response(content="x", delta=[[DeltaOp.DEL, ["vars", "nope"]]]))
        try:
            res = await client.request(Intent.REQUEST, "q")
            assert res.status == ReplyStatus.FAILED
            assert server_store(server, client).hash == client.store.hash
        finally:
            await client.close()
            await server.close()

    run(main())


def test_server_rejects_non_hello_first_frame():
    async def main():
        server = await Server(WorkerAgent()).start()
        try:
            conn = await FramedConnection.connect("127.0.0.1", server.port)
            await conn.send(Frame(type=MessageType.MSG, seq=0, ctx_v=0, body={0: 1, 1: "x", 3: b"\0" * 8}))
            frame = await conn.recv()
            assert frame.type == MessageType.ERROR and frame.body[0] == ErrorCode.OUT_OF_ORDER
            await conn.close()
        finally:
            await server.close()

    run(main())


def test_server_answers_garbage_with_error():
    async def main():
        server = await Server(WorkerAgent()).start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            junk = b"\xff\xfe\xfd"
            writer.write(len(junk).to_bytes(4, "big") + junk)
            await writer.drain()
            data = await reader.read(4096)
            frame = cbor2.loads(data[4:])
            assert frame[1] == MessageType.ERROR and frame[4][0] == ErrorCode.BAD_FRAME
            writer.close()
        finally:
            await server.close()

    run(main())


def test_server_rejects_bad_initial_context():
    async def main():
        server = await Server(WorkerAgent()).start()
        try:
            conn = await FramedConnection.connect("127.0.0.1", server.port)
            bad_ctx = {"sys": "", "tools": {}, "hist": "not a list", "vars": {}}
            await conn.send(Frame(type=MessageType.HELLO, seq=0, ctx_v=0, body={0: "A", 1: [], 2: bad_ctx}))
            frame = await conn.recv()
            assert frame.type == MessageType.ERROR and frame.body[0] == ErrorCode.BAD_FRAME
            await conn.close()
        finally:
            await server.close()

    run(main())


# ---------------------------------------------------------------- mock llm


def test_mock_llm_is_deterministic():
    ctx, _ = sample_context(1)
    a, b = MockLLM(), MockLLM()
    p = render_prompt(ctx)
    assert a.complete(p, "q") == b.complete(p, "q")
    assert a.prompt_chars_total == len(p)


def test_render_prompt_prefix_is_stable():
    ctx, _ = sample_context(1)
    p1 = render_prompt(ctx)
    ctx["hist"].append({"r": "c", "i": 1, "c": "new"})
    p2 = render_prompt(ctx)
    head = p1.split("## History")[0]
    assert p2.startswith(head)  # instructions and tools do not move
