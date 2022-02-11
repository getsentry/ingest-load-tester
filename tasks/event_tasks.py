"""
Contains tasks that generate various types of events
"""
import json
import uuid
from datetime import datetime, timedelta
import time
import random
from typing import Tuple, Callable, Any, Mapping, Optional, Sequence

from sentry_sdk.envelope import Envelope

from infrastructure import (
    send_message,
    send_envelope,
    send_session,
)
from infrastructure.configurable_user import get_project_info
from infrastructure.generators.breadcrumbs import breadcrumb_generator
from infrastructure.generators.contexts import (
    os_context_generator,
    device_context_generator,
    app_context_generator,
    trace_context_generator,
)
from infrastructure.generators.event import base_event_generator
from infrastructure.generators.transaction import (
    create_spans,
    measurements_generator,
    span_op_generator,
)
from infrastructure.generators.user import user_interface_generator
from infrastructure.generators.util import schema_generator
from infrastructure.util import parse_timedelta


def file_event_task_factory(task_params=None):
    filename = task_params.pop("filename")

    with open(filename) as f:
        event = json.load(f)

    def inner(user):
        """
        Sends a canned event from the event cache, the event is retrieved
        from
        """
        project_info = get_project_info(user)

        return send_message(user.client, project_info.id, project_info.key, event)

    return inner


def file_envelope_event_task_factory(task_params=None):
    filename = task_params.pop("filename")

    with open(filename) as f:
        event = json.load(f)

    def inner(user):
        project_info = get_project_info(user)

        envelope = Envelope()
        envelope.add_event(event)
        return send_envelope(user.client, project_info.id, project_info.key, envelope)

    return inner


def get_session_event_params(task_params):
    params_converter = {
        "num_releases": (1, lambda x: int(x)),
        "num_environments": (1, lambda x: int(x)),
        "started_range": (timedelta(minutes=1), lambda x: parse_timedelta(x)),
        "duration_range": (timedelta(minutes=1), lambda x: parse_timedelta(x)),
        "num_users": (1, lambda x: int(x)),
        "ok_weight": (1.0, lambda x: float(x)),
        "exited_weight": (1.0, lambda x: float(x)),
        "errored_weight": (1.0, lambda x: float(x)),
        "crashed_weight": (1.0, lambda x: float(x)),
        "abnormal_weight": (1.0, lambda x: float(x)),
    }
    return _convert_params(params_converter, task_params)


def _convert_params(
    params_converter: Mapping[str, Tuple[Any, Callable[[Any], Any]]], task_params
):
    """
    Converts parameters received from the configuration in the required parameters needed by the task
    The params_converter has the following structure
    {
        "<Param Name>": ( <Default Param value>, Func(<Value From Config>) -> Value of required type)
    }

    For the cases where the value used by the task can be set directly in JSON (or YAML)
    the conversion function can just be set to identity ( lambda x: x)

    In addition to performing conversion the function also provides a place to set default values.

    Example:
        task_params = { "interval": "2m", "max_col"s: 22 }
        conv = {
            "interval" : (timedelta(minutes=1), lambda x: parse_timedelta(x)),
            "min_col": (1, lambda x:x),
            "max_col": (100, lambda x:int(x)),
        }

        _convert_params(conv, task_params)
        # returns
        # {
        #    "interval": timedelta(minutes=2),
        #    "min_col": 1,
        #    "max_col": 22
        # }
    """

    def identity(x):
        return x

    ret_val = {}
    for key, val in params_converter.items():
        default, converter = val

        if converter is None:
            converter = identity

        try:
            param = task_params.get(key)
            if param is None:
                ret_val[key] = default

            ret_val[key] = converter(param)
        except:
            ret_val[key] = default

    return ret_val


def session_event_task_factory(task_params=None):
    params = get_session_event_params(task_params)

    session_data_tmpl = (
        '{{"sent_at":"{timestamp}"}}\n'
        + '{{"type":"session"}}\n'
        + '{{"init":{init},"started":"{started}","status":"{status}","errors":{errors},"duration":{duration},'
        + '"sid":"{session}","did":"{user}","seq":{seq},"timestamp":"{timestamp}",'
        + '"attrs":{{"release":"{release}","environment":"{environment}"}}}}'
    ).strip()

    def inner(user):
        project_info = get_project_info(user)
        # get maximum deviation in seconds of duration
        max_duration_deviation = int(params["duration_range"].total_seconds())
        # get maximum deviation in seconds of start time
        max_start_deviation = int(params["started_range"].total_seconds())
        now = datetime.utcnow()
        # set the base in the past enough for max_start_spread + max_duration_spread to end up before now
        base_start = now - timedelta(
            seconds=max_start_deviation + max_duration_deviation
        )
        started_time = base_start + timedelta(
            seconds=random.randint(0, max_start_deviation)
        )
        duration = random.randint(0, max_duration_deviation)
        started = started_time.isoformat()[:23] + "Z"  # date with milliseconds
        timestamp = now.isoformat()[:23] + "Z"
        rel = random.randint(1, params["num_releases"])
        release = f"r-1.0.{rel}"
        env = random.randint(1, params["num_environments"])
        environment = f"environment-{env}"

        ok = params["ok_weight"]
        exited = params["exited_weight"]
        errored = params["errored_weight"]
        crashed = params["crashed_weight"]
        abnormal = params["abnormal_weight"]
        status = random.choices(
            ["ok", "exited", "errored", "crashed", "abnormal"],
            weights=[ok, exited, errored, crashed, abnormal],
        )[0]

        if status == "ok":
            init = "true"
            seq = 0
        else:
            init = "false"
            seq = random.randint(1, 5)

        if status == "errored":
            errors = random.randint(1, 20)
        else:
            errors = 0

        usr = random.randint(1, params["num_users"])
        user_id = f"u-{usr}"

        session = uuid.uuid4()

        session_data = session_data_tmpl.format(
            started=started,
            init=init,
            status=status,
            errors=errors,
            duration=duration,
            session=session,
            user=user_id,
            seq=seq,
            timestamp=timestamp,
            release=release,
            environment=environment,
        )

        return send_session(
            user.client, project_info.id, project_info.key, session_data
        )

    return inner


