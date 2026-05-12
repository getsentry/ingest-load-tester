# ingest-load-tester

The project contains a load tester based on Locust (see https://locust.io/).

## Component: Load tester

### Installation

In order to create a virtual env and install all the necessary dependencies just call once

    make config

On MacOS you will _probably_ need additional dependencies that can be installed with

    make setup-brew

WARNING: the command will run `brew` under the hood, that might have unforeseen consequences for your
local enviroment.

### Configuration

The load tester can be run both against the Fake Sentry Server and against a full Relay-Sentry chain.

Configuration is split across two files:

- **`locust.config.yml`** — Defines relay/kafka settings and organization profiles for HTTP
  load tests. Organizations are required for HTTP tests (ingest and read API) but do not apply
  to kafka consumer tests. Each organization specifies a `slug`, `api_host`,
  `auth_token_env_var` (the name of an environment variable containing a Sentry auth token),
  `projects` (by slug — IDs and keys are resolved from the API at startup), and `user_tasks`
  (each with a `name` and `weight`).
- **`http.test.yml`** / **`kafka_consumers.test.yml`** — Define the user classes and their task
  parameters (query params, wait times, etc.). Weights for HTTP tasks are controlled by the
  org profile in `locust.config.yml`, not in the test YAML.

Under the `relay` key in `locust.config.yml` one configures the upstream which is either the url of the
FakeSentry or the url of a running `relay` server.

Under the `kafka` key one configures the address of the broker and the names of the ingest and outcome
topics (which normally should be left to their default values).

### Running

In order to load test you need to invoke locust and pass it the locust file that needs to be executed.
Presuming that you are in the load-tests directory you can run:

    make TEST=http load-test
    make TEST=kafka_consumers load-test

These tests will run with the configuration files `config/http.test.yml` and `config/kafka_consumers.test.yml` respectively.

Which will ensure that the virtual environment is installed and set up and will call:
`.venv/bin/locust -f http_locustfile.py`
or
`.venv/bin/locust -f kafka_consumers_locustfile.py`

You can run other locust files directly just by setting up the venv using `make setup-venv` and calling:

    .venv/bin/locust -f <MY-LOCUST-FILE>

After starting a load test as described above locust will start a control web server from which
you can start various load test sessions. Just go with a browser to http://localhost.8089

You can also start a session without a web server by passing the `--no-web` flag, like in the
example below (that starts 4 users, with a spawn rate of 2 per second and runs for 20 seconds).

    .venv/bin/locust -f kafka_consumers_locustfile.py --headless -u 4 -r 2 --run-time 20s --stop-timeout 10

Please consult the locust documentation for details: https://docs.locust.io/en/1.4.3/running-locust-without-web-ui.html

Once you have your tests working correctly locally, you can deploy a load
generator using the provided Kubernetes resource examples. See [the k8s readme](./k8s/README.md).


### Test Configuration

Locust uses a Python file as a load testing entrypoint.

`ingest-load-tester` uses Locust internally and adds the facility to configure tests by using yaml files. Under the hood `ingest-load-tester`
creates locust tests classes that are derived from `ConfigurableUser` class which in turn is derived from the locust `UserClass`.

The `ConfigurableUser` class adds functionality that allows the tests to be configured from a yaml file.

Two locust files are provided ([http_locustfile.py](https://github.com/getsentry/ingest-load-tester/blob/master/http_locustfile.py) for HTTP-based ingest and read API tests, and [kafka_consumers_locustfile.py](https://github.com/getsentry/ingest-load-tester/blob/master/kafka_consumers_locustfile.py) for Kafka consumer tests). The files have the following structure:
* import all the task factories that you intend ot use in your user classes in the file
* define the user classes
* in the user class configuration use one or more of the imported task factories to define tests.

The tests are structured on two levels, at the top level there are the ConfigurableUser derived classes
and each class contains one or more task factories. A task factory is used to generate requests.

At both levels there is a configurable weight parameter. The weights are relative to the other weights at the
same level. An example would illustrate what happens.

Presume that in your Locust file you have defined 2 test classes: `Purchase` and `Browse`. In
`Purchase` you have two tasks `Buy` and `CancelOrder` and in `Browse` you have another
two tasks `SearchItem` , `ItemDetail`.
If your configuration file looks like this:

```yaml

Purchase:
  weight: 1
  tasks:
    Buy:
      weight: 5
    CancelRequest:
      weight: 1

Browse:
  weight: 4
  tasks:
    SearchItem:
      weight: 1
    ItemDetail:
      weight: 9
```

Then locust will use the Browse user class four times out of five and the Purchase class one time out of five to create requests.

For each time locust will use the `Purchase` class it will use the `Buy` task 5 times more often then the `CancelRequest` task.

For the `Browse` class it will use the `ItemDetail` task 9 times more often than the `SearchItem` task.

Each time a task is called it will produce one request.

# Available Tasks

The following describes the available tasks, it doesn't try to comprehensively describe all
configurable attributes, it just gives an idea of what can be configured.

## Kafka

### kafka outcome
There are a few way to generate outcomes ( fixed outcomes, random outcomes, outcomes generated with
relative frequencies).

### kafka events
Uses the same event generator as the envelope event generators but sends it to kafka


## Envelope

### Session generator

Envelope based generator for sessions.

The following parameters can be configured:
* number of releases
* number of environments
* started time delta range
* duration time delta range
* number of users
* relative weights between the following session outcomes:
  * ok
  * existed
  * errored
  * crashed
  * abnormal termination

### Event generator

Events can be generated either by using a file (obsolete) or using the `RandomEventTask`
Generates events with a highly configurable set of parameters.

It supports configurations for:

* event groups
* number of users
* number of breadcrumbs
* javascript stack traces
* releases
* loggers
* transaction
* contexts

### Transaction generator

Envelope based generator for Transactions.

The following parameters can be configured:
* number releases
* number users
* number spans
* transaction duration range
* number of breadcrumbs
* various breadcrumb attributes
* measurements
* operations

### Span generator

Envelope based generator for spans using the [span v2 protocol](https://develop.sentry.dev/sdk/telemetry/spans/span-protocol/).
Each envelope contains one segment span and zero or more child spans, all sharing a single `trace_id`.

The following parameters can be configured:
* `min_items` / `max_items` — number of spans per envelope (1–1000)
* `min_duration_ms` / `max_duration_ms` — duration range for the segment span in milliseconds
* `min_attributes` / `max_attributes` — number of extra attributes per span
* `release` — optional release string added as `sentry.release` attribute
* `environment` — optional environment string added as `sentry.environment` attribute
* `operations` — list of operation names used for `sentry.op` (e.g. `http`, `db`, `browser`, `resource`)

### Log generator

Envelope based generator for Log events

The following parameters can be configured:

* min_items: Minimum number of log items per envelope (default: 1)
* max_items: Maximum number of log items per envelope (default: 100)
* min_message_bytes: Minimum size of log message body in bytes (default: 500)
* max_message_bytes: Maximum size of log message body in bytes (default: 512000)
* min_attributes: Minimum number of custom attributes per log item (default: 5)
* max_attributes: Maximum number of custom attributes per log item (default: 100)
* release: Release version string (optional)

Each log item includes a trace_id, span_id, level (info/warn/error), timestamp, body, and custom attributes.

### Profile chunk generator

Envelope based generator for Profiling data (Continuous Profiling chunks).

The following parameters can be configured:

* min_sample_count: Minimum number of samples per profile chunk (default: 5)
* max_sample_count: Maximum number of samples per profile chunk (default: 10)
* min_frame_count: Minimum number of stack frames (default: 10)
* max_frame_count: Maximum number of stack frames (default: 30)
* release: Release version string (default: "1.0.1")
* environment: Environment name (default: "dev")

Each profile chunk contains samples, stacks, and frames representing profiling data captured during execution.

### Replay generator

Envelope based generator for Replay events (Session Replay).

The following parameters can be configured:
* min_segments: Minimum number of replay_recording segments per replay_event (default: 1)
* max_segments: Maximum number of replay_recording segments per replay_event (default: 5)
* replay_type: Either "session" for full session recording or "buffer" for error replays (default: "session")
* release: Release version string (optional)
* environment: Environment name (optional)
* compress_recordings: Whether to gzip-compress the recording data (default: true)

Each replay_event is accompanied by the configured number of replay_recording segments, which contain
synthetic RRWeb recording data (mouse movements, clicks, scrolls, etc.).

## Read API

Load tests for Sentry's highest-traffic read API endpoints. Unlike the envelope/kafka tasks above which
test the ingest (write) path, these tasks issue authenticated GET requests against Sentry's REST API.

Auth tokens and org slugs are configured via organization profiles in `locust.config.yml`
(`auth_token_env_var` names the env var to read).

| Task | Endpoint | Description | Key Config |
|---|---|---|---|
| Organization Group Index | `GET /api/0/organizations/{org}/issues/` | Issues list — highest-volume read endpoint | stats_periods, limits, sort_options, queries |
| Organization Events | `GET /api/0/organizations/{org}/events/` | Discover events query with heavy Snuba fan-out | field_sets, datasets, per_page_values, sort_by |
| Group Details | `GET /api/0/organizations/{org}/issues/{id}/` | Issue detail with optional latest-event sub-path; pre-fetches real issue IDs at startup | fetch_limit, detail_weight, latest_event_weight |
| Organization Events Stats | `GET /api/0/organizations/{org}/events-stats/` | Time-series charting with expensive Snuba aggregations | y_axes, intervals, datasets |
| Group Event Details | `GET /api/0/organizations/{org}/issues/{id}/events/{event_id}/` | Issue event detail view; pre-fetches issue IDs, uses latest/oldest/recommended | fetch_limit, event_id_types |
| Organization Tags | `GET /api/0/organizations/{org}/tags/` | Filter dropdown tags — called on nearly every page | stats_periods, datasets |
| Group Events | `GET /api/0/organizations/{org}/issues/{id}/events/` | Issue events list — 2nd highest latency endpoint; pre-fetches issue IDs | fetch_limit, full_options, per_page_values |
| Organization Releases | `GET /api/0/organizations/{org}/releases/` | Release listing with health stats | per_page_values, sort_options, health_stat_options |
| Project Group Index | `GET /api/0/projects/{org}/{project_slug}/issues/` | Project-scoped issue list — same Snuba search path | limits, sort_options |
| Organization Group Index Stats | `GET /api/0/organizations/{org}/issues-stats/` | Companion to issue list — fetches sparkline stats in batches | fetch_limit, batch_size |

All tasks also receive org_slug, project_ids, and project_slugs from the organization profile.
