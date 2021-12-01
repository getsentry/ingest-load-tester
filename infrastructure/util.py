import functools
import os
from importlib import import_module
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
