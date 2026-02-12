import json
import time
import random
import uuid

from infrastructure.generators.util import (
    schema_generator,
    sentence_generator,
)
from infrastructure.util import full_path_from_module_relative_path, memoize


def create_profile_data():
    thread_id = random.randint(10000, 1000000)
    event_time = time.time()
    profile_data = {
        "samples": [
            {
                "timestamp": event_time - 0.02,
                "thread_id": str(thread_id),
                "stack_id": 0,
            },
            {
                "timestamp": event_time - 0.01,
                "thread_id": str(thread_id),
                "stack_id": 1,
            },
            {
                "timestamp": event_time,
                "thread_id": str(thread_id),
                "stack_id": 2,
            }
        ],
        "stacks": [
            [0, 1, 2, 3],
            [0, 1],
            [0, 1, 2],
        ],
        "frames": [
            {
                "filename": "main.py",
                "function": "main",
                "lineno": 101,
            },
            {
                "filename": "db.py",
                "function": "query",
                "lineno": 125,
            },
            {
                "filename": "config.py",
                "function": "get_config",
                "lineno": 204,
            },
            {
                "filename": "endpoint.py",
                "function": "do_get",
                "lineno": 205,
            },
        ],
        "thread_metadata": {
            thread_id: {
                "name": "MainThread",
            }
        }
    }
    return profile_data


def profile_chunk_item_generator(**kwargs):
    """
    v2 profiling chunks. Can't get these to ingest currently
    """
    def inner():
        """
        profile.samples -> list of sample
            sample is when a stack was capture
                timestamp - time of sample
                thread_id - id of thread
                stack_id - index of stack list.
        profile.stacks -> list of stack indexes
            lists of frames in a sample. Each sample has a stack list
        profile.frames -> list of frames
            frames are files captured in a sample.
            - abs_path
              module
              filename
              function
              lineno
              in_app
        profile.thread_metadata:
            names of threads.
            - id -> {name: str}
        """
        profile = {
            "profiler_id": uuid.uuid4().hex,
            "chunk_id": uuid.uuid4().hex,
            "version": 2,
            "release": "todo",
            "environment": "dev",
            "profile": create_profile_data(),
            "platform": "python",
        }
        return profile

    return inner
