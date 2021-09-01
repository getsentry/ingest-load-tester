import datetime
import logging
import os
import resource
import time
import threading
import uuid
from queue import Queue
from yaml import load
from logging.config import dictConfig

import mywsgi
from flask import Flask, request as flask_request, jsonify, abort, request

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

    def basic_project_config(self):
        return {
            "publicKeys": [
                {
                    "publicKey": self.dsn_public_key,
                    "isEnabled": True,
                    "numericId": 123,
                    "quotas": [],
                }
            ],
            "rev": "5ceaea8c919811e8ae7daae9fe877901",
            "disabled": False,
            "lastFetch": datetime.datetime.utcnow().isoformat() + "Z",
            "lastChange": datetime.datetime.utcnow().isoformat() + "Z",
            "config": {
                "allowedDomains": ["*"],
                "trustedRelays": list(self.iter_public_keys()),
                "piiConfig": {
                    "rules": {},
                    "applications": {
                        "$string": ["@email", "@mac", "@creditcard", "@userpath"],
                        "$object": ["@password"],
                    },
                },
            },
            "slug": "python",
        }

    def full_project_config(self):
        basic = self.basic_project_config()
        full = {
            "organizationId": 1,
            "config": {
                "excludeFields": [],
                "filterSettings": {},
                "scrubIpAddresses": False,
                "sensitiveFields": [],
                "scrubDefaults": True,
                "scrubData": True,
                "groupingConfig": {
                    "id": "legacy:2019-03-12",
                    "enhancements": "eJybzDhxY05qemJypZWRgaGlroGxrqHRBABbEwcC",
                },
                "blacklistedIps": ["127.43.33.22"],
                "trustedRelays": [],
            },
        }

        return {
            **basic,
            **full,
            "config": {**basic["config"], **full["config"]},
        }

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
        for public_key in flask_request.json["publicKeys"]:
            app.logger.debug("getting project config for: {}".format(public_key))
            rv[public_key] = sentry.full_project_config()
            rv[public_key]["publicKeys"][0]["publicKey"] = public_key
        return jsonify(configs=rv)

    @app.route("/api/0/relays/publickeys/", methods=["POST"])
    def public_keys():
        rv = {}
        for id in flask_request.json["relay_ids"]:
            rv[id] = authenticated_relays[id]

        return jsonify(public_keys=rv)

    @app.route("/api/<project_id>/store/", methods=["POST", "GET"])
    @app.route("/api/<project_id>/envelope/", methods=["POST"])
    def store_all(project_id):
        _log.debug(f"In store: '{request.full_path}'")
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
