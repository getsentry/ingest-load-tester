import copy
import os
from unittest.mock import patch, MagicMock

import pytest

from infrastructure.config import (
    OrgProfile,
    load_org_profiles,
    generate_project_info,
)
from infrastructure.util import resolve_env_var
from infrastructure.configurable_user import (
    create_org_user_classes,
    _inject_org_params,
)


def _make_org_profile(**overrides):
    defaults = dict(
        slug="test-org",
        org_id=123,
        weight=1,
        relay_host="https://o123.ingest.us.sentry.io",
        auth_token="test-token",
        api_host="https://us.sentry.io",
        projects=[{"id": 100, "key": "aabbcc"}],
        project_slugs=["web-app"],
        user_tasks=["TransactionEvents"],
    )
    defaults.update(overrides)
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
    def test_parses_single_org(self, mock_config, monkeypatch):
        monkeypatch.setenv("ACME_TOKEN", "tok123")
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "acme",
                    "org_id": 123,
                    "weight": 5,
                    "relay_host": "https://o123.ingest.sentry.io",
                    "auth_token_env_var": "ACME_TOKEN",
                    "api_host": "https://sentry.io",
                    "projects": [{"id": 1, "key": "abc"}],
                    "project_slugs": ["web"],
                    "user_tasks": ["TransactionEvents", "LogEvents"],
                }
            ]
        }
        profiles = load_org_profiles()
        assert len(profiles) == 1
        org = profiles[0]
        assert org.slug == "acme"
        assert org.org_id == 123
        assert org.weight == 5
        assert org.relay_host == "https://o123.ingest.sentry.io"
        assert org.auth_token == "tok123"
        assert org.api_host == "https://sentry.io"
        assert org.projects == [{"id": 1, "key": "abc"}]
        assert org.project_slugs == ["web"]
        assert org.user_tasks == ["TransactionEvents", "LogEvents"]

    @patch("infrastructure.config.locust_config")
    def test_parses_multiple_orgs(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {"slug": "org-a", "weight": 3, "user_tasks": ["TaskA"]},
                {"slug": "org-b", "weight": 1, "user_tasks": ["TaskB"]},
            ]
        }
        profiles = load_org_profiles()
        assert len(profiles) == 2
        assert profiles[0].slug == "org-a"
        assert profiles[0].weight == 3
        assert profiles[1].slug == "org-b"
        assert profiles[1].weight == 1

    @patch("infrastructure.config.locust_config")
    def test_defaults_for_optional_fields(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {"slug": "minimal", "user_tasks": ["SomeTask"]},
            ]
        }
        profiles = load_org_profiles()
        org = profiles[0]
        assert org.weight == 1
        assert org.org_id is None
        assert org.relay_host is None
        assert org.auth_token is None
        assert org.api_host is None
        assert org.projects == []
        assert org.project_slugs == []

    @patch("infrastructure.config.locust_config")
    def test_resolves_auth_token_from_env_var(self, mock_config, monkeypatch):
        monkeypatch.setenv("ORG_TOKEN", "secret")
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "envorg",
                    "auth_token_env_var": "ORG_TOKEN",
                    "user_tasks": [],
                },
            ]
        }
        profiles = load_org_profiles()
        assert profiles[0].auth_token == "secret"

    @patch("infrastructure.config.locust_config")
    def test_auth_token_none_when_env_var_missing(self, mock_config, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_TOKEN", raising=False)
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "envorg",
                    "auth_token_env_var": "NONEXISTENT_TOKEN",
                    "user_tasks": [],
                },
            ]
        }
        profiles = load_org_profiles()
        assert profiles[0].auth_token is None

    @patch("infrastructure.config.locust_config")
    def test_auth_token_none_when_no_env_var_key(self, mock_config):
        mock_config.return_value = {
            "organizations": [
                {
                    "slug": "envorg",
                    "user_tasks": [],
                },
            ]
        }
        profiles = load_org_profiles()
        assert profiles[0].auth_token is None


class TestGenerateProjectInfoForOrg:
    def test_selects_from_org_projects(self):
        org = _make_org_profile(
            projects=[{"id": 42, "key": "mykey"}],
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

    def test_no_projects_raises(self):
        org = _make_org_profile(projects=[])
        with pytest.raises(ValueError, match="no projects configured"):
            generate_project_info(1, org_profile=org)

    def test_num_projects_capped_at_available(self):
        org = _make_org_profile(
            projects=[{"id": 1, "key": "k1"}, {"id": 2, "key": "k2"}],
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
            slug="acme",
            auth_token="tok",
            api_host="https://sentry.io",
            projects=[{"id": 1, "key": "k"}],
            project_slugs=["web"],
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
        assert task_info["organization_slug"] == "acme"
        assert task_info["auth_token"] == "tok"
        assert task_info["host"] == "https://sentry.io"
        assert task_info["project_ids"] == [1]
        assert task_info["project_slugs"] == ["web"]

    def test_org_identity_fields_override_yaml_defaults(self):
        org = _make_org_profile(
            slug="acme",
            auth_token="org-tok",
            api_host="https://acme.sentry.io",
        )
        locust_info = {
            "tasks": {
                "some_task_factory": {
                    "weight": 1,
                    "organization_slug": "yaml-slug",
                    "auth_token": "yaml-tok",
                    "host": "http://localhost:8000",
                }
            },
        }
        result = _inject_org_params(locust_info, org)
        task_info = result["tasks"]["some_task_factory"]
        assert task_info["organization_slug"] == "acme"
        assert task_info["auth_token"] == "org-tok"
        assert task_info["host"] == "https://acme.sentry.io"

    def test_project_fields_use_setdefault(self):
        org = _make_org_profile(
            projects=[{"id": 1, "key": "k"}, {"id": 2, "key": "k2"}],
            project_slugs=["web", "mobile"],
        )
        locust_info = {
            "tasks": {
                "some_task_factory": {
                    "weight": 1,
                    "project_ids": [99],
                    "project_slugs": ["custom"],
                }
            },
        }
        result = _inject_org_params(locust_info, org)
        task_info = result["tasks"]["some_task_factory"]
        assert task_info["project_ids"] == [99]
        assert task_info["project_slugs"] == ["custom"]

    def test_does_not_mutate_original(self):
        org = _make_org_profile(slug="acme")
        locust_info = {"tasks": {"some_task_factory": {"weight": 1}}}
        original_tasks = copy.deepcopy(locust_info)
        _inject_org_params(locust_info, org)
        assert locust_info == original_tasks

    def test_handles_sequence_tasks(self):
        org = _make_org_profile()
        locust_info = {
            "tasks": ["task_a", "task_b"],
        }
        result = _inject_org_params(locust_info, org)
        assert result["tasks"] == ["task_a", "task_b"]

    def test_skips_none_auth_token(self):
        org = _make_org_profile(auth_token=None)
        locust_info = {"tasks": {"some_task_factory": {"weight": 1}}}
        result = _inject_org_params(locust_info, org)
        assert "auth_token" not in result["tasks"]["some_task_factory"]


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
