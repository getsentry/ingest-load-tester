"""
Contains tasks that generate various types of events
"""
import json
import uuid
from datetime import datetime, timedelta
import random

from sentry_sdk.envelope import Envelope

from infrastructure import (
    send_message,
    send_envelope,
    send_session,
)
from infrastructure.configurable_user import get_project_info
from infrastructure.generators.event import base_event_generator
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
    params = {
        "num_releases": (1, lambda x: int(x)),
        "num_environments": (1, lambda x: int(x)),
        "started_range": (timedelta(minutes=1), lambda x: parse_timedelta(x)),
        "num_users": (1, lambda x: int(x)),
        "ok_weight": (1.0, lambda x: float(x)),
        "exited_weight": (1.0, lambda x: float(x)),
        "errored_weight": (1.0, lambda x: float(x)),
        "crashed_weight": (1.0, lambda x: float(x)),
        "abnormal_weight": (1.0, lambda x: float(x)),
    }
    ret_val = {}
    for key, val in params.items():
        default, converter = val
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
        # get maximum deviation in seconds of start time
        max_start_deviation = int(params["started_range"].total_seconds())
        now = datetime.utcnow()
        started_time = now - timedelta(seconds=random.randint(0, max_start_deviation))
        started = started_time.isoformat()[:23] + "Z"  # date with milliseconds
        timestamp = now.isoformat()[:23]+"Z"
        rel = random.randint(1, params["num_releases"])
        release = f"r-1.0.{rel}"
        env = random.randint(1, params["num_environments"])
        environment = f"environment-{env}"

        ok = params["ok_weight"]
        exited = params["exited_weight"]
        errored = params["errored_weight"]
        crashed = params["crashed_weight"]
        abnormal = params["abnormal_weight"]
        status = random.choices(["ok", "exited", "errored", "crashed", "abnormal"], weights=[ok, exited, errored, crashed, abnormal])[0]

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
            duration=random.random() * 1000,
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
