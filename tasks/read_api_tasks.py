"""
Task factories for load-testing Sentry's highest-traffic read API endpoints.
"""

import logging
import os
import random
from urllib.parse import urlencode

import requests

from infrastructure.util import resolve_env_var

logger = logging.getLogger(__name__)


def _get_auth_token(task_params):
    token = task_params.get("auth_token")
    if not token:
        raise ValueError(
            "auth_token is required. Set auth_token_env_var on the organization profile."
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


def _is_sort_in_fields(sort_key, fields):
    bare = sort_key.lstrip("-")
    return bare in fields


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

        # we can't sort by an aggregate (e.g. -count()) not present in fields
        valid_sorts = [s for s in sort_by if _is_sort_in_fields(s, fields)]
        sort = _choice(valid_sorts, "") if valid_sorts else ""
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

    # transaction.duration metrics aren't available on the "errors" dataset
    _transaction_y_axes = {
        "p50(transaction.duration)",
        "p95(transaction.duration)",
        "p99(transaction.duration)",
        "avg(transaction.duration)",
    }

    def _is_y_axis_compatible(y_axis_set, dataset):
        if dataset != "errors":
            return True
        return not any(y in _transaction_y_axes for y in y_axis_set)

    def inner(user):
        dataset = _choice(datasets, "")
        compatible = [ys for ys in y_axes if _is_y_axis_compatible(ys, dataset)]
        y_axis_set = _choice(compatible, ["count()"]) if compatible else ["count()"]
        params = [("yAxis", y) for y in y_axis_set]

        params.append(("statsPeriod", _choice(stats_periods, "24h")))
        params.append(("interval", _choice(intervals, "1h")))

        query = _choice(queries, "")
        if query:
            params.append(("query", query))

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
    host = resolve_env_var(task_params.get("host", "")) or os.environ.get("API_HOST")
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


def group_event_details_task_factory(task_params=None):
    """
    Issue event detail endpoint:
      GET /api/0/organizations/{org}/issues/{id}/events/{event_id}/

    Pre-fetches real issue IDs at construction time. Each request picks a random
    issue and a random event_id type (latest, oldest, recommended).
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    host = resolve_env_var(task_params.get("host", "")) or os.environ.get("API_HOST")
    fetch_limit = task_params.get("fetch_limit", 100)
    event_id_types = task_params.get(
        "event_id_types", ["latest", "oldest", "recommended"]
    )

    issue_ids = _fetch_issue_ids(host, auth_token, org_slug, fetch_limit)
    if not issue_ids:
        raise ValueError(
            f"Failed to fetch issue IDs for org '{org_slug}'. "
            f"Ensure host (got: {host!r}) and auth_token are correct."
        )

    logger.info("Fetched %d issue IDs for group_event_details", len(issue_ids))

    headers = _read_headers(auth_token)
    name = f"/api/0/organizations/{org_slug}/issues/{{id}}/events/{{event_id}}/"

    def inner(user):
        issue_id = random.choice(issue_ids)
        event_id = _choice(event_id_types, "latest")
        path = f"/api/0/organizations/{org_slug}/issues/{issue_id}/events/{event_id}/"
        return user.client.get(path, headers=headers, name=name)

    return inner


def organization_tags_task_factory(task_params=None):
    """
    Organization tags endpoint: GET /api/0/organizations/{org}/tags/

    Powers filter dropdowns across the UI. Randomizes statsPeriod, dataset,
    and optional project filter per request.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    project_ids = task_params.get("project_ids", [])
    stats_periods = task_params.get("stats_periods", ["24h", "12h", "1h"])
    datasets = task_params.get("datasets", ["events", "discover"])

    base_path = f"/api/0/organizations/{org_slug}/tags/"
    headers = _read_headers(auth_token)

    def inner(user):
        params = [("statsPeriod", _choice(stats_periods, "24h"))]

        dataset = _choice(datasets, "")
        if dataset:
            params.append(("dataset", dataset))

        if project_ids:
            params.append(("project", random.choice(project_ids)))

        url = _build_query_url(base_path, params)
        return user.client.get(url, headers=headers, name=base_path)

    return inner


def group_events_task_factory(task_params=None):
    """
    Issue events list endpoint: GET /api/0/organizations/{org}/issues/{id}/events/

    Pre-fetches real issue IDs.Randomizes query, full (triggers expensive serialization), statsPeriod, and
    per_page per request.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    host = resolve_env_var(task_params.get("host", "")) or os.environ.get("API_HOST")
    fetch_limit = task_params.get("fetch_limit", 100)
    queries = task_params.get("queries", [""])
    full_options = task_params.get("full_options", [True, False])
    stats_periods = task_params.get("stats_periods", ["24h", "12h", "1h"])
    per_page_values = task_params.get("per_page_values", [10, 25, 50])

    issue_ids = _fetch_issue_ids(host, auth_token, org_slug, fetch_limit)
    if not issue_ids:
        raise ValueError(
            f"Failed to fetch issue IDs for org '{org_slug}'. "
            f"Ensure host (got: {host!r}) and auth_token are correct."
        )

    logger.info("Fetched %d issue IDs for group_events", len(issue_ids))

    headers = _read_headers(auth_token)
    name = f"/api/0/organizations/{org_slug}/issues/{{id}}/events/"

    def inner(user):
        issue_id = random.choice(issue_ids)
        params = [
            ("statsPeriod", _choice(stats_periods, "24h")),
            ("per_page", _choice(per_page_values, 10)),
        ]

        query = _choice(queries, "")
        if query:
            params.append(("query", query))

        if _choice(full_options, False):
            params.append(("full", "true"))

        path = f"/api/0/organizations/{org_slug}/issues/{issue_id}/events/"
        url = _build_query_url(path, params)
        return user.client.get(url, headers=headers, name=name)

    return inner


def organization_releases_task_factory(task_params=None):
    """
    Release listing endpoint: GET /api/0/organizations/{org}/releases/

    Randomizes per_page, sort, query, summaryStatsPeriod, healthStat, and
    optional project filter. Session-based sorts require flatten=1.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    project_ids = task_params.get("project_ids", [])
    per_page_values = task_params.get("per_page_values", [10, 25, 50])
    sort_options = task_params.get(
        "sort_options", ["date", "sessions", "crash_free_users"]
    )
    queries = task_params.get("queries", [""])
    health_stat_options = task_params.get("health_stat_options", ["sessions", ""])
    summary_stats_periods = task_params.get(
        "summary_stats_periods", ["24h", "48h", "7d", "14d"]
    )

    _session_sorts = frozenset(
        [
            "crash_free_sessions",
            "crash_free_users",
            "sessions",
            "users",
            "sessions_24h",
            "users_24h",
        ]
    )

    base_path = f"/api/0/organizations/{org_slug}/releases/"
    headers = _read_headers(auth_token)

    def inner(user):
        sort = _choice(sort_options, "date")
        params = [
            ("per_page", _choice(per_page_values, 10)),
            ("sort", sort),
            ("summaryStatsPeriod", _choice(summary_stats_periods, "24h")),
        ]

        if sort in _session_sorts:
            params.append(("flatten", "1"))

        query = _choice(queries, "")
        if query:
            params.append(("query", query))

        health_stat = _choice(health_stat_options, "")
        if health_stat:
            params.append(("healthStat", health_stat))

        if project_ids:
            params.append(("project", random.choice(project_ids)))

        url = _build_query_url(base_path, params)
        return user.client.get(url, headers=headers, name=base_path)

    return inner


def project_group_index_task_factory(task_params=None):
    """
    Project-scoped issue list: GET /api/0/projects/{org}/{project_slug}/issues/

    Same Snuba search path as organization_group_index but scoped to a single
    project. Requires project_slugs in config.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    project_slugs = task_params.get("project_slugs", [])
    if not project_slugs:
        raise ValueError(
            "project_slugs is required for project_group_index. "
            "Provide a list of project slugs in task params."
        )

    stats_periods = task_params.get("stats_periods", ["24h", "14d"])
    limits = task_params.get("limits", [25, 50, 100])
    sort_options = task_params.get("sort_options", ["date", "new"])
    queries = task_params.get("queries", ["is:unresolved", ""])

    headers = _read_headers(auth_token)
    name = f"/api/0/projects/{org_slug}/{{project_slug}}/issues/"

    def inner(user):
        project_slug = random.choice(project_slugs)
        params = [
            ("statsPeriod", _choice(stats_periods, "24h")),
            ("sort", _choice(sort_options, "date")),
            ("limit", _choice(limits, 25)),
        ]

        query = _choice(queries, "is:unresolved")
        if query:
            params.append(("query", query))

        path = f"/api/0/projects/{org_slug}/{project_slug}/issues/"
        url = _build_query_url(path, params)
        return user.client.get(url, headers=headers, name=name)

    return inner


def organization_group_index_stats_task_factory(task_params=None):
    """
    Issues stats companion endpoint: GET /api/0/organizations/{org}/issues-stats/

    Fired alongside the issue list to fetch sparkline data. Pre-fetches real
    issue IDs, then sends batches of group IDs per request.
    """
    if task_params is None:
        task_params = {}

    auth_token = _get_auth_token(task_params)
    org_slug = task_params.get("organization_slug", "sentry")
    host = resolve_env_var(task_params.get("host", "")) or os.environ.get("API_HOST")
    fetch_limit = task_params.get("fetch_limit", 100)
    batch_size = task_params.get("batch_size", 25)
    project_ids = task_params.get("project_ids", [])
    stats_periods = task_params.get("stats_periods", ["24h", "12h", "1h"])
    group_stats_periods = task_params.get("group_stats_periods", ["24h", "14d", "auto"])
    queries = task_params.get("queries", ["is:unresolved", ""])

    issue_ids = _fetch_issue_ids(host, auth_token, org_slug, fetch_limit)
    if not issue_ids:
        raise ValueError(
            f"Failed to fetch issue IDs for org '{org_slug}'. "
            f"Ensure host (got: {host!r}) and auth_token are correct."
        )

    logger.info(
        "Fetched %d issue IDs for organization_group_index_stats", len(issue_ids)
    )

    base_path = f"/api/0/organizations/{org_slug}/issues-stats/"
    headers = _read_headers(auth_token)

    def inner(user):
        sample_size = min(batch_size, len(issue_ids))
        batch = random.sample(issue_ids, sample_size)
        params = [("groups", gid) for gid in batch]

        params.append(("statsPeriod", _choice(stats_periods, "24h")))
        params.append(("groupStatsPeriod", _choice(group_stats_periods, "24h")))

        query = _choice(queries, "")
        if query:
            params.append(("query", query))

        if project_ids:
            params.append(("project", random.choice(project_ids)))

        url = _build_query_url(base_path, params)
        return user.client.get(url, headers=headers, name=base_path)

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
