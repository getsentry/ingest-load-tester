import os
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest

from tasks.read_api_tasks import (
    _build_query_url,
    _choice,
    _fetch_issue_ids,
    _get_auth_token,
    _read_headers,
    _resolve_env_var,
    group_details_task_factory,
    organization_events_stats_task_factory,
    organization_events_task_factory,
    organization_group_index_task_factory,
)


class TestHelpers:
    def test_resolve_env_var_plain_string(self):
        assert _resolve_env_var("my-token") == "my-token"

    def test_resolve_env_var_from_env(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert _resolve_env_var("${MY_TOKEN}") == "secret123"

    def test_resolve_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        assert _resolve_env_var("${MISSING_VAR}") is None

    def test_get_auth_token_from_params(self):
        assert _get_auth_token({"auth_token": "tok123"}) == "tok123"

    def test_get_auth_token_from_env(self, monkeypatch):
        monkeypatch.setenv("AUTH_TOKEN", "env-tok")
        assert _get_auth_token({}) == "env-tok"

    def test_get_auth_token_env_var_syntax(self, monkeypatch):
        monkeypatch.setenv("MY_TOK", "resolved")
        assert _get_auth_token({"auth_token": "${MY_TOK}"}) == "resolved"

    def test_get_auth_token_missing_raises(self, monkeypatch):
        monkeypatch.delenv("AUTH_TOKEN", raising=False)
        with pytest.raises(ValueError, match="auth_token is required"):
            _get_auth_token({})

    def test_read_headers(self):
        headers = _read_headers("tok")
        assert headers["Authorization"] == "Bearer tok"

    def test_build_query_url_no_params(self):
        assert _build_query_url("/api/0/issues/", []) == "/api/0/issues/"
        assert _build_query_url("/api/0/issues/", None) == "/api/0/issues/"

    def test_build_query_url_with_params(self):
        url = _build_query_url("/api/0/issues/", [("limit", 25), ("sort", "date")])
        assert url == "/api/0/issues/?limit=25&sort=date"

    def test_build_query_url_multi_value(self):
        url = _build_query_url(
            "/api/0/events/", [("field", "title"), ("field", "count()")]
        )
        assert url == "/api/0/events/?field=title&field=count%28%29"

    def test_choice_with_values(self):
        assert _choice(["a"], "z") == "a"

    def test_choice_empty_returns_fallback(self):
        assert _choice([], "z") == "z"
        assert _choice(None, "z") == "z"


class TestFetchIssueIds:
    def test_missing_host_raises(self):
        with pytest.raises(ValueError, match="host is required"):
            _fetch_issue_ids(None, "tok", "sentry", 100)

    @patch("tasks.read_api_tasks.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        ids = _fetch_issue_ids("https://sentry.io", "tok", "sentry", 100)
        assert ids == ["1", "2", "3"]
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "sentry.io/api/0/organizations/sentry/issues/" in call_args[0][0]

    @patch("tasks.read_api_tasks.requests.get")
    def test_http_error_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("connection refused")
        ids = _fetch_issue_ids("https://sentry.io", "tok", "sentry", 100)
        assert ids == []


def _make_mock_user():
    user = MagicMock()
    user.client.get.return_value = MagicMock(status_code=200)
    return user


class TestOrganizationGroupIndex:
    def test_factory_returns_callable(self):
        task = organization_group_index_task_factory(
            {"auth_token": "tok", "organization_slug": "myorg"}
        )
        assert callable(task)

    def test_request_url_structure(self):
        task = organization_group_index_task_factory(
            {
                "auth_token": "tok",
                "organization_slug": "myorg",
                "stats_periods": ["1h"],
                "limits": [25],
                "sort_options": ["date"],
                "queries": ["is:unresolved"],
            }
        )
        user = _make_mock_user()
        task(user)

        call_args = user.client.get.call_args
        url = call_args[0][0]
        assert url.startswith("/api/0/organizations/myorg/issues/")
        assert "statsPeriod=1h" in url
        assert "sort=date" in url
        assert "limit=25" in url
        assert "query=is%3Aunresolved" in url
        assert call_args[1]["name"] == "/api/0/organizations/myorg/issues/"

    def test_bearer_auth_header(self):
        task = organization_group_index_task_factory({"auth_token": "secret"})
        user = _make_mock_user()
        task(user)

        headers = user.client.get.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer secret"

    def test_project_filter(self):
        task = organization_group_index_task_factory(
            {
                "auth_token": "tok",
                "project_ids": [42],
                "queries": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "project=42" in url


class TestOrganizationEvents:
    def test_factory_returns_callable(self):
        task = organization_events_task_factory({"auth_token": "tok"})
        assert callable(task)

    def test_multi_value_fields(self):
        task = organization_events_task_factory(
            {
                "auth_token": "tok",
                "organization_slug": "myorg",
                "field_sets": [["title", "count()", "project"]],
                "stats_periods": ["24h"],
                "per_page_values": [10],
                "datasets": [""],
                "queries": [""],
                "sort_by": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "field=title" in url
        assert "field=count" in url
        assert "field=project" in url

    def test_optional_dataset(self):
        task = organization_events_task_factory(
            {
                "auth_token": "tok",
                "datasets": ["discover"],
                "field_sets": [["title"]],
                "stats_periods": ["1h"],
                "per_page_values": [10],
                "queries": [""],
                "sort_by": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "dataset=discover" in url


class TestOrganizationEventsStats:
    def test_factory_returns_callable(self):
        task = organization_events_stats_task_factory({"auth_token": "tok"})
        assert callable(task)

    def test_multi_value_yaxis(self):
        task = organization_events_stats_task_factory(
            {
                "auth_token": "tok",
                "organization_slug": "myorg",
                "y_axes": [["count()", "count_unique(user)"]],
                "stats_periods": ["24h"],
                "intervals": ["1h"],
                "queries": [""],
                "datasets": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.startswith("/api/0/organizations/myorg/events-stats/")
        assert "yAxis=count" in url
        assert "yAxis=count_unique" in url

    def test_interval_param(self):
        task = organization_events_stats_task_factory(
            {
                "auth_token": "tok",
                "y_axes": [["count()"]],
                "stats_periods": ["12h"],
                "intervals": ["30m"],
                "queries": [""],
                "datasets": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "interval=30m" in url
        assert "statsPeriod=12h" in url


class TestGroupDetails:
    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_factory_returns_callable(self, mock_fetch):
        mock_fetch.return_value = ["111", "222"]
        task = group_details_task_factory(
            {"auth_token": "tok", "host": "https://sentry.io"}
        )
        assert callable(task)

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_detail_url(self, mock_fetch):
        mock_fetch.return_value = ["42"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "organization_slug": "myorg",
                "host": "https://sentry.io",
                "detail_weight": 1,
                "latest_event_weight": 0,
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url == "/api/0/organizations/myorg/issues/42/"

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_latest_event_url(self, mock_fetch):
        mock_fetch.return_value = ["42"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "organization_slug": "myorg",
                "host": "https://sentry.io",
                "detail_weight": 0,
                "latest_event_weight": 1,
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url == "/api/0/organizations/myorg/issues/42/events/latest/"

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_weighted_distribution(self, mock_fetch):
        mock_fetch.return_value = ["1"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "host": "https://sentry.io",
                "detail_weight": 7,
                "latest_event_weight": 3,
            }
        )
        user = _make_mock_user()

        counts = Counter()
        for _ in range(1000):
            task(user)
            url = user.client.get.call_args[0][0]
            if "events/latest" in url:
                counts["latest"] += 1
            else:
                counts["detail"] += 1

        assert 200 < counts["latest"] < 400
        assert 600 < counts["detail"] < 800

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_no_issue_ids_raises(self, mock_fetch):
        mock_fetch.return_value = []
        with pytest.raises(ValueError, match="Failed to fetch issue IDs"):
            group_details_task_factory(
                {"auth_token": "tok", "host": "https://sentry.io"}
            )

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_name_param_uses_template(self, mock_fetch):
        mock_fetch.return_value = ["99"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "organization_slug": "sentry",
                "host": "https://sentry.io",
            }
        )
        user = _make_mock_user()
        task(user)

        name = user.client.get.call_args[1]["name"]
        assert "{id}" in name
        assert "99" not in name
