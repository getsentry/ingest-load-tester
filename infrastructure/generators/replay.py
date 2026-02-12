import gzip
import json
import random
import time
import uuid


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
    replay_id = uuid.uuid4().hex
    replay_start_timestamp = time.time()

    def inner():
        num_segments = random.randint(min_segments, max_segments)
        items = []

        for segment_id in range(num_segments):
            # Create the replay_event item
            replay_event = create_replay_event_item(
                replay_id=replay_id,
                replay_type=replay_type,
                segment_id=segment_id,
                replay_start_timestamp=replay_start_timestamp if segment_id == 0 else None,
                release=release,
                environment=environment,
            )
            items.append(replay_event)

            # Create the corresponding replay_recording item
            replay_recording = create_replay_recording_item(
                segment_id=segment_id,
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
    if random.random() > 0.5:
        replay_event["trace_ids"] = [uuid.uuid4().hex for _ in range(random.randint(1, 3))]

    # Add SDK information
    replay_event["sdk"] = {
        "name": "sentry.javascript.browser",
        "version": "7.80.0",
    }

    # Add user information
    if random.random() > 0.3:
        replay_event["user"] = {
            "id": str(random.randint(1, 10000)),
            "email": f"user{random.randint(1, 1000)}@example.com",
            "ip_address": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
        }

    # Add request information
    replay_event["request"] = {
        "url": random.choice([
            "https://example.com/",
            "https://example.com/dashboard",
            "https://example.com/profile",
            "https://example.com/settings",
        ]),
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
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


def create_replay_recording_item(segment_id: int, compress: bool = True):
    """
    Create a replay_recording item with synthetic recording data.

    The replay_recording format is:
    1. A JSON object with metadata (segment_id)
    2. A newline
    3. A JSON array of recording events (optionally gzip-compressed)
    """
    # Metadata line
    metadata = {"segment_id": segment_id}

    # Generate synthetic recording events
    recording_events = generate_recording_events(segment_id)

    # Combine metadata and recording data
    recording_data = json.dumps(metadata) + "\n" + json.dumps(recording_events)

    # Optionally compress the recording data
    if compress:
        recording_bytes = gzip.compress(recording_data.encode("utf-8"))
    else:
        recording_bytes = recording_data.encode("utf-8")

    return {
        "type": "replay_recording",
        "data": recording_bytes,
    }


def generate_recording_events(segment_id: int):
    """
    Generate synthetic RRWeb recording events.

    These are simplified versions of actual RRWeb events.
    """
    base_timestamp = int(time.time() * 1000)  # milliseconds
    events = []

    # Start with a meta event (type 4)
    events.append({
        "type": 4,  # Meta
        "timestamp": base_timestamp,
        "data": {
            "href": "https://example.com/",
            "width": 1920,
            "height": 1080,
        }
    })

    # Add a full snapshot event (type 2) for the first segment
    if segment_id == 0:
        events.append({
            "type": 2,  # FullSnapshot
            "timestamp": base_timestamp + 100,
            "data": {
                "node": {
                    "type": 0,
                    "childNodes": [
                        {
                            "type": 1,
                            "name": "html",
                            "attributes": {},
                            "childNodes": []
                        }
                    ]
                },
                "initialOffset": {
                    "left": 0,
                    "top": 0
                }
            }
        })

    # Add some incremental snapshots (type 3) - mouse movements, clicks, etc.
    num_events = random.randint(5, 20)
    for i in range(num_events):
        event_timestamp = base_timestamp + (i + 1) * 100

        # Random event type
        event_type = random.choice([
            "MouseMove",
            "MouseInteraction",
            "Scroll",
            "ViewportResize",
            "Input",
        ])

        if event_type == "MouseMove":
            events.append({
                "type": 3,  # IncrementalSnapshot
                "timestamp": event_timestamp,
                "data": {
                    "source": 1,  # MouseMove
                    "positions": [
                        {
                            "x": random.randint(0, 1920),
                            "y": random.randint(0, 1080),
                            "timeOffset": random.randint(0, 100)
                        }
                    ]
                }
            })
        elif event_type == "MouseInteraction":
            events.append({
                "type": 3,
                "timestamp": event_timestamp,
                "data": {
                    "source": 2,  # MouseInteraction
                    "type": random.choice([0, 1, 2]),  # MouseUp, MouseDown, Click
                    "x": random.randint(0, 1920),
                    "y": random.randint(0, 1080),
                }
            })
        elif event_type == "Scroll":
            events.append({
                "type": 3,
                "timestamp": event_timestamp,
                "data": {
                    "source": 3,  # Scroll
                    "x": random.randint(0, 100),
                    "y": random.randint(0, 1000),
                }
            })

    return events
