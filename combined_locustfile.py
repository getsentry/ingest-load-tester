# Combined locustfile for running both ingest and read API tasks in a single
# Locust process. This is necessary for multi-org mode because org profiles in
# locust.config.yml define a single user_tasks list spanning both ingest tasks
# (e.g. TransactionEvents) and read API tasks (e.g. OrganizationGroupIndex).
# The individual locustfiles (simple_locustfile.py, read_api_locustfile.py) each
# only register their own task factories, so they silently skip tasks belonging
# to the other domain. This file registers all task factories in one namespace
# so that create_org_user_classes() can resolve every task an org references.

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
from infrastructure.configurable_user import _load_locust_config
from tasks import event_tasks, read_api_tasks

# Register all task factories from both task modules into this module's namespace.
# load_object() resolves factory names against the locustfile's globals, so every
# factory referenced in a test YAML must be importable here.
for _mod in (event_tasks, read_api_tasks):
    for _name in dir(_mod):
        if _name.endswith("_task_factory"):
            globals()[_name] = getattr(_mod, _name)

# --- Load user classes ---
# In multi-org mode, load both test YAMLs and create per-org user classes from each.
# In single-org mode, fall back to creating user classes from whatever the YAMLs define.

_ingest_config = full_path_from_module_relative_path(__file__, "config/simple.test.yml")
_read_api_config = full_path_from_module_relative_path(
    __file__, "config/read_api.test.yml"
)

_ingest_classes = create_org_user_classes(_ingest_config, __name__)
_read_api_classes = create_org_user_classes(_read_api_config, __name__)

if _ingest_classes or _read_api_classes:
    for _cls in (_ingest_classes or []) + (_read_api_classes or []):
        globals()[_cls.__name__] = _cls
else:
    for _config_path in (_ingest_config, _read_api_config):
        for _user_name in _load_locust_config(_config_path):
            _cls = create_user_class(_user_name, _config_path, __name__)
            if _cls is not None:
                globals()[_user_name] = _cls
