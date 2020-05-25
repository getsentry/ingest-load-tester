import random

from infrastructure import memoize, full_path_from_module_relative_path
import json


@memoize
def javascript_frames():
    _config_path = full_path_from_module_relative_path(
        __file__, "../../js-stack-traces/all_frames.json"
    )
    with open(_config_path, "r") as f:
        frames = json.load(f)
    return frames


def javascript_frames_generator(**event_kwargs):
    max_frames = event_kwargs.get("max_frames", 50)
    min_frames = event_kwargs.get("min_frames", 0)
    frames = javascript_frames()

    def inner():
        num_frames = random.randrange(min_frames, max_frames)
        result = [random.choice(frames) for x in range(num_frames)]
        return result

    return inner


def javascript_exception_generator(**event_kwargs):
    frames_generator = javascript_frames_generator(**event_kwargs)

    def inner():
        return {
            "values": [{"type": "Error", "stacktrace": {"frames": frames_generator()}}]
        }

    return inner
