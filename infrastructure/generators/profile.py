import json
import time
import random
import uuid

from infrastructure.generators.util import (
    schema_generator,
    sentence_generator,
)
from infrastructure.util import full_path_from_module_relative_path, memoize

filenames = [
    "main.py",
    "config.py",
    "db.py",
    "app.py",
    "api.py",
    "worker.py",
    "serializer.py",
    "access.py",
    "auth.py",
    "foo.py",
    "bar.py",
]

functions = [
    "main",
    "config",
    "db",
    "app",
    "api",
    "worker",
    "serializer",
    "check_access",
    "perform_auth",
    "expire_auth",
    "delete_user",
    "read_thing",
    "record_event",
    "send_request",
    "process_response",
]


def create_profile_data(
    min_sample_count: int,
    max_sample_count: int,
    min_frame_count: int,
    max_frame_count: int,
):
    thread_id = random.randint(10000, 1000000)
    event_time = time.time()

    sample_count = random.randint(min_sample_count, max_sample_count)
    frame_count = random.randint(min_frame_count, max_frame_count)

    samples = []
    stacks = []
    frames = []

    for i in range(frame_count):
        lineno = random.randint(1, 100)
        function = random.choice(functions)
        filename = random.choice(filenames)
        frames.append(
            {
                "filename": filename,
                "function": function,
                "lineno": lineno,
            }
        )

    time_start = event_time - (0.01 * sample_count)
    for i in range(sample_count):
        # stack_frame_count = random.randint(0, frame_count)
        stack_values = list(range(max(frame_count - i, 1)))
        stacks.append(stack_values)

        samples.append(
            {
                "timestamp": time_start + (0.01 * i),
                "thread_id": str(thread_id),
                "stack_id": i,
            }
        )

    profile_data = {
        "samples": samples,
        "stacks": stacks,
        "frames": frames,
    }
    return profile_data


def profile_chunk_item_generator(
    min_sample_count: int,
    max_sample_count: int,
    min_frame_count: int,
    max_frame_count: int,
    release: str,
    environment: str,
    **kwargs
):
    def inner():
        profile = {
            "version": "2",
            "chunk_id": uuid.uuid4().hex,
            "profiler_id": uuid.uuid4().hex,
            "timestamp": time.time(),
            "release": release,
            "environment": environment,
            "profile": create_profile_data(
                min_sample_count=min_sample_count,
                max_sample_count=max_sample_count,
                min_frame_count=min_frame_count,
                max_frame_count=max_frame_count,
            ),
            "platform": "python",
            "client_sdk": {"name": "sentry.python", "version": "2.52.0"},
        }
        return profile

    return inner
