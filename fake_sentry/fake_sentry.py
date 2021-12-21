import atexit
import datetime
import gzip
from infrastructure.config import locust_config
import json
import logging
import os
import resource
import time
import threading
import uuid
from queue import Queue
from yaml import load
from logging.config import dictConfig
from pprint import pformat
from sentry_sdk.envelope import Envelope

import mywsgi
from flask import Flask, request as flask_request, jsonify, abort

try:
    from yaml import CFullLoader as FullLoader
except ImportError:
    from yaml import FullLoader

from infrastructure.util import full_path_from_module_relative_path

_log = logging.getLogger(__name__)


class Sentry(object):
    _healthcheck_passed = False

    def __init__(self, server_address, dns_public_key, app):
        self.server_address = server_address
        self.app = app
        self.project_configs = {}
        self.captured_events = Queue()
        self.test_failures = []
        self.upstream = None
        self.dsn_public_key = dns_public_key
        self._metrics = {}

    @property
    def url(self):
        return "http://{}:{}".format(*self.server_address)

    def _wait(self, path):
        backoff = 0.1
        while True:
            try:
                self.get(path).raise_for_status()
                break
            except Exception:
                time.sleep(backoff)
                if backoff > 10:
                    raise
                backoff *= 2

    def wait_relay_healthcheck(self):
        if self._healthcheck_passed:
            return

        self._wait("/api/relay/healthcheck/")
        self._healthcheck_passed = True

    def __repr__(self):
        return "<{}({})>".format(self.__class__.__name__, repr(self.upstream))

    @property
    def dsn(self):
        """DSN for which you will find the events in self.captured_events"""
        # bogus, we never check the DSN
        return "http://{}@{}:{}/42".format(self.dsn_public_key, *self.server_address)

    def iter_public_keys(self):
        try:
            yield self.public_key
        except AttributeError:
            pass

        if self.upstream is not None:
            if isinstance(self.upstream, tuple):
                for upstream in self.upstream:
                    yield from upstream.iter_public_keys()
            else:
                yield from self.upstream.iter_public_keys()

    def full_project_config(self, project_key):
        project_id = _project_id_form_project_key(project_key)

        base_project_config = load_proj_config(project_key)

        ret_val = {**base_project_config,
            "publicKeys": [
                {
                    **base_project_config["publicKeys"][0],
                    "publicKey": project_key,
                    "numericId": project_id,
                }
            ],
            "projectId": project_id,
            "lastFetch": datetime.datetime.utcnow().isoformat() + "Z",
            "lastChange": datetime.datetime.utcnow().isoformat() + "Z",
        }

        return ret_val

    @property
    def internal_error_dsn(self):
        """DSN whose events make the test fail."""
        return "http://{}@{}:{}/666".format(self.dsn_public_key, *self.server_address)


def run_fake_sentry_async(config):
    """
    Creates a fake sentry server in a new thread (and starts it) and returns the thread
    :param config: the cli configuration
    :return: the thread in which the fake
    """
    t = threading.Thread(target=run_blocking_fake_sentry, args=(config,))
    t.daemon = True
    t.start()
    return t


def run_blocking_fake_sentry(config):
    """
    Runs a fake sentry server on the current thread (this is a blocking call)
    :param config: the cli configuration
    """
    host = config.get("host")
    port = config.get("port")

    if config.get("use_uwsgi", True):
        # Exec uwsgi with some default parameters.
        # Parameters can be tweaked by setting certain environment variables.
        # For example, to change the number of uwsgi workers, set UWSGI_PROCESSES=<N> (1 by default)
        mywsgi.run(
            "fake_sentry.fake_sentry:app",
            "{}:{}".format(host or "127.0.0.1", port or 8000),
            listen=os.environ.get("UWSGI_LISTEN", 1024),
            disable_logging=True,
        )
    else:
        app.run(host=host, port=port)


_metrics_stats = {
    "buckets_collected": 0,
}


