"""
Tests for the event task factories in `tasks.event_tasks`.

Currently focused on `trace_metric_envelope_task_factory`, whose payload must
conform to Relay's `trace_metric` envelope item spec
(https://develop.sentry.dev/sdk/telemetry/metrics/) or ingestion rejects it.
"""
import io
import time
from unittest.mock import MagicMock, patch

import pytest

import tasks.event_tasks as et

# Per the trace_metric envelope item spec.
REQUIRED_FIELDS = {
    "timestamp",
    "trace_id",
    "span_id",
    "name",
    "type",
    "value",
    "attributes",
}
VALID_TYPES = {"counter", "gauge", "distribution"}
TRACE_METRIC_CONTENT_TYPE = "application/vnd.sentry.items.trace-metric+json"


def _run_factory(task_params, runs=1):
    """
    Build the factory and invoke its inner() `runs` times with a fake user,
    returning the list of envelopes handed to send_envelope.
    """
    # _convert_params mutates the dict it's given, so pass a fresh copy.
    inner = et.trace_metric_envelope_task_factory(
        dict(task_params) if task_params else task_params
    )

    project_info = MagicMock()
    project_info.id = 42
    project_info.key = "deadbeefdeadbeefdeadbeefdeadbeef"

    captured = []

    def capture(_client, _pid, _key, envelope):
        captured.append(envelope)

    with patch.object(et, "send_envelope", side_effect=capture), patch.object(
        et, "get_project_info", return_value=project_info
    ):
        user = MagicMock()
        for _ in range(runs):
            inner(user)

    return captured


def _single_item(envelope):
    items = list(envelope.items)
    assert len(items) == 1
    return items[0]


def _metrics(envelope):
    return _single_item(envelope).payload.json["items"]


class TestTraceMetricEnvelopeShape:
    def test_factory_is_relay_hosted(self):
        # http_locustfile auto-registers any *_task_factory; relay tasks must
        # declare relay_host so the user class points at the right endpoint.
        assert et.trace_metric_envelope_task_factory.__name__.endswith("_task_factory")
        assert et.trace_metric_envelope_task_factory.host_field == "relay_host"

    def test_single_item_with_correct_type_and_content_type(self):
        envelope = _run_factory({"min_items": 3, "max_items": 3})[0]
        item = _single_item(envelope)
        assert item.type == "trace_metric"
        assert item.headers["content_type"] == TRACE_METRIC_CONTENT_TYPE

    def test_item_count_header_matches_metric_count(self):
        for envelope in _run_factory({"min_items": 1, "max_items": 25}, runs=25):
            item = _single_item(envelope)
            assert item.headers["item_count"] == len(item.payload.json["items"])

    def test_payload_is_items_wrapper(self):
        envelope = _run_factory({"min_items": 2, "max_items": 2})[0]
        payload = _single_item(envelope).payload.json
        assert set(payload.keys()) == {"items"}
        assert isinstance(payload["items"], list)


class TestTraceMetricItemFields:
    def test_num_items_within_bounds(self):
        for envelope in _run_factory({"min_items": 2, "max_items": 6}, runs=50):
            assert 2 <= len(_metrics(envelope)) <= 6

    def test_min_equals_max_is_deterministic(self):
        for envelope in _run_factory({"min_items": 4, "max_items": 4}, runs=10):
            assert len(_metrics(envelope)) == 4

    def test_all_metrics_in_envelope_share_one_trace_id(self):
        for envelope in _run_factory({"min_items": 5, "max_items": 10}, runs=20):
            trace_ids = {m["trace_id"] for m in _metrics(envelope)}
            assert len(trace_ids) == 1

    def test_each_metric_has_required_fields(self):
        for envelope in _run_factory({"min_items": 1, "max_items": 10}, runs=20):
            for metric in _metrics(envelope):
                assert REQUIRED_FIELDS <= set(metric.keys())

    def test_metric_type_is_valid(self):
        seen = set()
        for envelope in _run_factory({"min_items": 5, "max_items": 25}, runs=40):
            for metric in _metrics(envelope):
                assert metric["type"] in VALID_TYPES
                seen.add(metric["type"])
        # over many runs we expect all three types to surface
        assert seen == VALID_TYPES

    def test_value_is_a_number(self):
        for envelope in _run_factory({"min_items": 5, "max_items": 10}, runs=20):
            for metric in _metrics(envelope):
                assert isinstance(metric["value"], (int, float))
                assert not isinstance(metric["value"], bool)

    def test_trace_and_span_id_are_hex_of_expected_length(self):
        for envelope in _run_factory({"min_items": 3, "max_items": 5}, runs=20):
            for metric in _metrics(envelope):
                assert len(metric["trace_id"]) == 32
                int(metric["trace_id"], 16)  # raises if not hex
                assert len(metric["span_id"]) == 16
                int(metric["span_id"], 16)

    def test_timestamp_is_recent_epoch_seconds(self):
        before = time.time()
        envelope = _run_factory({"min_items": 1, "max_items": 3})[0]
        after = time.time()
        for metric in _metrics(envelope):
            assert before <= metric["timestamp"] <= after

    def test_unit_when_present_is_a_string(self):
        for envelope in _run_factory({"min_items": 10, "max_items": 25}, runs=20):
            for metric in _metrics(envelope):
                if "unit" in metric:
                    assert isinstance(metric["unit"], str)


