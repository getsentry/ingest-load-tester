# Unified locustfile for all HTTP-based load tests (ingest + read API).
# Registers every task factory from both task modules so that
# create_org_user_classes() can resolve any task an org profile references.

import resource

# Raise the max number of open files
current_limits = resource.getrlimit(resource.RLIMIT_NOFILE)
new_limit = min(current_limits[1], 12000)
resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, new_limit))

from infrastructure import (
    full_path_from_module_relative_path,
    create_org_user_classes,
)
from tasks import event_tasks, read_api_tasks

# Register all task factories from both task modules into this module's namespace.
# load_object() resolves factory names against the locustfile's globals, so every
# factory referenced in a test YAML must be importable here.
for _mod in (event_tasks, read_api_tasks):
    for _name in dir(_mod):
        if _name.endswith("_task_factory"):
            globals()[_name] = getattr(_mod, _name)

# --- Load user classes ---
# Creates per-org user classes from config/http.test.yml, one per
# (org, task) pair defined in the organization profiles.

_config_path = full_path_from_module_relative_path(__file__, "config/http.test.yml")


def _load_user_classes():
    return {
        cls.__name__: cls for cls in create_org_user_classes(_config_path, __name__)
    }


globals().update(_load_user_classes())
