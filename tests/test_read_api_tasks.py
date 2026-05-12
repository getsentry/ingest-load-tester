from collections import Counter
from unittest.mock import MagicMock, patch

import pytest

from tasks.read_api_tasks import (
    _build_query_url,
    _choice,
    _fetch_issue_ids,
    _get_auth_token,
    _read_headers,
    group_details_task_factory,
    group_event_details_task_factory,
    group_events_task_factory,
    organization_events_stats_task_factory,
    organization_events_task_factory,
    organization_group_index_stats_task_factory,
    organization_group_index_task_factory,
    organization_releases_task_factory,
    organization_tags_task_factory,
    project_group_index_task_factory,
)


class TestHelpers:
    def test_get_auth_token_from_params(self):
        assert _get_auth_token({"auth_token": "tok123"}) == "tok123"

    def test_get_auth_token_missing_raises(self):
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
        with pytest.raises(ValueError, match="api_host is required"):
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
            {"auth_token": "tok", "org_slug": "sentry"}
        )
        assert callable(task)

    def test_request_url_structure(self):
        task = organization_group_index_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
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
        assert url.startswith("/api/0/organizations/sentry/issues/")
        assert "statsPeriod=1h" in url
        assert "sort=date" in url
        assert "limit=25" in url
        assert "query=is%3Aunresolved" in url
        assert call_args[1]["name"] == "/api/0/organizations/sentry/issues/"

    def test_bearer_auth_header(self):
        task = organization_group_index_task_factory(
            {"auth_token": "secret", "org_slug": "sentry"}
        )
        user = _make_mock_user()
        task(user)

        headers = user.client.get.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer secret"

    def test_project_filter(self):
        task = organization_group_index_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
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
        task = organization_events_task_factory(
            {"auth_token": "tok", "org_slug": "sentry"}
        )
        assert callable(task)

    def test_multi_value_fields(self):
        task = organization_events_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
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
                "org_slug": "sentry",
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
        task = organization_events_stats_task_factory(
            {"auth_token": "tok", "org_slug": "sentry"}
        )
        assert callable(task)

    def test_multi_value_yaxis(self):
        task = organization_events_stats_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
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
        assert url.startswith("/api/0/organizations/sentry/events-stats/")
        assert "yAxis=count" in url
        assert "yAxis=count_unique" in url

    def test_interval_param(self):
        task = organization_events_stats_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
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
            {"auth_token": "tok", "org_slug": "sentry", "api_host": "https://sentry.io"}
        )
        assert callable(task)

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_detail_url(self, mock_fetch):
        mock_fetch.return_value = ["42"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "detail_weight": 1,
                "latest_event_weight": 0,
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url == "/api/0/organizations/sentry/issues/42/"

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_latest_event_url(self, mock_fetch):
        mock_fetch.return_value = ["42"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "detail_weight": 0,
                "latest_event_weight": 1,
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url == "/api/0/organizations/sentry/issues/42/events/latest/"

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_weighted_distribution(self, mock_fetch):
        mock_fetch.return_value = ["1"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
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
                {
                    "auth_token": "tok",
                    "org_slug": "sentry",
                    "api_host": "https://sentry.io",
                }
            )

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_name_param_uses_template(self, mock_fetch):
        mock_fetch.return_value = ["99"]
        task = group_details_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
            }
        )
        user = _make_mock_user()
        task(user)

        name = user.client.get.call_args[1]["name"]
        assert "{id}" in name
        assert "99" not in name


class TestGroupEventDetails:
    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_factory_returns_callable(self, mock_fetch):
        mock_fetch.return_value = ["111", "222"]
        task = group_event_details_task_factory(
            {"auth_token": "tok", "org_slug": "sentry", "api_host": "https://sentry.io"}
        )
        assert callable(task)

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_url_uses_event_id_type(self, mock_fetch):
        mock_fetch.return_value = ["42"]
        task = group_event_details_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "event_id_types": ["recommended"],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url == "/api/0/organizations/sentry/issues/42/events/recommended/"

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_name_param_uses_template(self, mock_fetch):
        mock_fetch.return_value = ["99"]
        task = group_event_details_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
            }
        )
        user = _make_mock_user()
        task(user)

        name = user.client.get.call_args[1]["name"]
        assert "{id}" in name
        assert "{event_id}" in name
        assert "99" not in name

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_no_issue_ids_raises(self, mock_fetch):
        mock_fetch.return_value = []
        with pytest.raises(ValueError, match="Failed to fetch issue IDs"):
            group_event_details_task_factory(
                {
                    "auth_token": "tok",
                    "org_slug": "sentry",
                    "api_host": "https://sentry.io",
                }
            )

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_bearer_auth_header(self, mock_fetch):
        mock_fetch.return_value = ["1"]
        task = group_event_details_task_factory(
            {
                "auth_token": "secret",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
            }
        )
        user = _make_mock_user()
        task(user)

        headers = user.client.get.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer secret"


