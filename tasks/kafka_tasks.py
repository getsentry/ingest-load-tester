"""
Tasks and task helpers to be used to generate kafka events and outcomes
"""
import time

from infrastructure.configurable_user import get_project_info
from infrastructure.generators.event import base_event_generator
from infrastructure.kafka import Outcome, kafka_send_outcome, kafka_send_event
import random

from infrastructure.util import get_uuid


def kafka_outcome_task(outcome: Outcome):
    """
    A task generator that creates outcomes of a single (specified) type
    """

    def task(user):
        _kafka_send_outcome(user, outcome)

    return task


_id_to_outcome = {outcome.value: outcome for outcome in Outcome}


def kafka_random_outcome_task(user):
    """
    A task that creates random outcomes
    """
    outcome = _id_to_outcome[random.randint(0, 4)]
    _kafka_send_outcome(user, outcome)


def kafka_configurable_outcome_task_factory(task_params):
    """
    A task factory that can be configured from the locust yaml file.

    IMPORTANT NOTE: in order to function as intended the yaml task definition using this
    factory needs too have at least one parameter (that is not the optional weight parameter)

    Example:

    tasks:
        do_stuff_task:  # a simple task with no parameters
            weight: 1
        kafka_configurable_outcome_task:
            accepted: 1
            filtered: 1

    """
    outcome_names = {outcome.name.lower(): outcome for outcome in Outcome}
    frequencies = []
    total_freq = 0
    for name, val in task_params.items():
        if name in outcome_names and val != 0:
            total_freq += val
            frequencies.append([outcome_names[name], total_freq])
    if total_freq == 0:
        ValueError("kafka_configurable_outcome_task has no configured outcomes")

    def task(user):
        outcome_idx = random.randint(1, total_freq)
        for outcome, acc_freq in frequencies:
            if acc_freq >= outcome_idx:
                break
        else:
            raise ValueError(
                "kafka_configurable_outcome_task bug, invalid math, we should never get here"
            )
        _kafka_send_outcome(user, outcome)

    return task


def random_kafka_event_task_factory(task_params=None):
    if task_params is None:
        task_params = {}

    event_generator = base_event_generator(**task_params)

    def inner(user):
        event = event_generator()
        send_outcome = task_params.get("send_outcome", True)
        return _kafka_send_event(user, event, send_outcome)

    return inner


def _kafka_send_outcome(user, outcome: Outcome):
    project_info = get_project_info(user)
    event_id = get_uuid()
    kafka_send_outcome(
        user, project_info.id, outcome, event_id, reason=outcome.reason()
    )


def _kafka_send_event(user, event, send_outcome=True):
    project_info = get_project_info(user)
    event_id = get_uuid()
    event["event_id"] = event_id

    # set required attributes for processing in a central place
    event["project"] = project_info.id
    event["timestamp"] = time.time()

    kafka_send_event(user, event, project_info.id)

    if send_outcome:
        kafka_send_outcome(user, project_info.id, Outcome.ACCEPTED, event_id)
