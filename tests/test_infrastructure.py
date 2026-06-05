import copy
from unittest.mock import patch, MagicMock

import pytest

from infrastructure.config import (
    OrgProfile,
    UserTaskConfig,
    load_org_profiles,
    generate_project_info,
    _resolve_projects,
    _parse_user_tasks,
    _api_session,
)
from infrastructure.util import resolve_env_var
from infrastructure.configurable_user import (
    create_org_user_classes,
    create_user_class,
    _inject_org_params,
    _detect_host_field,
)


def _make_org_profile(**overrides):
    defaults = dict(
        slug="test-org",
        org_id=123,
        weight=1,
        relay_host="https://o123.ingest.us.sentry.io",
        auth_token="test-token",
        api_host="https://us.sentry.io",
        projects=[{"id": 100, "key": "aabbcc", "slug": "web-app"}],
        user_tasks=[UserTaskConfig("TransactionEvents", 1)],
    )
    defaults.update(overrides)
    if "user_tasks" in overrides:
        defaults["user_tasks"] = [
            UserTaskConfig(t, 1) if isinstance(t, str) else t
            for t in defaults["user_tasks"]
        ]
    return OrgProfile(**defaults)


class TestResolveEnvVar:
    def test_plain_string(self):
        assert resolve_env_var("hello") == "hello"

    def test_env_var_syntax(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "resolved")
        assert resolve_env_var("${MY_VAR}") == "resolved"

    def test_missing_env_var(self, monkeypatch):
        monkeypatch.delenv("MISSING", raising=False)
        assert resolve_env_var("${MISSING}") is None

    def test_none_passthrough(self):
        assert resolve_env_var(None) is None

    def test_non_string_passthrough(self):
        assert resolve_env_var(42) == 42


