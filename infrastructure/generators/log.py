import time
import random
import uuid

from infrastructure.generators.util import (
    schema_generator,
    sentence_generator,
)


def log_envelope_item_generator(min_items: int, max_items: int, release: str | None):
    trace_id = uuid.uuid4().hex

    def inner():
        num_spans = random.randint(min_items, max_items)
        items = []
        for _ in range(num_spans):
            item = create_log_item(trace_id=trace_id, release=release)
            items.append(item)
        return {"items": items}

    return inner


def create_log_item(trace_id=None, release=None):
    generator = schema_generator(
        trace_id=trace_id,
        span_id=lambda: uuid.uuid4().hex,
        level=["info", "warn", "error"],
        timestamp=time.time,
        body=sentence_generator(),
        attributes=attribute_generator(release=release),
    )
    return generator()


def attribute_generator(release):
    def inner():
        attrs = {}
        if release:
            attrs["sentry.release"] = {
                "value": release,
                "type": "string",
            }

        return attrs

    return inner
