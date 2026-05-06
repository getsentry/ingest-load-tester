import resource

# Raise the max number of open files
current_limits = resource.getrlimit(resource.RLIMIT_NOFILE)
new_limit = min(current_limits[1], 12000)
resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, new_limit))

from infrastructure import full_path_from_module_relative_path, create_user_class
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

_config_path = full_path_from_module_relative_path(
    __file__, "config/read_api.test.yml"
)

OrganizationGroupIndex = create_user_class(
    "OrganizationGroupIndex", _config_path, __name__
)
OrganizationEvents = create_user_class("OrganizationEvents", _config_path, __name__)
OrganizationEventsStats = create_user_class(
    "OrganizationEventsStats", _config_path, __name__
)
GroupDetails = create_user_class("GroupDetails", _config_path, __name__)
