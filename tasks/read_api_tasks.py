"""
Task factories for load-testing Sentry's highest-traffic read API endpoints.
"""

import logging
import os
import random
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)


def _resolve_env_var(value):
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1])
    return value


def _get_auth_token(task_params):
    token = _resolve_env_var(task_params.get("auth_token", ""))
    if not token:
        token = os.environ.get("AUTH_TOKEN")
    if not token:
        raise ValueError(
            "auth_token is required. Set it in task params or AUTH_TOKEN env var."
        )
    return token


def _read_headers(auth_token):
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


def _build_query_url(base_path, params):
    if not params:
        return base_path
    return f"{base_path}?{urlencode(params)}"


def _choice(choices, fallback):
    if choices:
        return random.choice(choices)
    return fallback


def organization_group_index_task_factory(task_params=None):
    """
    Issues list endpoint: GET /api/0/organizations/{org}/issues/

    Randomizes statsPeriod, sort, query, limit, and optional project filter per request.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    project_ids = task_params.get("project_ids", [])
    stats_periods = task_params.get("stats_periods", ["24h", "12h", "1h"])
    limits = task_params.get("limits", [25, 50, 100])
    sort_options = task_params.get("sort_options", ["date", "freq", "new", "trends"])
    queries = task_params.get("queries", ["is:unresolved", ""])

    base_path = f"/api/0/organizations/{org_slug}/issues/"
    headers = _read_headers(auth_token)

    def inner(user):
        params = [
            ("statsPeriod", _choice(stats_periods, "24h")),
            ("sort", _choice(sort_options, "date")),
            ("limit", _choice(limits, 25)),
        ]

        query = _choice(queries, "is:unresolved")
        if query:
            params.append(("query", query))

        if project_ids:
            params.append(("project", random.choice(project_ids)))

        url = _build_query_url(base_path, params)
        return user.client.get(url, headers=headers, name=base_path)

    return inner


def organization_events_task_factory(task_params=None):
    """
    Discover events endpoint: GET /api/0/organizations/{org}/events/

    Randomizes field sets, dataset, query, sort, and project filter per request.
    Each field in the chosen field set is added as a separate `field` query param.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    project_ids = task_params.get("project_ids", [])
    stats_periods = task_params.get("stats_periods", ["24h", "12h", "1h"])
    per_page_values = task_params.get("per_page_values", [10, 25, 50])
    field_sets = task_params.get(
        "field_sets",
        [
            ["title", "event.type", "project", "user.display", "timestamp"],
            ["title", "count()", "project"],
        ],
    )
    datasets = task_params.get("datasets", ["discover", "errors"])
    queries = task_params.get("queries", ["", "event.type:error"])
    sort_by = task_params.get("sort_by", ["-timestamp", "-count()"])

    base_path = f"/api/0/organizations/{org_slug}/events/"
    headers = _read_headers(auth_token)

    def inner(user):
        fields = _choice(field_sets, ["title", "event.type", "project", "timestamp"])
        params = [("field", f) for f in fields]

        params.append(("statsPeriod", _choice(stats_periods, "24h")))
        params.append(("per_page", _choice(per_page_values, 10)))

        dataset = _choice(datasets, "")
        if dataset:
            params.append(("dataset", dataset))

        query = _choice(queries, "")
        if query:
            params.append(("query", query))

        sort = _choice(sort_by, "")
        if sort:
            params.append(("sort", sort))

        if project_ids:
            params.append(("project", random.choice(project_ids)))

        url = _build_query_url(base_path, params)
        return user.client.get(url, headers=headers, name=base_path)

    return inner


