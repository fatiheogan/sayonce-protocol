import json

import cbor2
import pytest

from sayonce.codec import (
    Dictionary,
    Frame,
    FrameDecoder,
    ProtocolError,
    context_hash,
    encode_frame,
)
from sayonce.messages import (
    MAX_FRAME_SIZE,
    Bye,
    DeltaOp,
    Error,
    ErrorCode,
    Hello,
    HelloAck,
    Intent,
    MessageType,
    Msg,
    Reply,
    ReplyStatus,
    Resync,
    ResyncReason,
    Snapshot,
    parse_message,
)

H = b"\x01" * 8
DICT = Dictionary(["sys", "tools", "hist", "vars", "search", "budget", "description"])
CTX = {
    "sys": "You are a travel agent.",
    "tools": {"search": {"description": "Search flights", "params": {"from": "str", "to": "str"}}},
    "hist": [],
    "vars": {"budget": 500},
}


def roundtrip(msg, d=DICT, seq=3, ctx_v=7):
    wire = encode_frame(msg.to_frame(seq=seq, ctx_v=ctx_v, d=d))
    [frame] = FrameDecoder().feed(wire)
    assert (frame.seq, frame.ctx_v, frame.type) == (seq, ctx_v, msg.TYPE)
    return parse_message(frame, d)


# ----------------------------------------------------------------- messages


@pytest.mark.parametrize(
    "msg",
    [
        HelloAck(agent_id="B", session_id=b"\x00" * 8, ctx_h=H, resumed=True),
        Msg(intent=Intent.REQUEST, content="find flights IST-BER", ctx_h=H),
        Msg(
            intent=Intent.DELEGATE,
            content={"task": "book", "n": 2},
            ctx_h=H,
            delta=[
                [DeltaOp.SET, ["vars", "budget"], 450],
                [DeltaOp.DEL, ["vars", "old"]],
                [DeltaOp.APPEND, ["hist"], [{"note": "x"}]],
            ],
            task_id=42,
        ),
        Reply(status=ReplyStatus.OK, content=[1, 2, 3], ctx_h=H, in_reply_to=3),
        Resync(reason=ResyncReason.HASH_MISMATCH, my_ctx_v=4, my_ctx_h=H),
        Snapshot(ctx_v=9, ctx=CTX, ctx_h=H),
        Error(code=ErrorCode.BAD_FRAME, message="oops"),
        Bye(),
    ],
)
def test_message_roundtrip(msg):
    out = roundtrip(msg)
    if isinstance(msg, (Msg, Reply)) and msg.delta:
        # paths stay in wire form (resolved in context.py); values are expanded
        for sent, got in zip(msg.delta, out.delta):
            assert got[0] == sent[0]
            assert got[2:] == sent[2:]
        out.delta = msg.delta
    assert out == msg


def test_hello_roundtrip_uses_own_dictionary():
    hello = Hello(agent_id="A", dictionary=DICT.entries, ctx=CTX, caps={"zstd": False})
    # The receiver has no dictionary yet when HELLO arrives.
    out = roundtrip(hello, d=Dictionary())
    assert out == hello


def test_hello_resume():
    hello = Hello(agent_id="A", dictionary=[], ctx={}, resume=(b"s" * 8, 5, H))
    assert roundtrip(hello, d=Dictionary()).resume == (b"s" * 8, 5, H)


def test_missing_field_is_bad_frame():
    frame = Frame(type=MessageType.MSG, seq=0, ctx_v=0, body={0: 1, 3: H})
    with pytest.raises(ProtocolError) as exc:
        parse_message(frame, DICT)
    assert exc.value.code == ErrorCode.BAD_FRAME


def test_bad_hash_length():
    frame = Frame(type=MessageType.MSG, seq=0, ctx_v=0, body={0: 1, 1: "x", 3: b"short"})
    with pytest.raises(ProtocolError):
        parse_message(frame, DICT)


def test_unknown_intent():
    frame = Frame(type=MessageType.MSG, seq=0, ctx_v=0, body={0: 99, 1: "x", 3: H})
    with pytest.raises(ProtocolError):
        parse_message(frame, DICT)


# ------------------------------------------------------------------- framing


def test_decoder_handles_split_and_merged_frames():
    a = encode_frame(Msg(intent=Intent.INFORM, content="a", ctx_h=H).to_frame(0, 0, DICT))
    b = encode_frame(Msg(intent=Intent.INFORM, content="b" * 1000, ctx_h=H).to_frame(1, 1, DICT))
    stream = a + b
    dec = FrameDecoder()
    got = []
    for i in range(0, len(stream), 7):  # feed in 7-byte chunks
        got += dec.feed(stream[i : i + 7])
    assert [f.seq for f in got] == [0, 1]
    assert dec.buffered == 0


def test_decoder_rejects_oversized_frame():
    with pytest.raises(ProtocolError) as exc:
        FrameDecoder().feed((MAX_FRAME_SIZE + 1).to_bytes(4, "big"))
    assert exc.value.code == ErrorCode.FRAME_TOO_LARGE


def test_unsupported_version():
    payload = cbor2.dumps([2, 3, 0, 0, {}])
    with pytest.raises(ProtocolError) as exc:
        Frame.from_cbor(payload)
    assert exc.value.code == ErrorCode.UNSUPPORTED_VERSION


