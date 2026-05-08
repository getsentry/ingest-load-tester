import resource

# Raise the max number of open files
current_limits = resource.getrlimit(resource.RLIMIT_NOFILE)
new_limit = min(current_limits[1], 12000)
resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, new_limit))

from infrastructure import (
    full_path_from_module_relative_path,
    create_user_class,
    create_org_user_classes,
)
from tasks import read_api_tasks

# Expose task factories so the YAML config can reference them by name.
# Do NOT just import the functions in the module (you will get a warning that
# the function is not used, you will remove it and then will get a runtime error).
organization_group_index_task_factory = (
    read_api_tasks.organization_group_index_task_factory
)
organization_events_task_factory = read_api_tasks.organization_events_task_factory
organization_events_stats_task_factory = (
    read_api_tasks.organization_events_stats_task_factory
)
group_details_task_factory = read_api_tasks.group_details_task_factory
group_event_details_task_factory = read_api_tasks.group_event_details_task_factory
organization_tags_task_factory = read_api_tasks.organization_tags_task_factory
group_events_task_factory = read_api_tasks.group_events_task_factory
organization_releases_task_factory = read_api_tasks.organization_releases_task_factory
project_group_index_task_factory = read_api_tasks.project_group_index_task_factory
organization_group_index_stats_task_factory = (
    read_api_tasks.organization_group_index_stats_task_factory
)

_config_path = full_path_from_module_relative_path(__file__, "config/read_api.test.yml")
_org_classes = create_org_user_classes(
    _config_path, __name__, org_host_field="api_host"
)
if _org_classes:
    for _cls in _org_classes:
        globals()[_cls.__name__] = _cls
else:
    OrganizationGroupIndex = create_user_class(
        "OrganizationGroupIndex", _config_path, __name__
    )
    OrganizationEvents = create_user_class("OrganizationEvents", _config_path, __name__)
    OrganizationEventsStats = create_user_class(
        "OrganizationEventsStats", _config_path, __name__
    )
    GroupDetails = create_user_class("GroupDetails", _config_path, __name__)
    GroupEventDetails = create_user_class("GroupEventDetails", _config_path, __name__)
    OrganizationTags = create_user_class("OrganizationTags", _config_path, __name__)
    GroupEvents = create_user_class("GroupEvents", _config_path, __name__)
    OrganizationReleases = create_user_class(
        "OrganizationReleases", _config_path, __name__
    )
    ProjectGroupIndex = create_user_class("ProjectGroupIndex", _config_path, __name__)
    OrganizationGroupIndexStats = create_user_class(
        "OrganizationGroupIndexStats", _config_path, __name__
    )
