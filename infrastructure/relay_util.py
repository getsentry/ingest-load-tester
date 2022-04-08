from sentry_relay.processing import StoreNormalizer

from infrastructure.influxdb_metric_sink import timed_operation
from infrastructure.util import _auth_header


def send_message(client, project_id, project_key, msg_body, headers=None):
    url = "/api/{}/store/".format(project_id)
    headers = {
        "X-Sentry-Auth": _auth_header(project_key),
        "Content-Type": "application/json; charset=UTF-8",
        **(headers or {}),
    }
    return client.post(url, headers=headers, json=msg_body)


def send_envelope(client, project_id, project_key, envelope, headers=None):
    url = "/api/{}/envelope/".format(project_id)

    headers = {
        "X-Sentry-Auth": _auth_header(project_key),
        "Content-Type": "application/x-sentry-envelope",
        **(headers or {}),
    }

    data = envelope.serialize()
    return client.post(url, headers=headers, data=data)


def send_session(client, project_id, project_key, session_data, headers=None):
    url = "/api/{}/envelope/".format(project_id)

    headers = {
        "X-Sentry-Auth": _auth_header(project_key),
        "Content-Type": "text/plain; charset=UTF-8",
        **(headers or {}),
    }
    with timed_operation("session_request"):
        return client.post(url, headers=headers, data=session_data)


def normalize_event(event, project_id):
    normalizer = StoreNormalizer(
        project_id=project_id,
    )
    return normalizer.normalize_event(event)