def configure_app(config):
    # Raise the max number of open files
    current_limits = resource.getrlimit(resource.RLIMIT_NOFILE)
    new_limit = min(current_limits[1], 12000)
    resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, new_limit))

    log_config = config.get("log", {"version": 1})
    dictConfig(log_config)
    app = Flask(__name__)

    host = config.get("host")
    port = config.get("port")
    dns_public_key = config.get("key")
    sentry = Sentry((host, port), dns_public_key, app)

    authenticated_relays = {}

    @app.before_request
    def consume_body():
        # Consume POST body even if we don't like this request
        # to no clobber the socket and buffers
        _ = flask_request.data

    @app.route("/api/0/relays/register/challenge/", methods=["POST"])
    def get_challenge():
        relay_id = flask_request.json["relay_id"]
        public_key = flask_request.json["public_key"]
        authenticated_relays[relay_id] = public_key

        assert relay_id == flask_request.headers["x-sentry-relay-id"]
        return jsonify({"token": "123", "relay_id": relay_id})

    @app.route("/api/0/relays/register/response/", methods=["POST"])
    def check_challenge():
        relay_id = flask_request.json["relay_id"]
        assert relay_id == flask_request.headers["x-sentry-relay-id"]
        return jsonify({"relay_id": relay_id})

    @app.route("/api/0/relays/projectconfigs/", methods=["POST"])
    def get_project_config():
        assert flask_request.args.get("version") == "2"
        rv = {}
        _log.debug(f"f project configs request:\n{pformat(flask_request.json)}")
        for public_key in flask_request.json["publicKeys"]:
            app.logger.debug("getting project config for: {}".format(public_key))
            rv[public_key] = sentry.full_project_config(public_key)
            rv[public_key]["publicKeys"][0]["publicKey"] = public_key  # RaduW NOT sure why this was here
        _log.debug(f"f project configs returning:\n{pformat(rv,indent=4)}")
        return jsonify(configs=rv)

    @app.route("/api/0/relays/publickeys/", methods=["POST"])
    def public_keys():
        rv = {}
        for id in flask_request.json["relay_ids"]:
            rv[id] = authenticated_relays[id]

        return jsonify(public_keys=rv)

    @app.route("/api/<project_id>/store/", methods=["POST", "GET"])
    def store_all(project_id):
        _log.debug(f"In store: '{flask_request.full_path}'")
        return jsonify({"event_id": str(uuid.uuid4().hex)})

    @app.route("/api/<project_id>/envelope/", methods=["POST"])
    def store_envelope(project_id):
        _log.debug(f"In envelope: '{flask_request.full_path}'")
        assert (
            flask_request.headers.get("Content-Encoding", "") == "gzip"
        ), "Relay should always compress store requests"
        data = gzip.decompress(flask_request.data)
        assert (
            flask_request.headers.get("Content-Type") == "application/x-sentry-envelope"
        ), "Relay sent us non-envelope data to store"

        envelope = Envelope.deserialize(data)
        _parse_metrics(envelope)
        return jsonify({"event_id": str(uuid.uuid4().hex)})

    @app.route("/<path:u_path>", methods=["POST", "GET"])
    def catch_all(u_path):
        return (
            "<h1>Fake Sentry</h1>"
            + "<div>You have called fake-sentry on: <nbsp/>"
            + "<span style='font-family:monospace; background-color:#e8e8e8;'>{}</span></div>".format(
                u_path
            )
            + "<h3><b>Note:</b> This is probably the wrong url to call !!!<h3/>"
        )

    @app.route("/", methods=["GET"])
    def root():
        return "<h1>Fake Sentry</h1><div>This is the root url</div>"

    @app.errorhandler(Exception)
    def fail(e):
        app.logger.error("Fake sentry error generated error:\n{}".format(e))
        abort(400)

    return app


def _parse_metrics(envelope):
    for item in envelope:
        if item.type == "metric_buckets":
            content = item.payload.json
            print( content)
            _metrics_stats["buckets_collected"] += len(content)


def _summarize_metrics():
    print(_metrics_stats)


def _project_id_form_project_key(project_key: str) -> int:
    """
    Recover the project id from a fake project key.

    The project id is at the end of the string and
    is preceded by at least one non numeric char.

    >>> _project_id_form_project_key("abc1234")
    1234
    >>> _project_id_form_project_key("234")
    234
    >>> _project_id_form_project_key("")
    0
    >>> _project_id_form_project_key("")
    0
    >>> _project_id_form_project_key("abc")
    0
    >>> _project_id_form_project_key("123abc332def444")
    444
    """
    for idx, ch in enumerate(project_key[::-1]):
        if ch not in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            if idx == 0:
                return 0
            return int(project_key[-idx:])

    if len(project_key) > 0:
        return int(project_key)
    else:
        return 0


def load_proj_config(project_key):
    dir_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config", "../config/projects")

    file_name = os.path.join(dir_path, f"{project_key}.json")

    if os.path.exists(file_name):
        try:
            with open(file_name, "rt") as f:
                return json.load(f)
        except:
            pass

    default_config_name = os.path.join(dir_path, "default.json")

    with open(default_config_name, "rt") as f:
        return json.load(f)


def _get_config():
    """
    Returns the program settings located in the main directory (just above this file's directory)
    with the name config.yml
    """
    file_name = full_path_from_module_relative_path(
        __file__, "..", "config", "fake_sentry.config.yml"
    )

    try:
        with open(file_name, "r") as file:
            return load(file, Loader=FullLoader)
    except Exception as err:
        _log.error("Error while getting the configuration file:\n {}".format(err))
        raise ValueError("Invalid configuration")


config = _get_config()
app = configure_app(config)

if __name__ == "__main__":
    run_blocking_fake_sentry(config)