class TestOrganizationTags:
    def test_factory_returns_callable(self):
        task = organization_tags_task_factory(
            {"auth_token": "tok", "org_slug": "sentry"}
        )
        assert callable(task)

    def test_request_url_structure(self):
        task = organization_tags_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "stats_periods": ["1h"],
                "datasets": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.startswith("/api/0/organizations/sentry/tags/")
        assert "statsPeriod=1h" in url
        assert (
            user.client.get.call_args[1]["name"] == "/api/0/organizations/sentry/tags/"
        )

    def test_optional_dataset(self):
        task = organization_tags_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "datasets": ["events"],
                "stats_periods": ["1h"],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "dataset=events" in url

    def test_optional_project_filter(self):
        task = organization_tags_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "project_ids": [42],
                "stats_periods": ["1h"],
                "datasets": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "project=42" in url


class TestGroupEvents:
    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_factory_returns_callable(self, mock_fetch):
        mock_fetch.return_value = ["111"]
        task = group_events_task_factory(
            {"auth_token": "tok", "org_slug": "sentry", "api_host": "https://sentry.io"}
        )
        assert callable(task)

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_url_contains_issue_id(self, mock_fetch):
        mock_fetch.return_value = ["42"]
        task = group_events_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "stats_periods": ["24h"],
                "per_page_values": [10],
                "queries": [""],
                "full_options": [False],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "/issues/42/events/" in url

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_full_param(self, mock_fetch):
        mock_fetch.return_value = ["1"]
        task = group_events_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "stats_periods": ["24h"],
                "per_page_values": [10],
                "queries": [""],
                "full_options": [True],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "full=true" in url

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_name_param_uses_template(self, mock_fetch):
        mock_fetch.return_value = ["99"]
        task = group_events_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
            }
        )
        user = _make_mock_user()
        task(user)

        name = user.client.get.call_args[1]["name"]
        assert "{id}" in name
        assert "99" not in name

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_no_issue_ids_raises(self, mock_fetch):
        mock_fetch.return_value = []
        with pytest.raises(ValueError, match="Failed to fetch issue IDs"):
            group_events_task_factory(
                {
                    "auth_token": "tok",
                    "org_slug": "sentry",
                    "api_host": "https://sentry.io",
                }
            )


class TestOrganizationReleases:
    def test_factory_returns_callable(self):
        task = organization_releases_task_factory(
            {"auth_token": "tok", "org_slug": "sentry"}
        )
        assert callable(task)

    def test_request_url_structure(self):
        task = organization_releases_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "per_page_values": [25],
                "sort_options": ["date"],
                "summary_stats_periods": ["24h"],
                "queries": [""],
                "health_stat_options": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.startswith("/api/0/organizations/sentry/releases/")
        assert "per_page=25" in url
        assert "sort=date" in url
        assert "summaryStatsPeriod=24h" in url
        assert (
            user.client.get.call_args[1]["name"]
            == "/api/0/organizations/sentry/releases/"
        )

    def test_flatten_added_for_session_sorts(self):
        task = organization_releases_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "per_page_values": [10],
                "sort_options": ["sessions"],
                "summary_stats_periods": ["24h"],
                "queries": [""],
                "health_stat_options": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "sort=sessions" in url
        assert "flatten=1" in url

    def test_no_flatten_for_date_sort(self):
        task = organization_releases_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "per_page_values": [10],
                "sort_options": ["date"],
                "summary_stats_periods": ["24h"],
                "queries": [""],
                "health_stat_options": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "sort=date" in url
        assert "flatten" not in url

    def test_health_stat_param(self):
        task = organization_releases_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "per_page_values": [10],
                "sort_options": ["date"],
                "summary_stats_periods": ["24h"],
                "queries": [""],
                "health_stat_options": ["sessions"],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "healthStat=sessions" in url

    def test_optional_project_filter(self):
        task = organization_releases_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "project_ids": [42],
                "per_page_values": [10],
                "sort_options": ["date"],
                "summary_stats_periods": ["24h"],
                "queries": [""],
                "health_stat_options": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "project=42" in url


