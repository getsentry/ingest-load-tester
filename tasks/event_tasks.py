"""
Contains tasks that generate various types of events
"""
import json
from datetime import datetime

from locust import TaskSet
from sentry_sdk.envelope import Envelope

from infrastructure import (
    send_message,
    send_envelope,
    send_session,
)
from infrastructure.configurable_locust import get_project_info
from infrastructure.generators.event import base_event_generator


def file_event_task_factory(task_params=None):
    filename = task_params.pop("filename")

    with open(filename) as f:
        event = json.load(f)

    def inner(task_set: TaskSet):
        """
        Sends a canned event from the event cache, the event is retrieved
        from
        """
        project_info = get_project_info(task_set)

        return send_message(task_set.client, project_info.id, project_info.key, event)

    return inner


def file_envelope_event_task_factory(task_params=None):
    filename = task_params.pop("filename")

    with open(filename) as f:
        event = json.load(f)

    def inner(task_set: TaskSet):
        project_info = get_project_info(task_set)

        envelope = Envelope()
        envelope.add_event(event)
        return send_envelope(
            task_set.client, project_info.id, project_info.key, envelope
        )

    return inner


def session_event_task_factory(task_params=None):
    release = task_params.pop("release")
    if not release:
        raise ValueError("'release' parameter is required")

    session_data_tmpl = (
        '{{"sent_at":"{started}"}}\n'
        + '{{"type":"session"}}\n'
        + '{{"init":true,"started":"{started}","status":"exited","errors":0,"duration":0,"attrs":{{"release":"{release}"}}}}'
    ).strip()

    def inner(task_set: TaskSet):
        project_info = get_project_info(task_set)
        started = datetime.utcnow().isoformat()[:-3] + "Z"
        session_data = session_data_tmpl.format(release=release, started=started)

        return send_session(
            task_set.client, project_info.id, project_info.key, session_data
        )

    return inner


def random_event_task_factory(task_params=None):
    if task_params is None:
        task_params = {}

    event_generator = base_event_generator(**task_params)

    def inner(task_set: TaskSet):
        event = event_generator()
        project_info = get_project_info(task_set)

        return send_message(task_set.client, project_info.id, project_info.key, event)

    return inner


def random_envelope_event_task_factory(task_params=None):
    if task_params is None:
        task_params = {}
    event_generator = base_event_generator(**task_params)

    def inner(task_set: TaskSet):
        event = event_generator()
        project_info = get_project_info(task_set)
        envelope = Envelope()
        envelope.add_event(event)
        return send_envelope(
            task_set.client, project_info.id, project_info.key, envelope
        )

    return inner