class TestTraceMetricAttributes:
    def test_attributes_are_typed_key_value_pairs(self):
        envelope = _run_factory(
            {"min_items": 5, "max_items": 5, "min_attributes": 3, "max_attributes": 8}
        )[0]
        for metric in _metrics(envelope):
            for name, attr in metric["attributes"].items():
                assert isinstance(name, str)
                assert set(attr.keys()) == {"value", "type"}
                assert attr["type"] == "string"

    def test_attribute_count_within_bounds_when_no_release_or_env(self):
        for envelope in _run_factory(
            {"min_items": 3, "max_items": 5, "min_attributes": 2, "max_attributes": 6},
            runs=30,
        ):
            for metric in _metrics(envelope):
                assert 2 <= len(metric["attributes"]) <= 6

    def test_release_and_environment_added_as_attributes(self):
        envelope = _run_factory(
            {
                "min_items": 3,
                "max_items": 3,
                "min_attributes": 1,
                "max_attributes": 2,
                "release": "web@4.1.0",
                "environment": "production",
            }
        )[0]
        for metric in _metrics(envelope):
            attrs = metric["attributes"]
            assert attrs["sentry.release"] == {"value": "web@4.1.0", "type": "string"}
            assert attrs["sentry.environment"] == {
                "value": "production",
                "type": "string",
            }

    def test_no_release_or_environment_by_default(self):
        envelope = _run_factory({"min_items": 5, "max_items": 5})[0]
        for metric in _metrics(envelope):
            assert "sentry.release" not in metric["attributes"]
            assert "sentry.environment" not in metric["attributes"]


class TestTraceMetricSerialization:
    def test_envelope_serializes_and_item_roundtrips(self):
        """
        Guards that the payload is JSON-serializable and that Relay's parser
        would see the right headers: serialize the envelope to bytes and read
        it back, asserting the item type, content type, item_count, and body.
        """
        envelope = _run_factory({"min_items": 4, "max_items": 4})[0]

        buf = io.BytesIO()
        envelope.serialize_into(buf)
        buf.seek(0)

        import json

        from sentry_sdk.envelope import Envelope

        parsed = Envelope.deserialize_from(buf)
        item = _single_item(parsed)
        assert item.type == "trace_metric"
        assert item.headers["content_type"] == TRACE_METRIC_CONTENT_TYPE
        assert item.headers["item_count"] == 4
        # after deserialization the payload is raw bytes; parse it back
        body = json.loads(item.get_bytes())
        assert len(body["items"]) == 4


class TestTraceMetricTaskParams:
    def test_defaults(self):
        assert et._trace_metric_task_params(None) == {
            "min_items": 1,
            "max_items": 25,
            "min_attributes": 3,
            "max_attributes": 20,
            "release": None,
            "environment": None,
        }

    def test_overrides_are_respected(self):
        params = et._trace_metric_task_params(
            {"max_items": 50, "release": "r1", "environment": "prod"}
        )
        assert params["max_items"] == 50
        assert params["release"] == "r1"
        assert params["environment"] == "prod"
        # untouched keys keep defaults
        assert params["min_items"] == 1
