import random
import uuid
from enum import Enum
from typing import List, Any, Sequence, Callable


class SpanStatus(Enum):
    ok = "ok"
    deadline_exceeded = "deadline_exceeded"
    unauthenticated = "unauthenticated"
    permission_denied = "permission_denied"
    not_found = "not_found"
    resource_exhausted = "resource_exhausted"
    invalid_argument = "invalid_argument"
    unimplemented = "unimplemented"
    unavailable = "unavailable"
    internal_error = "internal_error"
    failure = "failure"
    unknown = "unknown"
    cancelled = "cancelled"
    already_exists = "already_exists"
    failed_precondition = "failed_precondition"
    aborted = "aborted"
    out_of_range = "out_of_range"
    data_loss = "data_loss"


def span_status_generator():
    if random.randint(1, 100) < 100:
        return lambda: SpanStatus.ok.value  # mostly return ok

    # return an error once every 101 spans
    values = list(map(lambda x: x.value, SpanStatus))
    return lambda: random.choice(values)


_new_span_status = span_status_generator()


def measurements_generator(measurements: Sequence[str]):
    pass

    def inner():
        return {
            measurement: {"value": random.random() * 10000}
            for measurement in measurements
        }

    return inner


def span_id_generator():
    return lambda: uuid.uuid4().hex[:16]


_new_span_id = span_id_generator()


def span_op_generator(operations: Sequence[str]):
    values = list(operations)

    return lambda: random.choice(values)


def create_spans(
    min_spans: int,
    max_spans: int,
    transaction_id: str,
    trace_id: str,
    transaction_start: float,
    timestamp: float,
    operations_generator: Callable[[], str],
) -> List[Any]:
    num_spans = random.randint(min_spans, max_spans)

    ret_val = []
    num_children_left = random.randint(1, 3)
    current_node_idx = 0
    time_slice = (timestamp - transaction_start) / num_children_left
    parent_start = transaction_start
    parent_id = transaction_id
    while len(ret_val) < num_spans:
        if num_children_left > 0:
            start_timestamp = parent_start + (num_children_left - 1) * time_slice
            timestamp = parent_start + num_children_left * time_slice
            operation = operations_generator()
            ret_val.append(
                _create_span(
                    parent_id=parent_id,
                    trace_id=trace_id,
                    timestamp=timestamp,
                    start_timestamp=start_timestamp,
                    operation=operation,
                )
            )
            num_children_left -= 1
        else:
            # decide how many sub spans
            num_children_left = random.randint(1, 3)
            # divide the time for each sub-span equally
            current_node = ret_val[current_node_idx]
            parent_end = current_node["timestamp"]
            parent_start = current_node["start_timestamp"]
            parent_id = current_node["span_id"]
            time_slice = (parent_end - parent_start) / num_children_left
            current_node_idx += 1  # go to next span and prepare to add sub-spans to it
    return ret_val


def _create_span(
    parent_id: str,
    trace_id: str,
    start_timestamp: float,
    timestamp: float,
    operation: str,
):
    return {
        "timestamp": timestamp,
        "start_timestamp": start_timestamp,
        "trace_id": trace_id,
        "parent_span_id": parent_id,
        "span_id": _new_span_id(),
        "op": operation,
        "status": _new_span_status(),
    }
