import pathlib
import json
import random
import time
import uuid
import zlib


FIXTURE_PATH = pathlib.Path(__file__).parent.parent.parent / "test-events"


def replay_envelope_generator(
    min_segments: int,
    max_segments: int,
    replay_type: str,
    release: str | None,
    environment: str | None,
    compress_recordings: bool = True,
):
    """
    Generate replay_event and replay_recording items for an envelope.

    Args:
        min_segments: Minimum number of replay_recording segments per replay_event
        max_segments: Maximum number of replay_recording segments per replay_event
        replay_type: Either "session" or "buffer"
        release: Release version string
        environment: Environment name
        compress_recordings: Whether to gzip-compress the recording data

    Returns:
        A generator function that creates replay items
    """

    def inner():
        # A fresh replay_id per call so every envelope is a distinct replay
        # rather than a flood of duplicate segments that the pipeline would dedupe
        replay_id = uuid.uuid4().hex
        replay_start_timestamp = time.time()

        num_segments = random.randint(min_segments, max_segments)
        items = []
        # Create the replay_event item
        replay_event = create_replay_event_item(
            replay_id=replay_id,
            replay_type=replay_type,
            segment_id=0,
            replay_start_timestamp=replay_start_timestamp,
            release=release,
            environment=environment,
        )
        items.append(replay_event)

        replay_recording = create_replay_recording_item(
            segment_id=0,
            num_segments=num_segments,
            compress=compress_recordings,
        )
        items.append(replay_recording)

        return items

    return inner


def create_replay_event_item(
    replay_id: str,
    replay_type: str,
    segment_id: int,
    replay_start_timestamp: float | None,
    release: str | None,
    environment: str | None,
):
    """
    Create a single replay_event item following the Sentry schema.
    """
    current_timestamp = time.time()

    # Build the base replay_event
    replay_event = {
        "type": "replay_event",
        "replay_id": replay_id,
        "event_id": replay_id,
        "segment_id": segment_id,
        "timestamp": current_timestamp,
        "replay_type": replay_type,
        "platform": "javascript",
    }

    # Add replay_start_timestamp only on the first segment
    if replay_start_timestamp is not None:
        replay_event["replay_start_timestamp"] = replay_start_timestamp

    # Add optional fields
    if release:
        replay_event["release"] = release

    if environment:
        replay_event["environment"] = environment

    # Add URLs visited during this segment
    replay_event["urls"] = generate_urls(segment_id)

    # Add trace IDs if any transactions occurred
    # if random.random() > 0.5:
    replay_event["trace_ids"] = [uuid.uuid4().hex for _ in range(random.randint(1, 3))]

    # Add SDK information
    replay_event["sdk"] = {
        "name": "sentry.javascript.browser",
        "version": "7.80.0",
    }

    # Add user information
    # if random.random() > 0.3:
    replay_event["user"] = {
        "id": str(random.randint(1, 10000)),
        "email": f"user{random.randint(1, 1000)}@example.com",
        "ip_address": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
    }

    # Add request information
    replay_event["request"] = {
        "url": random.choice(
            [
                "https://example.com/",
                "https://example.com/dashboard",
                "https://example.com/profile",
                "https://example.com/settings",
            ]
        ),
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
    }

    return replay_event


def generate_urls(segment_id: int):
    """Generate realistic URLs for a replay segment."""
    base_urls = [
        "https://example.com/",
        "https://example.com/dashboard",
        "https://example.com/profile",
        "https://example.com/settings",
        "https://example.com/help",
        "https://example.com/products",
        "https://example.com/checkout",
    ]

    # First segment usually has one URL, later segments might have more
    num_urls = 1 if segment_id == 0 else random.randint(1, 3)
    return random.sample(base_urls, min(num_urls, len(base_urls)))


def create_replay_recording_item(
    segment_id: int, num_segments: int, compress: bool = True
):
    """
    Create a replay_recording item with synthetic recording data.

    The replay_recording format is:
    1. A JSON object with metadata (segment_id)
    2. A newline
    3. A JSON array of recording events (optionally zlib/deflate-compressed)

    NOTE: Relay decompresses recording bodies with a zlib decoder (see
    relay-replays `RecordingScrubber::transcode_replay`)
    """
    # Metadata line
    metadata = {"segment_id": segment_id}

    # Generate synthetic recording events
    recording_event_bytes = generate_recording_events_from_file(num_segments)

    # Optionally compress the recording data
    if compress:
        recording_bytes = zlib.compress(recording_event_bytes)
    else:
        recording_bytes = recording_event_bytes

    # Combine metadata and recording data
    recording_data = (json.dumps(metadata) + "\n").encode("utf8") + recording_bytes

    return {
        "type": "replay_recording",
        "data": recording_data,
    }


def generate_recording_events_from_file(num_segments: int) -> bytes:
    """
    generate a replay recording segment from a fixture file.
    """
    if num_segments < 2:
        path = FIXTURE_PATH / "replay-recording-xsmall.json"
    elif num_segments < 5:
        path = FIXTURE_PATH / "replay-recording-small.json"
    else:
        path = FIXTURE_PATH / "replay-recording-medium.json"

    with open(path, "rb") as f:
        events = json.load(f)

    # Mutate each event and align the timestamp with the present.
    # Use the offsets in the fixture data so the order of operations
    # is preserved
    current_time = time.time()
    start_time: float | None = None
    for item in events:
        if start_time is None:
            start_time = item["timestamp"]
        event_time_delta = item["timestamp"] - start_time
        item["timestamp"] = current_time + event_time_delta
    return json.dumps(events).encode("utf8")
