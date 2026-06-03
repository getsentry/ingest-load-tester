import json
import uuid
import zlib

import pytest

from infrastructure.generators.replay import replay_envelope_generator


def _make_generator(compress_recordings=True):
    return replay_envelope_generator(
        min_segments=1,
        max_segments=3,
        replay_type="session",
        release="r-1.0",
        environment="prod",
        compress_recordings=compress_recordings,
    )


def _split(items):
    event = next(i for i in items if i["type"] == "replay_event")
    recording = next(i for i in items if i["type"] == "replay_recording")
    return event, recording


def _decode_like_relay(recording_data: bytes):
    """Mirror Relay's transcode_replay: split on first newline, then decode the
    body as a raw JSON array (starts with '[') or via zlib."""
    nl = recording_data.index(b"\n")
    header = json.loads(recording_data[:nl])
    body = recording_data[nl + 1 :]
    if body[:1] == b"[":
        decoded = body
    else:
        decoded = zlib.decompress(body)  # raises on gzip / non-zlib bodies
    return header, json.loads(decoded)


def test_compressed_recording_is_zlib_not_gzip():
    items = _make_generator(compress_recordings=True)()
    _, recording = _split(items)
    body = recording["data"][recording["data"].index(b"\n") + 1 :]
    assert body[:2] == b"\x78\x9c", "recording body must be a zlib stream, not gzip"


def test_recording_body_decodes_like_relay():
    for _ in range(10):
        items = _make_generator(compress_recordings=True)()
        event, recording = _split(items)
        header, events = _decode_like_relay(recording["data"])
        assert header["segment_id"] == event["segment_id"]
        assert isinstance(events, list) and events


def test_uncompressed_recording_is_raw_json_array():
    items = _make_generator(compress_recordings=False)()
    _, recording = _split(items)
    header, events = _decode_like_relay(recording["data"])
    assert isinstance(events, list) and events


def test_replay_event_passes_relay_validation():
    """Relay's replay::validate requires a replay_id, a segment_id <= u16::MAX,
    and valid UUID trace_ids/error_ids."""
    items = _make_generator()()
    event, _ = _split(items)
    uuid.UUID(event["replay_id"])
    assert 0 <= event["segment_id"] <= 0xFFFF
    for trace_id in event.get("trace_ids", []):
        uuid.UUID(trace_id)
    for error_id in event.get("error_ids", []):
        uuid.UUID(error_id)


def test_each_call_is_a_distinct_replay():
    gen = _make_generator()
    replay_ids = set()
    for _ in range(20):
        event, _ = _split(gen())
        replay_ids.add(event["replay_id"])
    assert len(replay_ids) == 20


def test_envelope_has_exactly_one_event_and_one_recording():
    """Relay rejects envelopes with more than one recording (InvalidItemCount)."""
    items = _make_generator()()
    types = [i["type"] for i in items]
    assert types.count("replay_event") == 1
    assert types.count("replay_recording") == 1