def organization_events_stats_task_factory(task_params=None):
    """
    Time-series charting endpoint: GET /api/0/organizations/{org}/events-stats/

    Randomizes yAxis set, statsPeriod, interval, query, dataset, and project filter.
    Each yAxis in the chosen set is added as a separate `yAxis` query param.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    project_ids = task_params.get("project_ids", [])
    stats_periods = task_params.get("stats_periods", ["24h", "12h", "1h"])
    y_axes = task_params.get(
        "y_axes",
        [
            ["count()"],
            ["count()", "count_unique(user)"],
            ["p50(transaction.duration)", "p95(transaction.duration)"],
        ],
    )
    intervals = task_params.get("intervals", ["1h", "30m", "5m"])
    queries = task_params.get("queries", ["", "event.type:error"])
    datasets = task_params.get("datasets", ["discover", "errors"])

    base_path = f"/api/0/organizations/{org_slug}/events-stats/"
    headers = _read_headers(auth_token)

    def inner(user):
        y_axis_set = _choice(y_axes, ["count()"])
        params = [("yAxis", y) for y in y_axis_set]

        params.append(("statsPeriod", _choice(stats_periods, "24h")))
        params.append(("interval", _choice(intervals, "1h")))

        query = _choice(queries, "")
        if query:
            params.append(("query", query))

        dataset = _choice(datasets, "")
        if dataset:
            params.append(("dataset", dataset))

        if project_ids:
            params.append(("project", random.choice(project_ids)))

        url = _build_query_url(base_path, params)
        return user.client.get(url, headers=headers, name=base_path)

    return inner


def group_details_task_factory(task_params=None):
    """
    Issue detail endpoint with two sub-paths:
      - Detail:       GET /api/0/organizations/{org}/issues/{id}/
      - Latest event: GET /api/0/organizations/{org}/issues/{id}/events/latest/

    At construction time, fetches real issue IDs from the issues endpoint to avoid
    hardcoding. Uses weighted randomization to choose between detail and latest-event
    paths per request.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    # host is needed to pre-fetch issue IDs outside of Locust's client.
    # Prefer setting it in the YAML task params; API_HOST is a fallback.
    host = _resolve_env_var(task_params.get("host", "")) or os.environ.get("API_HOST")
    fetch_limit = task_params.get("fetch_limit", 100)
    detail_weight = task_params.get("detail_weight", 1)
    latest_event_weight = task_params.get("latest_event_weight", 0)

    issue_ids = _fetch_issue_ids(host, auth_token, org_slug, fetch_limit)
    if not issue_ids:
        raise ValueError(
            f"Failed to fetch issue IDs for org '{org_slug}'. "
            f"Ensure host (got: {host!r}) and auth_token are correct."
        )

    logger.info("Fetched %d issue IDs for group_details", len(issue_ids))

    headers = _read_headers(auth_token)
    detail_name = f"/api/0/organizations/{org_slug}/issues/{{id}}/"
    latest_event_name = f"/api/0/organizations/{org_slug}/issues/{{id}}/events/latest/"

    def inner(user):
        issue_id = random.choice(issue_ids)

        if latest_event_weight > 0 and detail_weight > 0:
            use_latest = random.choices(
                [False, True],
                weights=[detail_weight, latest_event_weight],
            )[0]
        elif latest_event_weight > 0:
            use_latest = True
        else:
            use_latest = False

        if use_latest:
            path = f"/api/0/organizations/{org_slug}/issues/{issue_id}/events/latest/"
            name = latest_event_name
        else:
            path = f"/api/0/organizations/{org_slug}/issues/{issue_id}/"
            name = detail_name

        return user.client.get(path, headers=headers, name=name)

    return inner


def _fetch_issue_ids(host, auth_token, org_slug, limit):
    if not host:
        raise ValueError(
            "host is required for group_details to fetch issue IDs. "
            "Set it in task params or API_HOST env var."
        )

    url = f"{host.rstrip('/')}/api/0/organizations/{org_slug}/issues/"
    headers = _read_headers(auth_token)

    try:
        resp = requests.get(url, headers=headers, params={"limit": limit}, timeout=30)
        resp.raise_for_status()
        issues = resp.json()
        return [str(issue["id"]) for issue in issues]
    except Exception as e:
        logger.error("Failed to fetch issue IDs from %s: %s", url, e)
        return []
