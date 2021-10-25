from collections import namedtuple
from math import floor
from random import random

from yaml import load

try:
    from yaml import CLoader as Loader, CDumper as Dumper, CFullLoader as FullLoader
except ImportError:
    from yaml import Loader, Dumper, FullLoader

from .util import full_path_from_module_relative_path, memoize


def relay_address():
    config = locust_config()
    relay_settings = config.get("relay", {})
    host = relay_settings.get("host")
    port = relay_settings.get("port")

    if host is None:
        raise "Missing relay.host settings from config file:{}".format(
            _config_file_path()
        )
    if port is None:
        raise "Missing relay.port settings from config file:{}".format(
            _config_file_path()
        )

    return "{}:{}".format(host, port)


def kafka_config():
    config = locust_config()
    return config.get("kafka", {})


@memoize
def locust_config():
    """
    Returns the program settings located in the main directory (just above this file's directory)
    with the name config.yml
    """
    file_name = _config_file_path()
    try:
        with open(file_name, "r") as file:
            return load(file, Loader=FullLoader)
    except Exception as err:
        print(
            "Error while getting the configuration file:{}\n {}".format(file_name, err)
        )
        raise ValueError("Invalid configuration")


ProjectInfo = namedtuple("ProjectInfo", "id, key")


def generate_project_info(num_projects) -> ProjectInfo:
    config = locust_config()

    use_fake_projects = config["use_fake_projects"]

    if not use_fake_projects:
        projects = config["projects"]
        num_available_projects = len(projects)
        if num_projects > num_available_projects:
            num_projects = num_available_projects

    project_idx = 0
    if num_projects > 1:
        project_idx = floor(random() * num_projects)

    if use_fake_projects:
        project_id = project_idx + 1
        project_key = project_id_to_fake_project_key(project_id)
    else:
        project_cfg = config["projects"][project_idx]
        project_id = project_cfg["id"]
        project_key = project_cfg["key"]

    return ProjectInfo(id=project_id, key=project_key)


def project_id_to_fake_project_key(proj_id: int) -> str:
    """
    Creates a fake project key from a project id ( with a simple
    convention that can be easily reversed by the fake sentry to obtain
    the project id ( the project id is at the end of the string and
    is preceded by at least one non numeric char).

    >>> project_id_to_fake_project_key(123)
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaa123'
    >>> project_id_to_fake_project_key(1)
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1'
    """
    proj_key_len = 32  # this is the length of our project keys
    return str(proj_id)[:proj_key_len].rjust(proj_key_len, "a")




def _config_file_path():
    return full_path_from_module_relative_path(
        __file__, "..", "config", "locust.config.yml"
    )