def random_event_task_factory(task_params=None):
    if task_params is None:
        task_params = {}

    event_generator = base_event_generator(**task_params)

    def inner(user):
        event = event_generator()
        project_info = get_project_info(user)

        return send_message(user.client, project_info.id, project_info.key, event)

    return inner


def random_envelope_event_task_factory(task_params=None):
    if task_params is None:
        task_params = {}
    event_generator = base_event_generator(**task_params)

    def inner(user):
        event = event_generator()
        project_info = get_project_info(user)
        envelope = Envelope()
        envelope.add_event(event)
        return send_envelope(user.client, project_info.id, project_info.key, envelope)

    return inner


def transaction_event_task_factory(task_params=None):
    task_params = _get_transaction_event_params(task_params)

    generator = transaction_generator(**task_params)

    def inner(user):
        transaction_data = generator()
        project_info = get_project_info(user)
        envelope = Envelope()
        envelope.add_transaction(transaction_data)
        return send_envelope(user.client, project_info.id, project_info.key, envelope)

    return inner


def transaction_generator(
    num_releases: Optional[int],
    max_users: Optional[int],
    min_spans: int,
    max_spans: int,
    transaction_duration_max: timedelta,
    transaction_duration_min: timedelta,
    transaction_timestamp_spread: timedelta,
    min_breadcrumbs: int,
    max_breadcrumbs: int,
    breadcrumb_categories,
    breadcrumb_levels,
    breadcrumb_types,
    breadcrumb_messages,
    measurements: Sequence[str],
    operations: Sequence[str],
    **kwargs,  # additional ignored params
):
    basic_generator = schema_generator(
        event_id=lambda: uuid.uuid4().hex,
        release=(
            lambda: f"release{random.randrange(num_releases)}"
            if num_releases is not None
            else None
        ),
        transaction=[None, lambda: f"mytransaction{random.randrange(100)}"],
        logger=["foo.bar.baz", "bam.baz.bad", None],
        environment=["production", "development", "staging"],
        user=user_interface_generator(max_users=max_users),
        contexts={
            "os": [None, os_context_generator()],
            "device": [None, device_context_generator()],
            "app": [None, app_context_generator()],
            "trace": trace_context_generator(operations=operations),
        },
        breadcrumbs=breadcrumb_generator(
            min=min_breadcrumbs,
            max=max_breadcrumbs,
            categories=breadcrumb_categories,
            levels=breadcrumb_levels,
            types=breadcrumb_types,
            messages=breadcrumb_messages,
        ),
        measurements=measurements_generator(measurements=measurements),
    )

    def inner():
        # get the basic structure (before adding the spans)
        transaction_data = basic_generator()
        # extract trace_id and root span to use in child spans
        trace_ctx = transaction_data["contexts"]["trace"]
        trace_id = trace_ctx["trace_id"]
        transaction_id = trace_ctx["span_id"]
        now = time.time()
        duration_min_sec = transaction_duration_min.total_seconds()
        duration_max_sec = transaction_duration_max.total_seconds()
        range_seconds = duration_max_sec - duration_min_sec
        transaction_duration = timedelta(
            seconds=range_seconds * random.random() + duration_min_sec
        )
        transaction_delta = timedelta(
            seconds=transaction_timestamp_spread.total_seconds() * random.random()
        )

        timestamp = now - transaction_delta.total_seconds()
        transaction_start = timestamp - transaction_duration.total_seconds()

        spans = create_spans(
            min_spans=min_spans,
            max_spans=max_spans,
            transaction_id=transaction_id,
            trace_id=trace_id,
            transaction_start=transaction_start,
            timestamp=timestamp,
            operations_generator=span_op_generator(operations),
        )

        transaction_data["spans"] = spans
        transaction_data["timestamp"] = timestamp
        transaction_data["start_timestamp"] = transaction_start

        return transaction_data

    return inner


def _get_transaction_event_params(task_params):
    if task_params is None:
        task_params = {}

    conv = {
        "min_spans": (1, None),
        "max_spans": (10, None),
        "transaction_duration_max": (timedelta(hours=2), parse_timedelta),
        "transaction_duration_min": (timedelta(minutes=1), parse_timedelta),
        "transaction_timestamp_spread": (timedelta(minutes=1), parse_timedelta),
        "num_releases": (None, None),
        "max_users": (1, None),
        "min_breadcrumbs": (1, None),
        "max_breadcrumbs": (1, None),
        "breadcrumb_categories": (None, None),
        "breadcrumb_levels": (None, None),
        "breadcrumb_types": (None, None),
        "breadcrumb_messages": (None, None),
        "measurements": ([], None),
        "operations": (["pageload"], None),
    }
    return _convert_params(params_converter=conv, task_params=task_params)