class TestProjectGroupIndex:
    def test_factory_returns_callable(self):
        task = project_group_index_task_factory(
            {"auth_token": "tok", "org_slug": "sentry", "project_slugs": ["my-project"]}
        )
        assert callable(task)

    def test_request_url_structure(self):
        task = project_group_index_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "project_slugs": ["web-app"],
                "stats_periods": ["24h"],
                "limits": [25],
                "sort_options": ["date"],
                "queries": ["is:unresolved"],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.startswith("/api/0/projects/sentry/web-app/issues/")
        assert "statsPeriod=24h" in url
        assert "sort=date" in url
        assert "limit=25" in url

    def test_name_param_uses_template(self):
        task = project_group_index_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "project_slugs": ["web-app"],
            }
        )
        user = _make_mock_user()
        task(user)

        name = user.client.get.call_args[1]["name"]
        assert "{project_slug}" in name
        assert "web-app" not in name

    def test_missing_project_slugs_raises(self):
        with pytest.raises(ValueError, match="project_slugs is required"):
            project_group_index_task_factory(
                {"auth_token": "tok", "org_slug": "sentry"}
            )

    def test_empty_project_slugs_raises(self):
        with pytest.raises(ValueError, match="project_slugs is required"):
            project_group_index_task_factory(
                {"auth_token": "tok", "org_slug": "sentry", "project_slugs": []}
            )


class TestOrganizationGroupIndexStats:
    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_factory_returns_callable(self, mock_fetch):
        mock_fetch.return_value = ["111", "222"]
        task = organization_group_index_stats_task_factory(
            {"auth_token": "tok", "org_slug": "sentry", "api_host": "https://sentry.io"}
        )
        assert callable(task)

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_request_url_structure(self, mock_fetch):
        mock_fetch.return_value = ["1", "2", "3"]
        task = organization_group_index_stats_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "batch_size": 2,
                "stats_periods": ["24h"],
                "group_stats_periods": ["14d"],
                "queries": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.startswith("/api/0/organizations/sentry/issues-stats/")
        assert "groups=" in url
        assert "statsPeriod=24h" in url
        assert "groupStatsPeriod=14d" in url

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_multi_value_groups(self, mock_fetch):
        mock_fetch.return_value = [str(i) for i in range(30)]
        task = organization_group_index_stats_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "batch_size": 5,
                "stats_periods": ["24h"],
                "queries": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.count("groups=") == 5

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_batch_size_capped_at_available(self, mock_fetch):
        mock_fetch.return_value = ["1", "2", "3"]
        task = organization_group_index_stats_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "batch_size": 25,
                "stats_periods": ["24h"],
                "queries": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert url.count("groups=") == 3

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_no_issue_ids_raises(self, mock_fetch):
        mock_fetch.return_value = []
        with pytest.raises(ValueError, match="Failed to fetch issue IDs"):
            organization_group_index_stats_task_factory(
                {
                    "auth_token": "tok",
                    "org_slug": "sentry",
                    "api_host": "https://sentry.io",
                }
            )

    @patch("tasks.read_api_tasks._fetch_issue_ids")
    def test_optional_project_filter(self, mock_fetch):
        mock_fetch.return_value = ["1"]
        task = organization_group_index_stats_task_factory(
            {
                "auth_token": "tok",
                "org_slug": "sentry",
                "api_host": "https://sentry.io",
                "project_ids": [42],
                "batch_size": 1,
                "stats_periods": ["24h"],
                "queries": [""],
            }
        )
        user = _make_mock_user()
        task(user)

        url = user.client.get.call_args[0][0]
        assert "project=42" in url