class TestLoadOrgProfiles:
    @patch("infrastructure.config.locust_config")
    def test_raises_when_no_organizations(self, mock_config):
        mock_config.return_value = {"relay": {"host": "http://localhost"}}
        with pytest.raises(ValueError, match="No 'organizations' defined"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_for_empty_organizations(self, mock_config):
        mock_config.return_value = {"organizations": []}
        with pytest.raises(ValueError, match="No 'organizations' defined"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_when_org_missing_slug(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {"projects": [{"slug": "p"}], "user_tasks": []},
            ]
        }
        with pytest.raises(ValueError, match="missing required 'slug' field"):
            load_org_profiles()

    @patch("infrastructure.config._resolve_projects")
    @patch("infrastructure.config.locust_config")
    def test_parses_single_org(self, mock_config, mock_resolve, monkeypatch):
        monkeypatch.setenv("ACME_TOKEN", "tok123")
        mock_resolve.return_value = [{"id": 1, "key": "abc", "slug": "web"}]
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "sentry",
                    "org_id": 123,
                    "weight": 5,
                    "relay_host": "https://o123.ingest.sentry.io",
                    "auth_token_env_var": "ACME_TOKEN",
                    "api_host": "https://sentry.io",
                    "projects": [{"slug": "web"}],
                    "user_tasks": [
                        {"name": "TransactionEvents", "weight": 2},
                        {"name": "LogEvents", "weight": 5},
                    ],
                }
            ]
        }
        profiles = load_org_profiles()
        assert len(profiles) == 1
        org = profiles[0]
        assert org.slug == "sentry"
        assert org.org_id == 123
        assert org.weight == 5
        assert org.relay_host == "https://o123.ingest.sentry.io"
        assert org.auth_token == "tok123"
        assert org.api_host == "https://sentry.io"
        assert org.projects == [{"id": 1, "key": "abc", "slug": "web"}]
        assert org.user_tasks == [
            UserTaskConfig("TransactionEvents", 2),
            UserTaskConfig("LogEvents", 5),
        ]

    @patch("infrastructure.config._resolve_projects")
    @patch("infrastructure.config.locust_config")
    def test_user_task_weight_defaults_to_one(
        self, mock_config, mock_resolve, monkeypatch
    ):
        monkeypatch.setenv("TOK", "t")
        mock_resolve.return_value = [{"id": 1, "key": "k", "slug": "p"}]
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "org-a",
                    "auth_token_env_var": "TOK",
                    "api_host": "https://a.io",
                    "projects": [{"slug": "p"}],
                    "user_tasks": [{"name": "TaskA"}],
                },
            ]
        }
        profiles = load_org_profiles()
        assert profiles[0].user_tasks == [UserTaskConfig("TaskA", 1)]

    @patch("infrastructure.config._resolve_projects")
    @patch("infrastructure.config.locust_config")
    def test_parses_multiple_orgs(self, mock_config, mock_resolve, monkeypatch):
        monkeypatch.setenv("TOK", "t")
        mock_resolve.side_effect = [
            [{"id": 1, "key": "k", "slug": "p"}],
            [{"id": 2, "key": "k", "slug": "p"}],
        ]
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "org-a",
                    "weight": 3,
                    "auth_token_env_var": "TOK",
                    "api_host": "https://a.io",
                    "projects": [{"slug": "p"}],
                    "user_tasks": [{"name": "TaskA"}],
                },
                {
                    "slug": "org-b",
                    "weight": 1,
                    "auth_token_env_var": "TOK",
                    "api_host": "https://b.io",
                    "projects": [{"slug": "p"}],
                    "user_tasks": [{"name": "TaskB"}],
                },
            ]
        }
        profiles = load_org_profiles()
        assert len(profiles) == 2
        assert profiles[0].slug == "org-a"
        assert profiles[0].weight == 3
        assert profiles[1].slug == "org-b"
        assert profiles[1].weight == 1

    @patch("infrastructure.config.locust_config")
    def test_raises_when_no_projects(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {"slug": "no-projects", "user_tasks": ["SomeTask"]},
            ]
        }
        with pytest.raises(ValueError, match="missing required 'projects'"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_when_empty_projects(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {"slug": "empty", "projects": [], "user_tasks": ["SomeTask"]},
            ]
        }
        with pytest.raises(ValueError, match="'projects' must not be empty"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_when_project_missing_slug(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "bad-proj",
                    "auth_token_env_var": "TOK",
                    "api_host": "https://sentry.io",
                    "projects": [{"id": 1}],
                    "user_tasks": ["SomeTask"],
                },
            ]
        }
        with pytest.raises(ValueError, match="missing required 'slug' field"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_when_missing_api_host(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "myorg",
                    "auth_token_env_var": "TOK",
                    "projects": [{"slug": "web"}],
                    "user_tasks": [],
                },
            ]
        }
        with pytest.raises(ValueError, match="missing required 'api_host'"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_when_missing_auth_token_env_var(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "myorg",
                    "api_host": "https://sentry.io",
                    "projects": [{"slug": "web"}],
                    "user_tasks": [],
                },
            ]
        }
        with pytest.raises(ValueError, match="missing required 'auth_token_env_var'"):
            load_org_profiles()

    @patch("infrastructure.config.locust_config")
    def test_raises_when_env_var_not_set(self, mock_config, monkeypatch):
        monkeypatch.delenv("MISSING_TOKEN", raising=False)
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "myorg",
                    "api_host": "https://sentry.io",
                    "auth_token_env_var": "MISSING_TOKEN",
                    "projects": [{"slug": "web"}],
                    "user_tasks": [],
                },
            ]
        }
        with pytest.raises(
            ValueError, match="environment variable 'MISSING_TOKEN' is not set"
        ):
            load_org_profiles()

    @patch("infrastructure.config._resolve_projects")
    @patch("infrastructure.config.locust_config")
    def test_parses_user_tasks_with_weight_overrides(
        self, mock_config, mock_resolve, monkeypatch
    ):
        monkeypatch.setenv("TOK", "t")
        mock_resolve.return_value = [{"id": 1, "key": "k", "slug": "p"}]
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "org-a",
                    "auth_token_env_var": "TOK",
                    "api_host": "https://a.io",
                    "projects": [{"slug": "p"}],
                    "user_tasks": [
                        {"name": "PlainTask"},
                        {"name": "WeightedTask", "weight": 7},
                    ],
                },
            ]
        }
        profiles = load_org_profiles()
        assert profiles[0].user_tasks == [
            UserTaskConfig("PlainTask", 1),
            UserTaskConfig("WeightedTask", 7),
        ]

    @patch("infrastructure.config._resolve_projects")
    @patch("infrastructure.config.locust_config")
    def test_resolves_projects_via_api(self, mock_config, mock_resolve, monkeypatch):
        monkeypatch.setenv("TOK", "secret")
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "myorg",
                    "auth_token_env_var": "TOK",
                    "api_host": "https://sentry.io",
                    "projects": [{"slug": "web"}],
                    "user_tasks": [{"name": "TaskA"}],
                },
            ]
        }
        mock_resolve.return_value = [{"id": 42, "key": "abc", "slug": "web"}]
        profiles = load_org_profiles()
        assert profiles[0].projects == [{"id": 42, "key": "abc", "slug": "web"}]
        mock_resolve.assert_called_once_with(
            "myorg", [{"slug": "web"}], "https://sentry.io", "secret"
        )


