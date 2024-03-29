import time
import uuid
import random

from infrastructure.generators.javascript_frames import javascript_exception_generator
from infrastructure.generators.util import (
    schema_generator,
    sentence_generator,
)
from infrastructure.generators.user import user_generator
from infrastructure.generators.contexts import (
    os_context_generator,
    device_context_generator,
    app_context_generator,
)
from infrastructure.generators.breadcrumbs import breadcrumb_generator
from infrastructure.generators.native import native_data_generator


def base_event_generator(
    with_event_id=True,
    with_level=True,
    num_event_groups=1,
    max_users=None,
    min_breadcrumbs=None,
    max_breadcrumbs=None,
    breadcrumb_categories=None,
    breadcrumb_levels=None,
    breadcrumb_types=None,
    breadcrumb_messages=None,
    with_native_stacktrace=False,
    with_javascript_stacktrace=False,
    num_stacktraces=5,
    num_frames=100,
    num_releases=10,
    release=None,
    min_frames=5,
    max_frames=30,
    **kwargs,
):
    event_generator = schema_generator(
        event_id=(lambda: uuid.uuid4().hex) if with_event_id else None,
        level=["error", "debug"] if with_level else None,
        fingerprint=lambda: [f"fingerprint{random.randrange(num_event_groups)}"],
        release=(
            lambda: f"release{random.randrange(num_releases)}"
            if release is None
            else release
        ),
        transaction=[None, lambda: f"mytransaction{random.randrange(100)}"],
        logentry={"formatted": sentence_generator()},
        logger=["foo.bar.baz", "bam.baz.bad", None],
        timestamp=time.time,
        environment=["production", "development", "staging"],
        user=user_generator(max_users=max_users),
        contexts={
            "os": [None, os_context_generator()],
            "device": [None, device_context_generator()],
            "app": [None, app_context_generator()],
        },
        breadcrumbs=breadcrumb_generator(
            min=min_breadcrumbs,
            max=max_breadcrumbs,
            categories=breadcrumb_categories,
            levels=breadcrumb_levels,
            types=breadcrumb_types,
            messages=breadcrumb_messages,
        ),
    )

    if with_native_stacktrace:
        native_gen = native_data_generator(
            num_frames=random.randrange(min_frames, max_frames)
        )

        exc_gen = schema_generator(value=sentence_generator())

        def event_generator(base_gen=event_generator):
            event = base_gen()
            event["platform"] = "cocoa"

            frames, images = native_gen()
            exc = exc_gen()
            exc["stacktrace"] = {"frames": exc_frames}

            event["exception"] = {"values": [exc]}
            event["debug_meta"] = {"images": images}
            return event

    elif with_javascript_stacktrace:
        js_gen = javascript_exception_generator(
            min_frames=min_frames, max_frames=max_frames
        )

        def event_generator(base_gen=event_generator):
            event = base_gen()
            event["platform"] = "javascript"
            event["exception"] = js_gen()
            return event

    return event_generator
