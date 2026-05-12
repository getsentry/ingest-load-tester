import copy
from collections import abc

from locust.contrib.fasthttp import FastHttpUser
from yaml import load

from .config import relay_address, generate_project_info, load_org_profiles, ProjectInfo
from .util import memoize, load_object

try:
    from yaml import CLoader as Loader, CDumper as Dumper, CFullLoader as FullLoader
except ImportError:
    from yaml import Loader, Dumper, FullLoader

from locust import TaskSet, HttpUser, constant, between, constant_pacing, Locust, User


def create_tasks(user_name, config, module_name):

    tasks_info = config.get("tasks")

    if isinstance(tasks_info, abc.Sequence):
        # we have a list of tasks with no params just load them
        tasks = [load_object(task_name, module_name) for task_name in tasks_info]
    elif isinstance(tasks_info, abc.Mapping):
        # we have tasks with attributes
        tasks = {}
        for task_func_name, task_info in tasks_info.items():
            if "weight" in task_info:
                weight = task_info["weight"]
                del task_info["weight"]
            else:
                weight = 1
            if weight == 0:
                continue  # task disabled

            if len(task_info) > 0:
                # we have other attributes besides frequency, the tasks are actually task factory functions
                task_factory = load_object(task_func_name, module_name)
                task = task_factory(task_info)
                if hasattr(task_factory, "host_field"):
                    task.host_field = task_factory.host_field
                tasks[task] = weight
            else:
                task = load_object(task_func_name, module_name)
                tasks[task] = weight
    else:
        raise ValueError(
            "Could not find a tasks dictionary attribute for user_name", user_name
        )

    if len(tasks) == 0:
        raise ("User with 0 tasks enabled", user_name)

    return tasks


_VALID_HOST_FIELDS = frozenset({"api_host", "relay_host"})


def host(field):
    if field not in _VALID_HOST_FIELDS:
        raise ValueError(
            f"Invalid host field {field!r}; expected one of {_VALID_HOST_FIELDS}"
        )

    def decorator(func):
        func.host_field = field
        return func

    return decorator


def _detect_host_field(tasks):
    host_fields = set()
    items = tasks.keys() if isinstance(tasks, dict) else tasks
    for task in items:
        host_field = getattr(task, "host_field", None)
        if host_field is not None:
            host_fields.add(host_field)
    # A user class with tasks from different modules (e.g. a read_api_tasks
    # factory and an event_tasks factory) would require two different hosts,
    # which Locust's FastHttpUser cannot support.
    if len(host_fields) > 1:
        raise ValueError(
            f"Tasks declare conflicting host_field values: {host_fields}. "
            f"All tasks in a user class must target the same host."
        )
    return host_fields.pop() if host_fields else None


def _get_wait_time(locust_info):
    """
    Evaluates a wait expression, the result should be a Callable[[None], float]

    in the locust file we expect something like:
    wait_time: between(12, 23)

    the following functions are recognized  between, constant, constant_pacing
    (all imported from the `locust` module)

    """
    wait_expr = locust_info.get("wait_time")

    if wait_expr is None:
        return constant(0)

    env_locals = {
        # add recognized functions (no attempt to recognize anything beyond what is here)
        "between": between,
        "constant": constant,
        "constant_pacing": constant_pacing,
    }
    return eval(wait_expr, globals(), env_locals)


def create_user_class(
    name,
    config_file_name,
    module_name,
    host=None,
    base_classes=None,
    org_profile=None,
    task_weight=None,
):
    if base_classes is None:
        base_classes = (FastHttpUser,)

    config = _load_locust_config(config_file_name)
    locust_info = config.get(name)

    if locust_info is None:
        return None

    if org_profile is not None:
        locust_info = _inject_org_params(locust_info, org_profile)

    # Org-based callers pass task_weight from locust.config.yml; the YAML
    # fallback covers direct callers like the kafka locustfile.
    _weight = task_weight if task_weight is not None else locust_info.get("weight", 1)
    if org_profile is not None:
        _weight = _weight * org_profile.weight

    if _weight == 0:
        return None  # locust is disabled don't bother loading it

    _tasks = create_tasks(name, locust_info, module_name)

    _wait_time = _get_wait_time(locust_info)
    if host is None:
        _host = None
        if org_profile is not None:
            detected = _detect_host_field(_tasks)
            if detected is None:
                raise ValueError(
                    f"No tasks in {name!r} declare a host_field. "
                    f"Use @host('api_host') or @host('relay_host') on each task factory."
                )
            _host = getattr(org_profile, detected, None)
        if _host is None:  # Non-org callers (e.g. kafka locustfile)
            _host = relay_address()
    else:
        _host = host

    _org_profile = org_profile

    class ConfigurableUser(*base_classes):
        """
        Root class for a configurable User.
        """

        tasks = _tasks
        wait_time = _wait_time
        weight = _weight
        params = locust_info
        host = _host
        org_profile = _org_profile

        def get_params(self):
            return self.params

    ConfigurableUser.__name__ = name
    ConfigurableUser.__qualname__ = name

    return ConfigurableUser


def create_org_user_classes(config_file_name, module_name, base_classes=None):
    org_profiles = load_org_profiles()
    config = _load_locust_config(config_file_name)
    classes = []

    for org in org_profiles:
        for task_entry in org.user_tasks:
            if task_entry.name not in config:
                continue

            class_name = f"{task_entry.name}_{org.slug.replace('-', '_')}"
            cls = create_user_class(
                task_entry.name,
                config_file_name,
                module_name,
                base_classes=base_classes,
                org_profile=org,
                task_weight=task_entry.weight,
            )
            if cls is not None:
                cls.__name__ = class_name
                cls.__qualname__ = class_name
                classes.append(cls)

    return classes


def _inject_org_params(locust_info, org_profile):
    locust_info = copy.deepcopy(locust_info)
    tasks_info = locust_info.get("tasks")
    if not isinstance(tasks_info, abc.Mapping):
        return locust_info

    for _task_name, task_info in tasks_info.items():
        if not isinstance(task_info, abc.Mapping):
            continue
        task_info["org_slug"] = org_profile.slug
        task_info["auth_token"] = org_profile.auth_token
        task_info["api_host"] = org_profile.api_host
        task_info["relay_host"] = org_profile.relay_host
        task_info["project_ids"] = [p["id"] for p in org_profile.projects]
        task_info["project_slugs"] = [p["slug"] for p in org_profile.projects]

    return locust_info


@memoize
def _load_locust_config(file_name):
    config = getattr(_load_locust_config, "config", None)
    if config is not None:
        return config
    with open(file_name, "r") as f:
        config = load(f, Loader=FullLoader)

    users = config.get("users")
    return users


def get_project_info(user) -> ProjectInfo:
    """
    Returns a randomly chosen project info for the locust.

    It assumes that the user is a ConfigurableUser derived object

    It expects a locust configuration with an entry for num_projects
    Something Like:

    users:
      SimpleLoadTest:
        num_projects: 10
    """
    locust_params = user.get_params()
    num_projects = locust_params.get("num_projects", 1)
    org_profile = getattr(user, "org_profile", None)
    return generate_project_info(num_projects, org_profile=org_profile)
