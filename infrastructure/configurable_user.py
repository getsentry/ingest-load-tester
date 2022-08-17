from collections import abc

from locust.contrib.fasthttp import FastHttpUser
from yaml import load

from .config import relay_address, generate_project_info, ProjectInfo
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
                tasks[task] = weight
            else:
                task = load_object(task_func_name, module_name)
                tasks[task] = weight
    else:
        raise ValueError(
            "Could not find a tasks dictionary attribute for user_name", user_name
        )

    if len(tasks) == 0:
        raise Exception(f"User with 0 tasks enabled name={user_name}")

    return tasks


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
    name, config_file_name, module_name, host=None, base_classes=None
):
    if base_classes is None:
        base_classes = (FastHttpUser,)

    config = _load_locust_config(config_file_name)
    locust_info = config.get(name)

    if locust_info is None:
        return None

    _weight = locust_info.get("weight", 1)

    if _weight == 0:
        return None  # locust is disabled don't bother loading it

    _tasks = create_tasks(name, locust_info, module_name)

    _wait_time = _get_wait_time(locust_info)
    if host is None:
        _host = relay_address()
    else:
        _host = host

    class ConfigurableUser(*base_classes):
        """
        Root class for a configurable User.
        """

        tasks = _tasks
        wait_time = _wait_time
        weight = _weight
        params = locust_info
        host = _host

        def get_params(self):
            return self.params

    ConfigurableUser.__name__ = name

    return ConfigurableUser


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
    return generate_project_info(num_projects)