class TestGenerateProjectInfoForOrg:
    def test_selects_from_org_projects(self):
        org = _make_org_profile(
            projects=[{"id": 42, "key": "mykey", "slug": "proj"}],
            relay_host="https://o123.ingest.sentry.io",
            org_id=123,
        )
        info = generate_project_info(1, org_profile=org)
        assert info.id == 42
        assert info.key == "mykey"
        assert info.org_id == 123
        assert "mykey" in info.dsn
        assert "o123.ingest.sentry.io" in info.dsn

    def test_org_id_from_profile_takes_precedence(self):
        org = _make_org_profile(
            org_id=999,
            relay_host="https://o123.ingest.sentry.io",
        )
        info = generate_project_info(1, org_profile=org)
        assert info.org_id == 999

    def test_org_id_extracted_from_relay_host_when_none(self):
        org = _make_org_profile(
            org_id=None,
            relay_host="https://o456.ingest.sentry.io",
        )
        info = generate_project_info(1, org_profile=org)
        assert info.org_id == "456"

    def test_num_projects_capped_at_available(self):
        org = _make_org_profile(
            projects=[
                {"id": 1, "key": "k1", "slug": "p1"},
                {"id": 2, "key": "k2", "slug": "p2"},
            ],
        )
        info = generate_project_info(100, org_profile=org)
        assert info.id in (1, 2)

    @patch("infrastructure.config.relay_address", return_value="http://localhost:3000")
    def test_falls_back_to_relay_address_when_no_relay_host(self, mock_relay):
        org = _make_org_profile(relay_host=None, api_host=None)
        info = generate_project_info(1, org_profile=org)
        assert "localhost:3000" in info.dsn


class TestInjectOrgParams:
    def test_injects_into_task_info(self):
        org = _make_org_profile(
            slug="sentry",
            auth_token="tok",
            api_host="https://sentry.io",
            projects=[{"id": 1, "key": "k", "slug": "web"}],
        )
        locust_info = {
            "weight": 1,
            "tasks": {
                "some_task_factory": {
                    "weight": 1,
                }
            },
        }
        result = _inject_org_params(locust_info, org)
        task_info = result["tasks"]["some_task_factory"]
        assert task_info["org_slug"] == "sentry"
        assert task_info["auth_token"] == "tok"
        assert task_info["api_host"] == "https://sentry.io"
        assert task_info["relay_host"] == "https://o123.ingest.us.sentry.io"
        assert task_info["project_ids"] == [1]
        assert task_info["project_slugs"] == ["web"]

    def test_project_fields_from_org_profile(self):
        org = _make_org_profile(
            projects=[
                {"id": 1, "key": "k", "slug": "web"},
                {"id": 2, "key": "k2", "slug": "mobile"},
            ],
        )
        locust_info = {
            "tasks": {
                "some_task_factory": {
                    "weight": 1,
                }
            },
        }
        result = _inject_org_params(locust_info, org)
        task_info = result["tasks"]["some_task_factory"]
        assert task_info["project_ids"] == [1, 2]
        assert task_info["project_slugs"] == ["web", "mobile"]


