import logging
from collections import namedtuple
from math import floor
import os
from random import random
import urllib.parse

import requests
from yaml import load

try:
    from yaml import CLoader as Loader, CDumper as Dumper, CFullLoader as FullLoader
except ImportError:
    from yaml import Loader, Dumper, FullLoader

from .util import full_path_from_module_relative_path, memoize, resolve_env_var

logger = logging.getLogger(__name__)


OrgProfile = namedtuple(
    "OrgProfile",
    "slug, org_id, weight, relay_host, auth_token, api_host, projects, user_tasks",
)


def _require(mapping, field, context):
    if field not in mapping:
        raise ValueError("{}: missing required '{}' field".format(context, field))
    return mapping[field]


def load_org_profiles():
    config = locust_config()
    orgs_raw = config.get("organizations")
    if not orgs_raw:
        raise ValueError(
            "No 'organizations' defined in {}. "
            "At least one organization is required.".format(_config_file_path())
        )

    profiles = []
    for i, org in enumerate(orgs_raw):
        org_slug = _require(org, "slug", "Organization at index {}".format(i))
        ctx = "Organization '{}'".format(org_slug)

        _require(org, "projects", ctx)
        if not org["projects"]:
            raise ValueError("{}: 'projects' must not be empty".format(ctx))
        for j, p in enumerate(org["projects"]):
            _require(p, "slug", "{}, project {}".format(ctx, j))

        api_host = resolve_env_var(_require(org, "api_host", ctx))
        env_var = _require(org, "auth_token_env_var", ctx)
        auth_token = os.environ.get(env_var)
        if not auth_token:
            raise ValueError(
                "{}: environment variable '{}' is not set".format(ctx, env_var)
            )

        profiles.append(
            OrgProfile(
                slug=org_slug,
                org_id=org.get("org_id"),
                weight=org.get("weight", 1),
                relay_host=resolve_env_var(org.get("relay_host")),
                auth_token=auth_token,
                api_host=api_host,
                projects=_resolve_projects(
                    org_slug, org["projects"], api_host, auth_token
                ),
                user_tasks=org.get("user_tasks", []),
            )
        )
    return profiles


def _resolve_projects(org_slug, projects, api_host, auth_token):
    """
    Resolve project id and key from the Sentry API for each project slug.
    """
    api_projects = _fetch_org_projects(org_slug, api_host, auth_token)
    by_slug = {p["slug"]: p for p in api_projects}

    resolved = []
    for proj in projects:
        slug = proj["slug"]
        api_proj = by_slug.get(slug)
        if api_proj is None:
            raise ValueError(
                "Organization '{}': project '{}' not found via API".format(
                    org_slug, slug
                )
            )

        key = _fetch_project_key(org_slug, slug, api_host, auth_token)
        resolved.append({"slug": slug, "id": api_proj["id"], "key": key})

    logger.info("Resolved %d project(s) for org '%s' from API", len(resolved), org_slug)
    return resolved


def _fetch_org_projects(org_slug, api_host, auth_token):
    url = "{}/api/0/organizations/{}/projects/".format(api_host.rstrip("/"), org_slug)
    headers = {"Authorization": "Bearer {}".format(auth_token)}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise ValueError(
            "Failed to fetch projects for org '{}' from {}: {}".format(org_slug, url, e)
        )


def _fetch_project_key(org_slug, project_slug, api_host, auth_token):
    url = "{}/api/0/projects/{}/{}/keys/".format(
        api_host.rstrip("/"), org_slug, project_slug
    )
    headers = {"Authorization": "Bearer {}".format(auth_token)}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        keys = resp.json()
        if not keys:
            raise ValueError(
                "No client keys found for project '{}/{}'".format(
                    org_slug, project_slug
                )
            )
        return keys[0]["public"]
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            "Failed to fetch keys for project '{}/{}' from {}: {}".format(
                org_slug, project_slug, url, e
            )
        )


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

    # Non-org path (kafka consumers only) — always uses fake projects.
    config = locust_config()

    project_idx = 0
    if num_projects > 1:
        project_idx = floor(random() * num_projects)

    project_id = project_idx + 1
    project_key = project_id_to_fake_project_key(project_id)

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
