import socket
import threading
import time
import os

from contextlib import contextmanager
from typing import Optional

import influxdb_client

from .util import memoize, get_value_with_env_override
from influxdb_client.client.write_api import PointSettings

from infrastructure.config import metrics_enabled, get_metrics_config


@contextmanager
def timed_operation(measurement: str, **tags: str):
    """
    Anything run inside this contextmanager will be timed and a
    metric will be sent (if metrics are enabled)

    Usage:

    from infrastructure import timed_operation

    with timed_operation("my_metric", some_tag="hello", importance="High"):
        function_i_want_to_time()
        another_timed_function()
    # anything below is not timed
    untimed_function()


    NOTE: import this from module level (from infrastructure) in order
    to facilitate exchanging this implementation with a different one (e.g. statsd)
    """
    start = None
    enabled = metrics_enabled()
    if enabled:
        start = int(time.monotonic() * 1000)
    try:
        yield
    finally:
        if enabled:
            end = int(time.monotonic() * 1000)
            duration_ms = end - start
            _log_timed_metric(measurement, duration_ms, **tags)


@memoize
def _get_influxdb_client() -> Optional[influxdb_client.InfluxDBClient]:
    metrics_config = get_metrics_config()
    influxdb_config = metrics_config.get("influxdb")

    if influxdb_config is None:
        return None

    url = get_value_with_env_override(influxdb_config, "url")
    token = get_value_with_env_override(influxdb_config, "token")
    org = get_value_with_env_override(influxdb_config, "url")

    if url is None or token is None or org is None:
        return None

    return influxdb_client.InfluxDBClient(
        url=url,
        token=token,
        org=org
    )


@memoize
def _get_point_settings() -> PointSettings:
    point_settings = PointSettings()
    point_settings.add_default_tag("host_name", socket.gethostname())
    return point_settings


@memoize
def _get_org_bucket() -> (str, str):
    metrics = get_metrics_config()
    influxdb_config = metrics.get("influxdb", {})
    org = influxdb_config.get("org")
    bucket = influxdb_config.get("bucket")
    return org, bucket


def _time_ns() -> int:
    return int(time.time() * 1_000_000_000)


@memoize
def get_run_id():
    return os.getenv("TEST_RUN_ID", default="UNKNOWN")


def _log_timed_metric(measurement: str, duration_ms, **tags: str):
    client = _get_influxdb_client()
    if client:
        with client.write_api(point_settings=_get_point_settings()) as write_api:
            p = influxdb_client.Point(measurement)
            for k, v in tags.items():
                p = p.tag(k, v)
            p = p.field("duration", duration_ms)
            p.tag("thread_id", threading.get_ident())
            p.tag("run", get_run_id())
            p.time(_time_ns(), write_precision="ns")
            org_name, bucket_name = _get_org_bucket()
            write_api.write(bucket_name, org_name, p)
