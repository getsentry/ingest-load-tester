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


def create_profile_data():
    thread_id = random.randint(10000, 1000000)
    event_time = time.time()

    sample_count = random.randint(5, 15)
    frame_count = random.randint(5, 30)

    samples = []
    stacks = []
    frames = []

    for i in range(frame_count):
        lineno = random.randint(1, 100)
        function = random.choice(functions)
        filename = random.choice(filenames)
        frames.append({
            "filename": filename,
            "function": function,
            "lineno": lineno,
        })

    time_start = event_time - (0.01 * sample_count)
    for i in range(sample_count):
        # stack_frame_count = random.randint(0, frame_count)
        stack_values = list(range(max(frame_count - i, 1)))
        stacks.append(stack_values)

        samples.append({
            "timestamp": time_start + (0.01 * i),
            "thread_id": str(thread_id),
            "stack_id": i,
        })

    profile_data = {
        "samples": samples,
        "stacks": stacks,
        "frames": frames,
    }
    return profile_data

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
    if random.random() < 0.5:
        return profile_data

    profile_data = {
        "samples": [
          {
            "stack_id": 0,
            "thread_id": "0x0000000102adc700",
            "timestamp": event_time - (0.01 * 3),
          },
          {
            "stack_id": 1,
            "thread_id": "0x0000000102adc700",
            "timestamp": event_time - (0.01 * 2),
          },
          {
            "stack_id": 0,
            "thread_id": "0x0000000102adc700",
            "timestamp": event_time - (0.01),
          },
          {
            "stack_id": 1,
            "thread_id": "0x0000000102adc700",
            "timestamp": event_time,
          }
        ],
        "stacks": [
          [0, 1],
          [1, 2, 3]
        ],
        "frames": [
          {
            "instruction_addr": "0xa722447ffffffffc"
          },
          {
            "instruction_addr": "0x442e4b81f5031e58"
          },
          {
            "instruction_addr": "0x442e4b81f5031e57"
          },
          {
            "instruction_addr": "0x442e4b81f5031e16"
          }
        ],
        "thread_metadata": {
          "0x0000000102adc700": {
            "name": "com.apple.main-thread"
          },
          "0x000000016d8fb180": {
            "name": "com.apple.network.connections"
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
            "version": "2",
            "chunk_id": uuid.uuid4().hex,
            "profiler_id": uuid.uuid4().hex,
            "timestamp": time.time(),
            "release": "1.0.1",
            "environment": "dev",
            "profile": create_profile_data(),
            # "platform": "python",
            # "client_sdk": {"name": "sentry.python.django", "version": "2.47.0"},
            "platform": "cocoa",
            "client_sdk": {"name": "sentry-cocoa", "version": "7.6.1"},
            "debug_meta": {
                "images": [
                  {
                    "debug_id": "32420279-25E2-34E6-8BC7-8A006A8F2425",
                    "image_addr": "0x000000010258c000",
                    "code_file": "/private/var/containers/Bundle/Application/C3511752-DD67-4FE8-9DA2-ACE18ADFAA61/TrendingMovies.app/TrendingMovies",
                    "type": "macho",
                    "image_size": 1720320,
                    "image_vmaddr": "0x0000000100000000"
                  },
                ],
            }
        }
        return profile

    return inner
