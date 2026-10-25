import pytest

from sayonce.codec import Dictionary, FrameDecoder, context_hash, encode_frame
from sayonce.context import (
    CLIENT,
    SERVER,
    ContextStore,
    DeltaError,
    ResyncRequired,
    apply_delta,
    empty_context,
)
from sayonce.messages import (
    DeltaOp,
    Intent,
    Msg,
    Reply,
    ReplyStatus,
    ResyncReason,
    parse_message,
)

SET, DEL, APPEND = DeltaOp.SET, DeltaOp.DEL, DeltaOp.APPEND
D = Dictionary(["sys", "tools", "hist", "vars", "budget", "search"])


def base_ctx():
    ctx = empty_context()
    ctx["sys"] = "You are a travel agent."
    ctx["tools"] = {"search": {"description": "Search flights"}}
    ctx["vars"] = {"budget": 500, "items": [1, 2, 3]}
    return ctx


def pair():
    return ContextStore(base_ctx(), D), ContextStore(base_ctx(), D)


def diverge(store, **vars_):
    """Make a store hold a different (but internally consistent) context."""
    v, ctx, _ = store.snapshot()
    ctx["vars"].update(vars_)
    store.load_snapshot(v, ctx, context_hash(ctx))


# ------------------------------------------------------------ apply_delta


def test_set_existing_and_new_keys():
    ctx = base_ctx()
    apply_delta(ctx, [[SET, ["vars", "budget"], 450], [SET, ["vars", "city"], "BER"]], D)
    assert ctx["vars"]["budget"] == 450 and ctx["vars"]["city"] == "BER"


def test_set_creates_intermediate_maps():
    ctx = base_ctx()
    apply_delta(ctx, [[SET, ["vars", "a", "b", "c"], 1]], D)
    assert ctx["vars"]["a"]["b"]["c"] == 1


def test_set_list_index():
    ctx = base_ctx()
    apply_delta(ctx, [[SET, ["vars", "items", 1], 99]], D)
    assert ctx["vars"]["items"] == [1, 99, 3]


def test_delete():
    ctx = base_ctx()
    apply_delta(ctx, [[DEL, ["tools", "search"]], [DEL, ["vars", "items", 0]]], D)
    assert ctx["tools"] == {} and ctx["vars"]["items"] == [2, 3]


def test_append():
    ctx = base_ctx()
    apply_delta(ctx, [[APPEND, ["vars", "items"], [4, 5]]], D)
    assert ctx["vars"]["items"] == [1, 2, 3, 4, 5]


def test_dictionary_reference_vs_list_index():
    ctx = base_ctx()
    # 3 -> "vars", 4 -> "budget" (map positions); 0 stays a list index
    apply_delta(ctx, [[SET, [3, 4], 1], [SET, [3, "items", 0], 7]], D)
    assert ctx["vars"]["budget"] == 1 and ctx["vars"]["items"][0] == 7


@pytest.mark.parametrize(
    "op",
    [
        [SET, [], 1],  # empty path
        [SET, ["nope"], 1],  # unknown segment
        [DEL, ["vars"]],  # cannot delete a segment
        [SET, ["hist"], "not a list"],  # wrong segment type
        [DEL, ["vars", "missing"]],
        [DEL, ["vars", "missing", "deep"]],
        [SET, ["vars", "items", 10], 1],  # index out of range
        [SET, ["vars", "items", "x"], 1],  # string index into list
        [APPEND, ["vars", "budget"], [1]],  # not a list
        [APPEND, ["vars", "missing"], [1]],
        [SET, ["vars", 99], 1],  # bad dictionary reference
        [SET, ["sys", "x"], 1],  # cannot index into a string
        [9, ["vars"], 1],  # unknown op
    ],
)
def test_invalid_operations(op):
    with pytest.raises(DeltaError):
        apply_delta(base_ctx(), [op], D)


# ------------------------------------------------------------ store sync


def test_fifty_rounds_stay_in_sync():
    client, server = pair()
    for i in range(50):
        step = client.advance(CLIENT, Intent.REQUEST, f"question {i}", [[SET, ["vars", "round"], i]])
        server.receive(CLIENT, Intent.REQUEST, f"question {i}", [[SET, ["vars", "round"], i]], step.version, step.new_hash)

        step = server.advance(SERVER, ReplyStatus.OK, f"answer {i}", [[APPEND, ["vars", "items"], [i]]])
        client.receive(SERVER, ReplyStatus.OK, f"answer {i}", [[APPEND, ["vars", "items"], [i]]], step.version, step.new_hash)

    assert client.version == server.version == 100
    assert client.hash == server.hash
    assert client.ctx == server.ctx
    assert len(client.ctx["hist"]) == 100
    assert client.ctx["hist"][0] == {"r": "c", "i": 1, "c": "question 0"}
    assert client.ctx["hist"][1] == {"r": "s", "s": 0, "c": "answer 0"}


def test_sync_over_the_wire_with_dictionary():
    """Full path: advance -> Msg -> bytes -> decode -> receive."""
    client, server = pair()
    delta = [[SET, ["vars", "budget"], 450]]
    step = client.advance(CLIENT, Intent.REQUEST, "cheapest?", delta)
    msg = Msg(intent=Intent.REQUEST, content="cheapest?", ctx_h=step.new_hash, delta=delta)
    wire = encode_frame(msg.to_frame(seq=0, ctx_v=step.version, d=D))

    [frame] = FrameDecoder().feed(wire)
    got = parse_message(frame, D)
    assert got.delta[0][1] == [3, 4]  # path travels as dictionary references
    server.receive(CLIENT, got.intent, got.content, got.delta, frame.ctx_v, got.ctx_h)
    assert server.hash == client.hash and server.ctx["vars"]["budget"] == 450

    step = server.advance(SERVER, ReplyStatus.OK, "flight X", [])
    rep = Reply(status=ReplyStatus.OK, content="flight X", ctx_h=step.new_hash, in_reply_to=0)
    [frame] = FrameDecoder().feed(encode_frame(rep.to_frame(seq=0, ctx_v=step.version, d=D)))
    got = parse_message(frame, D)
    client.receive(SERVER, got.status, got.content, got.delta, frame.ctx_v, got.ctx_h)
    assert client.version == server.version == 2 and client.hash == server.hash