def test_unknown_type():
    with pytest.raises(ProtocolError) as exc:
        Frame.from_cbor(cbor2.dumps([1, 99, 0, 0, {}]))
    assert exc.value.code == ErrorCode.UNKNOWN_TYPE


@pytest.mark.parametrize("payload", [b"\xff\xff", cbor2.dumps({"a": 1}), cbor2.dumps([1, 3, 0])])
def test_malformed_frames(payload):
    with pytest.raises(ProtocolError) as exc:
        Frame.from_cbor(payload)
    assert exc.value.code == ErrorCode.BAD_FRAME


# ---------------------------------------------------------------- dictionary


def test_dictionary_compress_expand():
    wire = DICT.compress(CTX)
    assert 0 in wire and "sys" not in wire  # "sys" -> 0
    assert DICT.expand(wire) == CTX


def test_dictionary_does_not_touch_values():
    value = {"note": "search"}  # "search" is a value here, not a key
    assert DICT.compress(value) == {"note": "search"}


def test_dictionary_rejects_bad_reference():
    with pytest.raises(ProtocolError):
        DICT.expand({99: "x"})


def test_dictionary_rejects_non_string_keys():
    with pytest.raises(ValueError):
        DICT.compress({1: "x"})


def test_dictionary_entries_unique():
    with pytest.raises(ValueError):
        Dictionary(["a", "a"])


def test_compress_path():
    assert DICT.compress_path(["vars", "budget"]) == [3, 5]
    assert DICT.compress_path(["hist", 4, "unknown"]) == [2, 4, "unknown"]


# ------------------------------------------------------------------- hashing


def test_hash_independent_of_key_order():
    a = {"x": 1, "y": [1, 2], "z": {"p": 1, "q": 2}}
    b = {"z": {"q": 2, "p": 1}, "y": [1, 2], "x": 1}
    assert context_hash(a) == context_hash(b)
    assert len(context_hash(a)) == 8


def test_hash_changes_with_content():
    assert context_hash({"x": 1}) != context_hash({"x": 2})


# ----------------------------------------------------------- size sanity check


def test_cbor_smaller_than_json():
    """Not a benchmark, just a sanity check that the encoding is compact."""
    snap = Snapshot(ctx_v=0, ctx=CTX, ctx_h=H)
    cbor_size = len(encode_frame(snap.to_frame(0, 0, DICT)))
    json_size = len(json.dumps({"jsonrpc": "2.0", "method": "snapshot", "params": {"ctx": CTX}}))
    assert cbor_size < json_size


# --------------------------------------------------------------- compression


from sayonce.codec import DEFAULT_COMPRESS_THRESHOLD, TAG_ZSTD_FRAME  # noqa: E402


def test_large_frames_are_compressed_and_roundtrip():
    snap = Snapshot(ctx_v=0, ctx={**CTX, "sys": " ".join(f"word{i % 50}" for i in range(2000))}, ctx_h=H)
    frame = snap.to_frame(0, 0, DICT)
    plain = encode_frame(frame)
    packed = encode_frame(frame, DEFAULT_COMPRESS_THRESHOLD)
    assert len(packed) < len(plain) / 2
    assert cbor2.loads(packed[4:]).tag == TAG_ZSTD_FRAME
    [back] = FrameDecoder().feed(packed)
    assert parse_message(back, DICT) == snap


def test_small_frames_stay_uncompressed():
    frame = Msg(intent=Intent.REQUEST, content="hi", ctx_h=H).to_frame(0, 0, DICT)
    assert encode_frame(frame, DEFAULT_COMPRESS_THRESHOLD) == encode_frame(frame)


def test_compression_only_used_when_smaller():
    import os

    frame = Msg(intent=Intent.REQUEST, content=os.urandom(4000), ctx_h=H).to_frame(0, 0, DICT)
    assert encode_frame(frame, 100) == encode_frame(frame)  # random bytes do not compress


def test_decoder_rejects_bad_compressed_frames():
    import zstandard

    cases = [
        cbor2.CBORTag(TAG_ZSTD_FRAME, "not bytes"),
        cbor2.CBORTag(TAG_ZSTD_FRAME, b"not zstd at all"),
        cbor2.CBORTag(TAG_ZSTD_FRAME, zstandard.ZstdCompressor().compress(b"\xff\xff")),  # bad inner CBOR
        cbor2.CBORTag(TAG_ZSTD_FRAME, zstandard.ZstdCompressor().compress(
            cbor2.dumps(cbor2.CBORTag(TAG_ZSTD_FRAME, b"")))),  # nested
    ]
    for tag in cases:
        with pytest.raises(ProtocolError):
            Frame.from_cbor(cbor2.dumps(tag))


def test_decoder_rejects_decompression_bomb():
    import zstandard

    bomb = zstandard.ZstdCompressor().compress(b"\0" * (MAX_FRAME_SIZE + 1))  # tiny on the wire
    assert len(bomb) < 10_000
    with pytest.raises(ProtocolError) as exc:
        Frame.from_cbor(cbor2.dumps(cbor2.CBORTag(TAG_ZSTD_FRAME, bomb)))
    assert exc.value.code == ErrorCode.FRAME_TOO_LARGE

    unknown_size = zstandard.ZstdCompressor(write_content_size=False).compress(b"\0" * 100)
    with pytest.raises(ProtocolError):
        Frame.from_cbor(cbor2.dumps(cbor2.CBORTag(TAG_ZSTD_FRAME, unknown_size)))
