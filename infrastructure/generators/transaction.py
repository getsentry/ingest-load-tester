import random
import time

from infrastructure.generators.contexts import (
    os_context_generator,
    device_context_generator,
    trace_context_generator,
)
from infrastructure.generators.util import (
    schema_generator,
    op_generator,
    span_id_generator,
    uuid_generator,
)


def base_transaction_generator(release=None, min_spans=1, max_spans=15, max_duration_secs=30, **kwargs):
    return schema_generator(
        event_id=uuid_generator(),
        type="transaction",
        version="7",
        release=release,
        timestamp=time.time,
        start_timestamp=lambda: time.time() - 0.001 - random.randrange(0, max_duration_secs),
        contexts={
            "os": [None, os_context_generator()],
            "device": [None, device_context_generator()],
            "trace": [None, trace_context_generator()],
        },
        culprit=op_generator(),
        environment=["prod", "debug"],
        spans=spans_generator(min=min_spans, max=max_spans),
    )


def spans_generator(min=1, max=11):
    def inner():
        spans = []
        gen = span_generator()
        num_spans = random.randrange(min, max)
        for i in range(num_spans):
            spans.append(gen())
        return spans

    return inner


def span_generator():
    return schema_generator(
        timestamp=time.time,
        start_timestamp=time.time,
        description=op_generator(),
        op=op_generator(),
        span_id=span_id_generator(),
        parent_span_id=span_id_generator(),
        same_process_as_parent=[True, False],
    )