class TestCreateOrgUserClasses:
    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_creates_classes_for_matching_tasks(
        self, mock_create, mock_load_config, mock_load_orgs
    ):
        mock_load_orgs.return_value = [
            _make_org_profile(slug="org-a", user_tasks=["TaskA", "TaskB"]),
        ]
        mock_load_config.return_value = {
            "TaskA": {"weight": 1, "tasks": {}},
            "TaskB": {"weight": 2, "tasks": {}},
        }
        mock_cls_a = MagicMock()
        mock_cls_a.__name__ = "TaskA"
        mock_cls_b = MagicMock()
        mock_cls_b.__name__ = "TaskB"
        mock_create.side_effect = [mock_cls_a, mock_cls_b]

        classes = create_org_user_classes("/fake/path.yml", "__main__")
        assert len(classes) == 2
        assert classes[0].__name__ == "TaskA_org_a"
        assert classes[1].__name__ == "TaskB_org_a"

    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_skips_tasks_not_in_config(
        self, mock_create, mock_load_config, mock_load_orgs
    ):
        mock_load_orgs.return_value = [
            _make_org_profile(
                slug="org-a",
                user_tasks=["TaskA", "NonExistentTask"],
            ),
        ]
        mock_load_config.return_value = {
            "TaskA": {"weight": 1, "tasks": {}},
        }
        mock_cls = MagicMock()
        mock_cls.__name__ = "TaskA"
        mock_create.return_value = mock_cls

        classes = create_org_user_classes("/fake/path.yml", "__main__")
        assert len(classes) == 1
        assert mock_create.call_count == 1

    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_passes_org_profile_to_create_user_class(
        self, mock_create, mock_load_config, mock_load_orgs
    ):
        org = _make_org_profile(slug="myorg", user_tasks=["TaskA"])
        mock_load_orgs.return_value = [org]
        mock_load_config.return_value = {
            "TaskA": {"weight": 1, "tasks": {}},
        }
        mock_cls = MagicMock()
        mock_cls.__name__ = "TaskA"
        mock_create.return_value = mock_cls

        create_org_user_classes("/fake/path.yml", "__main__")
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["org_profile"] is org

    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_returns_empty_list_when_all_classes_disabled(
        self, mock_create, mock_load_config, mock_load_orgs
    ):
        mock_load_orgs.return_value = [
            _make_org_profile(slug="org-a", user_tasks=["TaskA"]),
        ]
        mock_load_config.return_value = {
            "TaskA": {"weight": 0, "tasks": {}},
        }
        mock_create.return_value = None

        result = create_org_user_classes("/fake/path.yml", "__main__")
        assert result == []

    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_multiple_orgs_multiple_tasks(
        self, mock_create, mock_load_config, mock_load_orgs
    ):
        mock_load_orgs.return_value = [
            _make_org_profile(slug="org-a", weight=5, user_tasks=["TaskA", "TaskB"]),
            _make_org_profile(slug="org-b", weight=1, user_tasks=["TaskA"]),
        ]
        mock_load_config.return_value = {
            "TaskA": {"weight": 1, "tasks": {}},
            "TaskB": {"weight": 2, "tasks": {}},
        }
        mock_classes = []
        for name in ["TaskA", "TaskB", "TaskA"]:
            cls = MagicMock()
            cls.__name__ = name
            mock_classes.append(cls)
        mock_create.side_effect = mock_classes

        classes = create_org_user_classes("/fake/path.yml", "__main__")
        assert len(classes) == 3
        names = [c.__name__ for c in classes]
        assert "TaskA_org_a" in names
        assert "TaskB_org_a" in names
        assert "TaskA_org_b" in names


class TestParseUserTasks:
    def test_dict_with_weight(self):
        result = _parse_user_tasks([{"name": "TaskA", "weight": 5}], "test")
        assert result == [UserTaskConfig("TaskA", 5)]

    def test_weight_defaults_to_one(self):
        result = _parse_user_tasks([{"name": "TaskA"}], "test")
        assert result == [UserTaskConfig("TaskA", 1)]

    def test_multiple_entries(self):
        result = _parse_user_tasks(
            [{"name": "TaskA", "weight": 3}, {"name": "TaskB", "weight": 7}],
            "test",
        )
        assert result == [
            UserTaskConfig("TaskA", 3),
            UserTaskConfig("TaskB", 7),
        ]

    def test_dict_missing_name_raises(self):
        with pytest.raises(ValueError, match="missing required 'name'"):
            _parse_user_tasks([{"weight": 5}], "test")

    def test_plain_string_raises(self):
        with pytest.raises(ValueError, match="expected a mapping"):
            _parse_user_tasks(["TaskA"], "test")

    def test_empty_list(self):
        assert _parse_user_tasks([], "test") == []


class TestCreateOrgUserClassesWeightOverride:
    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_passes_task_weight_from_user_task_config(
        self, mock_create, mock_load_config, mock_load_orgs
    ):
        mock_load_orgs.return_value = [
            _make_org_profile(
                slug="org-a",
                user_tasks=[UserTaskConfig("TaskA", 10)],
            ),
        ]
        mock_load_config.return_value = {
            "TaskA": {"tasks": {}},
        }
        mock_cls = MagicMock()
        mock_cls.__name__ = "TaskA"
        mock_create.return_value = mock_cls

        create_org_user_classes("/fake/path.yml", "__main__")
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["task_weight"] == 10

    @patch("infrastructure.configurable_user.load_org_profiles")
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_user_class")
    def test_default_weight_is_one(self, mock_create, mock_load_config, mock_load_orgs):
        mock_load_orgs.return_value = [
            _make_org_profile(
                slug="org-a",
                user_tasks=[UserTaskConfig("TaskA", 1)],
            ),
        ]
        mock_load_config.return_value = {
            "TaskA": {"tasks": {}},
        }
        mock_cls = MagicMock()
        mock_cls.__name__ = "TaskA"
        mock_create.return_value = mock_cls

        create_org_user_classes("/fake/path.yml", "__main__")
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["task_weight"] == 1


