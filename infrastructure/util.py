import functools
import os
import re

from datetime import timedelta
from importlib import import_module
from typing import Optional
from uuid import uuid4


def full_path_from_module_relative_path(module_name, *args):
    dir_path = os.path.dirname(os.path.realpath(module_name))
    return os.path.abspath(os.path.join(dir_path, *args))


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


def get_value_with_env_override(d, key, conversion_func=lambda x: x):
    """
    Gets a value from a dictionary
    If the value is a string with the format ${SOME_VAR}
    Then the environment variable SOME_VAL will be read and
    conversion_func(SOME_VAR) will be returned

    eg: get_value_with_env_override({"x":"${MY_VAR}"}, "x", int)
    will fetch the MY_VAR env var and try to convert it to int

    """
    val = d.get(key)
    if val is None:
        return None

    if isinstance(val, str):
        if val.startswith("${") and val.endswith("}"):
            var_name = val[2:-1]
            val = os.getenv(var_name)
            if val is not None:
                return conversion_func(val)

    return val


TIMEDELTA_REGEX = (
    r"(?P<minus>-)?"
    r"((?P<weeks>\d+)w)?"
    r"((?P<days>\d+)d)?"
    r"((?P<hours>\d+)h)?"
    r"((?P<minutes>\d+)m)?"
    r"((?P<seconds>\d+)s)?"
    r"((?P<milliseconds>\d+)ms)?"
)
TIMEDELTA_PATTERN = re.compile(TIMEDELTA_REGEX, re.IGNORECASE)


def parse_timedelta(delta: str) -> Optional[timedelta]:
    """Parses a human readable timedelta (3d5h19m2s57ms) into a datetime.timedelta.
    Delta includes:
    * - (for negative deltas)
    * Xw weeks
    * Xd days
    * Xh hours
    * Xm minutes
    * Xs seconds
    * Xms milliseconds

    >>> parse_timedelta("2s")
    datetime.timedelta(0, 2)
    >>> parse_timedelta("1h1s")
    datetime.timedelta(0, 3601)
    >>> parse_timedelta("1d1s")
    datetime.timedelta(1, 1)
    >>> parse_timedelta("2w17s")
    datetime.timedelta(14, 17)
    >>> parse_timedelta("-1s") + parse_timedelta("2s")
    datetime.timedelta(0, 1)
    """
    match = TIMEDELTA_PATTERN.match(delta)
    if match:
        groups = match.groupdict()
        sign = -1 if groups.pop("minus", None) else 1
        parts = {k: int(v) for k, v in groups.items() if v}
        return timedelta(**parts) * sign
    return None