# ------------------------------------------------------------ resync cases


def test_version_mismatch():
    client, server = pair()
    client.advance(CLIENT, Intent.INFORM, "lost message")  # server never sees this one
    step = client.advance(CLIENT, Intent.INFORM, "second")
    with pytest.raises(ResyncRequired) as exc:
        server.receive(CLIENT, Intent.INFORM, "second", [], step.version, step.new_hash)
    assert exc.value.reason == ResyncReason.VERSION_MISMATCH
    assert server.version == 0  # unchanged


def test_hash_mismatch_when_contexts_diverged():
    client, server = pair()
    diverge(server, budget=1)  # one side has a different context
    step = client.advance(CLIENT, Intent.INFORM, "hi")
    before = server.ctx["vars"]["budget"]
    with pytest.raises(ResyncRequired) as exc:
        server.receive(CLIENT, Intent.INFORM, "hi", [], step.version, step.new_hash)
    assert exc.value.reason == ResyncReason.HASH_MISMATCH
    assert server.version == 0 and server.ctx["vars"]["budget"] == before
    assert len(server.ctx["hist"]) == 0  # nothing half-applied


def test_apply_failed_leaves_store_unchanged():
    client, server = pair()
    bad = [[SET, ["vars", "x"], 1], [DEL, ["vars", "missing"]]]
    with pytest.raises(ResyncRequired) as exc:
        server.receive(CLIENT, Intent.INFORM, "hi", bad, 0, b"\x00" * 8)
    assert exc.value.reason == ResyncReason.APPLY_FAILED
    assert "x" not in server.ctx["vars"] and server.version == 0


def test_invalid_own_delta_leaves_store_unchanged():
    client, _ = pair()
    with pytest.raises(DeltaError):
        client.advance(CLIENT, Intent.INFORM, "hi", [[DEL, ["vars", "missing"]]])
    assert client.version == 0 and client.ctx["hist"] == []


def test_snapshot_recovers_and_sync_continues():
    client, server = pair()
    diverge(server, budget=1)

    v, ctx, h = client.snapshot()
    server.load_snapshot(v, ctx, h)
    assert server.ctx == client.ctx and server.hash == client.hash

    step = client.advance(CLIENT, Intent.REQUEST, "go on")
    server.receive(CLIENT, Intent.REQUEST, "go on", [], step.version, step.new_hash)
    assert server.hash == client.hash


def test_snapshot_with_wrong_hash_is_rejected():
    client, server = pair()
    v, ctx, _ = client.snapshot()
    with pytest.raises(ResyncRequired):
        server.load_snapshot(v, ctx, b"\x00" * 8)


def test_snapshot_is_a_copy():
    client, _ = pair()
    _, ctx, _ = client.snapshot()
    ctx["vars"]["budget"] = -1
    assert client.ctx["vars"]["budget"] == 500


def test_content_is_copied_into_history():
    client, _ = pair()
    content = {"q": [1, 2]}
    client.advance(CLIENT, Intent.REQUEST, content)
    content["q"].append(3)
    assert client.ctx["hist"][0]["c"] == {"q": [1, 2]}


# ------------------------------------------------------------ incremental hashing


def test_incremental_hash_equals_full_hash():
    client, server = pair()
    deltas = [
        [],
        [[SET, ["vars", "budget"], 1]],
        [[APPEND, ["vars", "items"], [9]]],
        [[SET, ["tools", "new"], {"description": "x"}]],
        [[SET, ["sys"], "new instructions"]],
        [[SET, ["hist", 0, "c"], "edited"]],  # rewrites history: chain recomputed
        [[DEL, ["tools", "search"]]],
    ]
    for i, delta in enumerate(deltas):
        step = client.advance(CLIENT, Intent.REQUEST, f"q{i}", delta)
        server.receive(CLIENT, Intent.REQUEST, f"q{i}", delta, step.version, step.new_hash)
        assert client.hash == server.hash == context_hash(client.ctx)
        assert client.verify() and server.verify()


def test_committed_versions_are_not_mutated():
    client, _ = pair()
    old = client.ctx
    old_vars = dict(old["vars"])
    client.advance(CLIENT, Intent.REQUEST, "q", [[SET, ["vars", "budget"], 1], [APPEND, ["vars", "items"], [4]]])
    assert old["vars"] == old_vars and len(old["hist"]) == 0
    assert client.ctx["tools"] is old["tools"]  # untouched segment is shared, not copied


def test_checkpoint_and_restore():
    client, _ = pair()
    cp = client.checkpoint()
    client.advance(CLIENT, Intent.REQUEST, "to be undone", [[SET, ["vars", "budget"], 1]])
    client.restore(cp)
    assert client.version == 0 and client.ctx["hist"] == [] and client.ctx["vars"]["budget"] == 500
    assert client.verify()


def test_verify_detects_silent_local_corruption():
    client, _ = pair()
    client._ctx["tools"]["search"]["description"] = "tampered"  # bypasses the store
    assert not client.verify()
