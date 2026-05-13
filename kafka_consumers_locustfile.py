"""
Load test for kafka consumer
"""
from locust import User

from infrastructure import (
    full_path_from_module_relative_path,
    create_org_user_classes,
)
from infrastructure.kafka import KafkaProducerMixin, Outcome
from tasks.kafka_tasks import (
    kafka_outcome_task,
    kafka_random_outcome_task,
    kafka_configurable_outcome_task_factory,
    random_kafka_event_task_factory,
)

accepted_outcome = kafka_outcome_task(Outcome.ACCEPTED)
rate_limited_outcome = kafka_outcome_task(Outcome.RATE_LIMITED)
random_outcome = kafka_random_outcome_task
kafka_configurable_outcome_factory = kafka_configurable_outcome_task_factory
random_kafka_event_task_factory = random_kafka_event_task_factory

_config_path = full_path_from_module_relative_path(
    __file__, "config/kafka_consumers.test.yml"
)


# Creates per-org user classes from kafka_consumers.test.yml, one per
# (org, task) pair. Org user_tasks that don't match an entry in
# kafka_consumers.test.yml (e.g. HTTP-only tasks) are silently skipped
def _load_user_classes():
    return {
        cls.__name__: cls
        for cls in create_org_user_classes(
            _config_path, __name__, base_classes=(User, KafkaProducerMixin)
        )
    }


globals().update(_load_user_classes())
