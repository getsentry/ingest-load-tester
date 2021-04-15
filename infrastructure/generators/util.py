import random
import uuid


def schema_generator(**fields):
    """
    Generate a dictionary instance according to the schema outlined by the
    provided kwargs. Supports:

    * string
    * number
    * callable
    * range object
    * list of any of the above (random item will be selected)
    """

    def inner():
        rv = {}
        for k, sub_generator in fields.items():
            if isinstance(sub_generator, (list, tuple, range)):
                sub_generator = random.choice(sub_generator)

            if isinstance(sub_generator, dict):
                sub_generator = schema_generator(**sub_generator)

            if callable(sub_generator):
                sub_generator = sub_generator()

            if sub_generator is not None:
                rv[k] = sub_generator

        return rv

    return inner


def version_generator(num_segments=3, max_version_segment=10):
    def inner():
        return ".".join(
            str(random.randrange(max_version_segment)) for _ in range(num_segments)
        )

    return inner


def string_databag_generator(max_length=10000):
    """
    Generate a really random string of potentially ludicrous length.
    """

    def inner():
        rv = []
        for _ in range(random.randrange(max_length)):
            rv.append(chr(random.randrange(0, 256)))

        return "".join(rv)

    return inner


_articles1 = ["The", "A"]
_articles2 = ["The", "An"]
_predicate = [
    "eats",
    "talks with",
    "looks at",
    "annoys",
    "collects",
    "sprays",
    "disrespects",
    "embarrasses",
    "empathises with",
    "slaps",
    "plays with",
    "runs after",
    "swims after",
]
_subject = [
    "man",
    "dog",
    "child",
    "woman",
    "girl",
    "boy",
    "lion",
    "cat",
    "wombat",
    "llama",
    "alpaca",
    "vicuna",
    "guanaco",
    "leopard",
    "cougar",
    "wallaby",
    "bear",
    "skunk",
    "rabbit",
    "badger",
]
_direct_object = _subject + [
    "meal",
    "baby",
    "table",
    "glass",
    "chronometer",
    "parliament",
    "computer",
    "cellular phone",
    "toy",
    "tortilla",
    "laptop",
    "bottle",
    "fountain pen",
]


def sentence_generator():
    def inner():
        subject = random.choice(_subject)

        while True:
            direct_object = random.choice(_direct_object)
            if direct_object != subject:
                break

        if subject[0] == "a":
            article1 = random.choice(_articles2)
        else:
            article1 = random.choice(_articles1)

        if _direct_object[0] == "a":
            article2 = random.choice(_articles2)
        else:
            article2 = random.choice(_articles1)

        article2 = article2.lower()

        predicate = random.choice(_predicate)

        return f"{article1} {subject} {predicate} {article2} {direct_object}."

    return inner


op_parts = [
    "celery",
    "task",
    "redis",
    "feature",
    "flagr",
    "has",
    "nodestore",
    "set_subkeys",
    "sentry",
    "reprocessing2",
    "save_unprocessed_event",
    "get_unprocessed_event",
    "relay",
    "actors",
    "connector",
    "controller",
    "events",
    "healthcheck",
    "mod",
    "outcome",
    "project",
    "project_cache",
    "project_local",
    "project_redis",
    "project_upstream",
    "relay",
    "server",
    "store",
    "upstream",
]


def op_generator():
    def inner():
        num_segments = random.randrange(1, 5)
        segments = []
        while len(segments) < num_segments:
            segment = random.choice(op_parts)
            if segment not in segments:
                segments.append(segment)
        return ".".join(segments)

    return inner


def trace_generator(
    trace_release=None,
    trace_user_id=None,
    trace_user_segment=None,
    trace_environment=None,
    public_key=None,
    trace_id= None,
    **kwargs
):
    """
    Generates the trace header to be placed in an envelope header

    """
    if trace_user_id is not None or trace_user_segment is not None:
        user_generator = {}
        if trace_user_segment is not None:
            user_generator["segment"] = trace_user_segment
        if trace_user_id is not None:
            user_generator["id"] = trace_user_id
    else:
        user_generator = None
    if trace_id is None:
        trace_id = uuid_generator()

    return schema_generator(
        release=trace_release,
        user=user_generator,
        environment=trace_environment,
        trace_id=trace_id,
        public_key=public_key
    )


def envelope_header_generator(event_id=None, **kwargs):
    return schema_generator(
        event_id=event_id,
        trace=trace_generator(**kwargs)
    )


def span_id_generator():
    def inner():
        return uuid.uuid4().hex[0:16]

    return inner


def uuid_generator():
    def inner():
        return uuid.uuid4().hex

    return inner
