"""
Contains tasks that generate various types of events
"""
import json
from datetime import datetime

from sentry_sdk.envelope import Envelope

from infrastructure import (
    send_message,
    send_envelope,
    send_session,
)
from infrastructure.configurable_user import get_project_info
from infrastructure.generators.event import base_event_generator
from infrastructure.generators.transaction import base_transaction_generator
from infrastructure.generators.util import envelope_header_generator
from infrastructure.util import get_at_path


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


def session_event_task_factory(task_params=None):
    release = task_params.pop("release")
    if not release:
        raise ValueError("'release' parameter is required")

    session_data_tmpl = (
        '{{"sent_at":"{started}"}}\n'
        + '{{"type":"session"}}\n'
        + '{{"init":true,"started":"{started}","status":"exited","errors":0,"duration":0,"attrs":{{"release":"{release}"}}}}'
    ).strip()

    def inner(user):
        project_info = get_project_info(user)
        started = datetime.utcnow().isoformat()[:-3] + "Z"
        session_data = session_data_tmpl.format(release=release, started=started)

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
        # push the current public key in params (this can't be hard coded)
        header_params = {
            **task_params,
            "public_key": project_info.key,
            "event_id": event.get("event_id"),
            "trace_id": get_at_path(event,"contexts.trace.trace_id"),
        }
        headers = envelope_header_generator(**header_params)()
        envelope = Envelope(headers=headers)
        envelope.add_event(event)
        return send_envelope(user.client, project_info.id, project_info.key, envelope)

    return inner


def random_envelope_transaction_task_factory(task_params=None):
    if task_params is None:
        task_params = {}
    transaction_generator = base_transaction_generator(**task_params)

    def inner(user):
        transaction = transaction_generator()
        project_info = get_project_info(user)
        header_params = {
            **task_params,
            "public_key": project_info.key,
            "event_id": transaction.get("event_id"),
            "trace_id": get_at_path(transaction,"contexts.trace.trace_id"),
        }
        headers = envelope_header_generator(**header_params)()
        envelope = Envelope(headers=headers)
        envelope.add_transaction(transaction)
        return send_envelope(user.client, project_info.id, project_info.key, envelope)

    return inner
