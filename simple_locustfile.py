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
random_envelope_transaction_task_factory = event_tasks.random_envelope_transaction_task_factory
file_event_task_factory = event_tasks.file_event_task_factory
file_envelope_event_task_factory = event_tasks.file_envelope_event_task_factory
session_event_task_factory = event_tasks.session_event_task_factory

_config_path = full_path_from_module_relative_path(__file__, "config/simple.test.yml")
SimpleLoadTest = create_user_class("SimpleLoadTest", _config_path, __name__)
RandomEvents = create_user_class("RandomEvents", _config_path, __name__)
