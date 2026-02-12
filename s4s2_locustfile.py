import resource

# Raise the max number of open files
current_limits = resource.getrlimit(resource.RLIMIT_NOFILE)
new_limit = min(current_limits[1], 12000)
resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, new_limit))

###
from infrastructure import full_path_from_module_relative_path, create_user_class
from tasks import event_tasks


# do NOT just import the functions in the module (you will get a warning that the function is not used,
# you will remove it and then will get a runtime error)
random_event_task_factory = event_tasks.random_event_task_factory
random_envelope_event_task_factory = event_tasks.random_envelope_event_task_factory
file_event_task_factory = event_tasks.file_event_task_factory
file_envelope_event_task_factory = event_tasks.file_envelope_event_task_factory
session_event_task_factory = event_tasks.session_event_task_factory
transaction_event_task_factory = event_tasks.transaction_event_task_factory
log_envelope_task_factory = event_tasks.log_envelope_task_factory
profile_chunk_envelope_task_factory = event_tasks.profile_chunk_envelope_task_factory

# Load config and add config to factories.
_config_path = full_path_from_module_relative_path(__file__, "config/s4s2.test.yml")

# TransactionEvents = create_user_class("TransactionEvents", _config_path, __name__)
# SimpleLoadTest = create_user_class("SimpleLoadTest", _config_path, __name__)
RandomEvents = create_user_class("RandomEvents", _config_path, __name__)
LogEvents = create_user_class("LogEvents", _config_path, __name__)
ProfileChunkEvents = create_user_class("ProfileChunkEvents", _config_path, __name__)
