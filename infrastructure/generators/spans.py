import time
import random
import uuid
from typing import Sequence


_SPAN_NAMES_BY_OP = {
    "http": [
        "GET /api/users",
        "POST /api/events",
        "GET /api/projects",
        "PUT /api/settings",
        "DELETE /api/items",
        "GET /api/organizations",
    ],
    "db": [
        "SELECT * FROM users",
        "INSERT INTO events",
        "UPDATE projects SET status",
        "DELETE FROM sessions",
        "SELECT * FROM transactions",
    ],
    "browser": [
        "browser.page_load",
        "browser.resource.script",
        "browser.resource.css",
        "browser.paint",
        "browser.mark",
    ],
    "resource": [
        "resource.script",
        "resource.link",
        "resource.img",
        "resource.fetch",
        "resource.xhr",
    ],
    "default": [
        "task.process",
        "queue.submit",
        "cache.get",
        "cache.set",
        "serialize.payload",
    ],
}


def _span_name_for_op(op: str) -> str:
    key = op.split(".")[0]
    names = _SPAN_NAMES_BY_OP.get(key, _SPAN_NAMES_BY_OP["default"])
    return random.choice(names)


def span_envelope_item_generator(
    min_items: int,
    max_items: int,
    min_duration_ms: int,
    max_duration_ms: int,
    min_attributes: int,
    max_attributes: int,
    release: str | None,
    environment: str | None,
    operations: Sequence[str],
):
    def inner():
        num_spans = random.randint(min_items, max_items)
        trace_id = uuid.uuid4().hex
        now = time.time()

        segment_duration = random.randint(min_duration_ms, max_duration_ms) / 1000.0
        segment_start = now - segment_duration
        segment_span_id = uuid.uuid4().hex[:16]
        segment_op = random.choice(operations)

        spans = [
            _create_span(
                trace_id=trace_id,
                span_id=segment_span_id,
                parent_span_id=None,
                is_segment=True,
                start_timestamp=segment_start,
                end_timestamp=now,
                op=segment_op,
                release=release,
                environment=environment,
                min_attributes=min_attributes,
                max_attributes=max_attributes,
            )
        ]

        for _ in range(num_spans - 1):
            child_duration_s = random.uniform(0, segment_duration)
            child_end = random.uniform(segment_start + child_duration_s, now)
            child_start = child_end - child_duration_s
            child_op = random.choice(operations)

            spans.append(
                _create_span(
                    trace_id=trace_id,
                    span_id=uuid.uuid4().hex[:16],
                    parent_span_id=segment_span_id,
                    is_segment=False,
                    start_timestamp=child_start,
                    end_timestamp=child_end,
                    op=child_op,
                    release=release,
                    environment=environment,
                    min_attributes=min_attributes,
                    max_attributes=max_attributes,
                )
            )

        return {"items": spans}

    return inner


def _create_span(
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    is_segment: bool,
    start_timestamp: float,
    end_timestamp: float,
    op: str,
    release: str | None,
    environment: str | None,
    min_attributes: int,
    max_attributes: int,
) -> dict:
    span = {
        "trace_id": trace_id,
        "span_id": span_id,
        "is_segment": is_segment,
        "name": _span_name_for_op(op),
        "status": random.choices(["ok", "error"], weights=[19, 1])[0],
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "attributes": _attribute_generator(
            op=op,
            release=release,
            environment=environment,
            min_attributes=min_attributes,
            max_attributes=max_attributes,
        ),
    }
    if parent_span_id is not None:
        span["parent_span_id"] = parent_span_id
    return span


def _attribute_generator(
    op: str,
    release: str | None,
    environment: str | None,
    min_attributes: int,
    max_attributes: int,
) -> dict:
    attrs = {
        "sentry.op": {"value": op, "type": "string"},
    }
    if release:
        attrs["sentry.release"] = {"value": release, "type": "string"}
    if environment:
        attrs["sentry.environment"] = {"value": environment, "type": "string"}

    num_extra = random.randint(min_attributes, max_attributes)
    for i in range(num_extra):
        attrs[f"attribute.{i}"] = {"value": f"value-{i}", "type": "string"}

    return attrs
