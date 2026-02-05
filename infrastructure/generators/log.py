import time
import random
import uuid

from infrastructure.generators.util import (
    schema_generator,
    sentence_generator,
)


def log_envelope_item_generator(
    min_items: int,
    max_items: int,
    release: str | None,
    min_message_bytes: int,
    max_message_bytes: int,
    min_attributes: int,
    max_attributes: int,
):
    trace_id = uuid.uuid4().hex

    def inner():
        num_items = random.randint(min_items, max_items)
        items = []
        for _ in range(num_items):
            item = create_log_item(
                trace_id=trace_id,
                release=release,
                min_message_bytes=min_message_bytes,
                max_message_bytes=max_message_bytes,
                min_attributes=min_attributes,
                max_attributes=max_attributes,
            )
            items.append(item)
        return {"items": items}

    return inner


def create_log_item(
    trace_id: str |None,
    release: str | None,
    min_message_bytes: int,
    max_message_bytes: int,
    min_attributes: int,
    max_attributes: int,
):
    generator = schema_generator(
        trace_id=trace_id,
        span_id=lambda: uuid.uuid4().hex,
        level=["info", "warn", "error"],
        timestamp=time.time,
        body=log_body_generator(
            min_message_bytes=min_message_bytes,
            max_message_bytes=max_message_bytes
        ),
        attributes=attribute_generator(
            release=release,
            min_attributes=min_attributes,
            max_attributes=max_attributes,
        ),
    )
    return generator()

def log_body_generator(min_message_bytes: int, max_message_bytes: int):
    word_generator = sentence_generator()

    def inner():
        body_len = random.randint(min_message_bytes, max_message_bytes)
        body = ""
        while len(body) < body_len:
            new_words = word_generator()
            if (len(body) + len(new_words)) > body_len:
                new_words = new_words[0:body_len]
            body += new_words
        return body

    return inner


def attribute_generator(
    release: str | None,
    min_attributes: int,
    max_attributes: int,
):
    def inner():
        attrs = {}
        if release:
            attrs["sentry.release"] = {
                "value": release,
                "type": "string",
            }
        num_attrs = random.randint(min_attributes, max_attributes)
        for i in range(num_attrs):
            name = f"attribute-name-{i}"
            value = f"value-{i}"
            attrs[name] = {
                "value": value,
                "type": "string",
            }


        return attrs

    return inner