class TestResolveProjects:
    @patch("infrastructure.config._fetch_project_key", return_value="resolved-key")
    @patch("infrastructure.config._fetch_org_projects")
    def test_resolves_id_and_key_from_api(self, mock_fetch_projects, mock_fetch_key):
        mock_fetch_projects.return_value = [
            {"id": 42, "slug": "web"},
        ]
        result = _resolve_projects("org", [{"slug": "web"}], "https://sentry.io", "tok")
        assert result == [{"slug": "web", "id": 42, "key": "resolved-key"}]
        mock_fetch_key.assert_called_once_with("org", "web", "https://sentry.io", "tok")

    @patch("infrastructure.config._fetch_project_key", return_value="k")
    @patch("infrastructure.config._fetch_org_projects")
    def test_resolves_multiple_projects(self, mock_fetch_projects, mock_fetch_key):
        mock_fetch_projects.return_value = [
            {"id": 1, "slug": "web"},
            {"id": 2, "slug": "mobile"},
        ]
        result = _resolve_projects(
            "org",
            [{"slug": "web"}, {"slug": "mobile"}],
            "https://sentry.io",
            "tok",
        )
        assert len(result) == 2
        assert result[0]["slug"] == "web"
        assert result[1]["slug"] == "mobile"

    @patch("infrastructure.config._fetch_org_projects")
    def test_raises_when_project_not_found(self, mock_fetch_projects):
        mock_fetch_projects.return_value = [
            {"id": 99, "slug": "other"},
        ]
        with pytest.raises(ValueError, match="not found via API"):
            _resolve_projects("org", [{"slug": "missing"}], "https://sentry.io", "tok")


class TestApiSession:
    def test_session_is_reused(self):
        assert _api_session() is _api_session()

    def test_session_has_retry_adapter(self):
        session = _api_session()
        adapter = session.get_adapter("https://sentry.io")
        retry = adapter.max_retries
        assert retry.total == 5
        assert 429 in retry.status_forcelist
        assert 503 in retry.status_forcelist


class TestDetectHostField:
    def test_returns_none_for_empty_tasks(self):
        assert _detect_host_field({}) is None

    def test_returns_none_when_no_host_field(self):
        def task_a():
            pass

        assert _detect_host_field({task_a: 1}) is None

    def test_detects_api_host(self):
        from tasks.read_api_tasks import organization_group_index_task_factory

        assert (
            _detect_host_field({organization_group_index_task_factory: 1}) == "api_host"
        )

    def test_detects_relay_host(self):
        from tasks.event_tasks import transaction_event_task_factory

        assert _detect_host_field({transaction_event_task_factory: 1}) == "relay_host"

    def test_consistent_host_fields_ok(self):
        from tasks.read_api_tasks import (
            organization_group_index_task_factory,
            organization_events_task_factory,
        )

        tasks = {
            organization_group_index_task_factory: 1,
            organization_events_task_factory: 1,
        }
        assert _detect_host_field(tasks) == "api_host"

    def test_conflicting_host_fields_raises(self):
        from tasks.read_api_tasks import organization_group_index_task_factory
        from tasks.event_tasks import transaction_event_task_factory

        tasks = {
            organization_group_index_task_factory: 1,
            transaction_event_task_factory: 1,
        }
        with pytest.raises(ValueError, match="conflicting host_field"):
            _detect_host_field(tasks)

    def test_works_with_list_tasks(self):
        from tasks.read_api_tasks import organization_group_index_task_factory

        assert _detect_host_field([organization_group_index_task_factory]) == "api_host"

    def test_mixed_with_and_without_host_field(self):
        from tasks.read_api_tasks import organization_group_index_task_factory

        def plain_task():
            pass

        tasks = {organization_group_index_task_factory: 1, plain_task: 1}
        assert _detect_host_field(tasks) == "api_host"


class TestCreateUserClassHostValidation:
    @patch(
        "infrastructure.configurable_user.relay_address",
        return_value="http://localhost:3000",
    )
    @patch("infrastructure.configurable_user._load_locust_config")
    @patch("infrastructure.configurable_user.create_tasks")
    def test_falls_back_to_relay_address_when_no_host_field(
        self, mock_create_tasks, mock_load_config, mock_relay
    ):
        mock_load_config.return_value = {
            "TestUser": {"weight": 1, "tasks": {}},
        }

        def plain_task():
            pass

        mock_create_tasks.return_value = {plain_task: 1}

        org = _make_org_profile(slug="org-a")
        cls = create_user_class(
            "TestUser", "/fake/path.yml", "__main__", org_profile=org
        )
        assert cls is not None
        assert cls.host == "http://localhost:3000"
