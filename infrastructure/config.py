from collections import namedtuple
from math import floor
from random import random
import os
import urllib.parse

from yaml import load

try:
    from yaml import CLoader as Loader, CDumper as Dumper, CFullLoader as FullLoader
except ImportError:
    from yaml import Loader, Dumper, FullLoader

from .util import full_path_from_module_relative_path, memoize


OrgProfile = namedtuple(
    "OrgProfile",
    "slug, org_id, weight, relay_host, auth_token, api_host, projects, project_slugs, user_tasks",
)


def _resolve_env_var(value):
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1])
    return value


def load_org_profiles():
    config = locust_config()
    orgs_raw = config.get("organizations")
    if not orgs_raw:
        return None

    profiles = []
    for org in orgs_raw:
        profiles.append(
            OrgProfile(
                slug=org["slug"],
                org_id=org.get("org_id"),
                weight=org.get("weight", 1),
                relay_host=_resolve_env_var(org.get("relay_host")),
                auth_token=_resolve_env_var(org.get("auth_token")),
                api_host=_resolve_env_var(org.get("api_host")),
                projects=org.get("projects", []),
                project_slugs=org.get("project_slugs", []),
                user_tasks=org.get("user_tasks", []),
            )
        )
    return profiles


def relay_address():
    config = locust_config()
    relay_settings = config.get("relay", {})
    host = relay_settings.get("host")

    if host is None:
        raise ValueError(
            "Missing relay.host settings from config file:{}".format(
                _config_file_path()
            )
        )

    return host


def kafka_config():
    config = locust_config()
    return config.get("kafka", {})


@memoize
def get_metrics_config():
    config = locust_config()
    return config.get("metrics", {})


@memoize
def metrics_enabled():
    metrics = get_metrics_config()
    return metrics.get("enabled", False)


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


ProjectInfo = namedtuple("ProjectInfo", "id, key, org_id, dsn")


def generate_project_info(num_projects, org_profile=None) -> ProjectInfo:
    if org_profile is not None:
        return _generate_project_info_for_org(num_projects, org_profile)

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

    host = config["relay"]["host"]
    parsed = urllib.parse.urlsplit(host)

    dsn = f"{parsed.scheme}://{project_key}:@{parsed.netloc}/{project_id}"
    org_id = None
    if parsed.netloc.startswith("o"):
        org_domain = parsed.netloc.split(".")[0]
        org_id = org_domain[1:]

    return ProjectInfo(id=project_id, key=project_key, org_id=org_id, dsn=dsn)


def _generate_project_info_for_org(num_projects, org_profile):
    org_projects = org_profile.projects
    if not org_projects:
        raise ValueError(
            f"Organization '{org_profile.slug}' has no projects configured"
        )

    # handles the case where an org has less projects than is designated in the user config
    num_available_from_org = len(org_projects)
    if num_projects > num_available_from_org:
        num_projects = num_available_from_org

    project_idx = 0
    if num_projects > 1:
        project_idx = floor(random() * num_projects)

    project_config = org_projects[project_idx]
    project_id = project_config["id"]
    project_key = project_config["key"]

    host = org_profile.relay_host or relay_address()
    parsed = urllib.parse.urlsplit(host)

    dsn = f"{parsed.scheme}://{project_key}:@{parsed.netloc}/{project_id}"
    org_id = org_profile.org_id
    if org_id is None and parsed.netloc.startswith("o"):
        org_domain = parsed.netloc.split(".")[0]
        org_id = org_domain[1:]

    return ProjectInfo(id=project_id, key=project_key, org_id=org_id, dsn=dsn)


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
