import functools
import os
from importlib import import_module
from uuid import uuid4
from sentry_relay.processing import StoreNormalizer


def full_path_from_module_relative_path(module_name, *args):
    dir_path = os.path.dirname(os.path.realpath(module_name))
    return os.path.abspath(os.path.join(dir_path, *args))


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
    return client.post(url, headers=headers, data=session_data)


def _auth_header(project_key):
    return "Sentry sentry_key={},sentry_version=7".format(project_key)


def get_uuid() -> hex:
    return uuid4().hex


def memoize(f):
    memo = {}

    @functools.wraps(f)
    def wrapper(*args):
        key_pattern = "{}_" * len(args)
        key = key_pattern.format(*args)
        if key not in memo:
            memo[key] = f(*args)
        return memo[key]

    return wrapper


def get_at_path(obj, path, default=None):
    """
    >>> x= {'a': {'b': {'c': 1, 'd': {'x': 1}, 'e': [1, 2, 3], 'f': 'hello'}}}
    >>> get_at_path(x, 'a.b.e')
    [1, 2, 3]
    >>> get_at_path(x, 'a.b.f')
    'hello'
    >>> get_at_path(x, 'a.b.c')
    1
    >>> get_at_path(x, 'a.b.d')
    {'x': 1}
    >>> get_at_path(x, 'a.b.d.x')
    1
    >>> get_at_path(x, 'm.n.p', {'x': "unknown"})
    {'x': "unknown"}
    """
    if path is None or obj is None:
        return default

    path = path.strip()

    if len(path) == 0:
        return default

    path = path.split(".")

    sub_obj = obj
    for name in path:
        if sub_obj is None or not isinstance(sub_obj, dict):
            return default
        sub_obj = sub_obj.get(name)
    return sub_obj


def load_object(name: str, locust_module_name):
    """
    Loads an object (class, function, etc) from its name.

    Note: Relative names will be resolved relative to this module (and it is not a recommended practice).
    For reliable results specify the full class name i.e. `package.module.object_name`
    """
    last_dot_offset = name.rfind(".")

    if last_dot_offset == -1:
        # the task is specified relative to the locust module
        # append the locust file module name to the name
        module_name = locust_module_name
    else:
        module_name = name[:last_dot_offset]

    module = import_module(module_name)
    object = getattr(module, name[last_dot_offset + 1 :])

    if object is None:
        raise ValueError("Could not find object", name)
    else:
        print(f"The loaded object {object}")
    return object


def normalize_event(event, project_id):
    normalizer = StoreNormalizer(project_id=project_id,)
    return normalizer.normalize_event(event)
