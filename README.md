# Relay load test tools

## Load test contains tools for load testing relay.

The project contains two tools: a load tester based on Locust (see https://locust.io/) and a
fake Sentry server that contains just enough functionality to get relay working with an upstream.

## Fake Sentry Server

The FakeSentryServer runs a Flask server that responds to the security challenge messages from Relay and
is able to provide project configurations for any project (it responds with a canned project configuration)

The FakeSentryServer can be configured via the `config/fake.sentry.config.yml` file (situated in the top level directory).

To start the Fake Sentry Server run:

    make fake-sentry

`uwsgi` is used under the hood, and its parameters can be tweaked by providing environment variables.
For example, to achieve higher throughput, one can raise the number of workers and the size of listen queue:

    UWSGI_LISTEN=10000 UWSGI_PROCESSES=16 make fake-sentry

## Load tester

### Installation

In order to create a virtual env and install all the necessary dependencies just call once

    make config

### Configuration

The load tester can be run both against the Fake Sentry Server and against a full Relay-Sentry chain.

In general the load tester does not care (or see) if it is running against the Fake Sentry Server or against
the a full Relay-Sentry chain. The only difference in running against a real sentry server is that the tests
should provide real project IDs and DSNs (otherwise the real Sentry will reject the requests).

There is a flag in `locust.config.yml` that controls how the load test uses project ids.

If the flag is `use_fake_projects: true` then it expects to run against a Fake Sentry server and it will use as
many projects as it wants with ids starting at 1 and going all the way to `max_num_projects` (specified by
each individual test). For all projects it will use the same DSN key specified under `fake_projects.key` which
will be safely ignored by FakeSentry.

If the flag is `use_fake_projects: false` then the tests will use the project Ids and Keys listed under
the `projects` field in `locust.config.yml` and, of course, it will use up to the number of projects listed in
the config file.

Besides configuring how the load tests use projects `locust.config.yml` also contains configurations about the
Relay server and the kafka broker.

Under the `relay` key one configures the upstream which is either the url of the FakeSentry or the url of a running
`relay` server

Under the `kafka` key one configures the address of the broker and the names of the ingest and outcome topics (which
normally should be left to their default values).

### Running

In order to load test you need to invoke locust and pass it the locust file that needs to be executed.
Presuming that you are in the load-tests directory you can run:

    make TEST=simple load-test
    make TEST=kafka_consumers load-test

These tests will run with the configuration files `config/simple.test.yml` and `config/kafka_consumers.test.yml` respectively.

Which will ensure that the virtual environment is installed and set up and will call:
`.venv/bin/locust -f simple_locustfile.py`
or
`.venv/bin/locust -f kafka_consumers_locustfile.py`

You can run other locust files directly just by setting up the venv using `make
setup-venv` and calling:

    .venv/bin/locust -f <MY-LOCUST-FILE>

After starting a load test as described above locust will start a control web server from which
you can start various load test sessions. Just go with a browser to http://localhost.8089

You can also start a session without a web server by passing the `--no-web` flag, like in the
example below (that starts 4 users, with a spawn rate of 2 per second and runs for 20 seconds).

    .venv/bin/locust -f kafka_consumers_locustfile.py --no-web -u 4 -r 2 --run-time 20s --stop-timeout 10

Please consult the locust documentation for details: https://docs.locust.io/en/0.14.6/running-locust-without-web-ui.html

**Note:** At the moment (18.05.2020) we are using locust 0.14.6, which is not the latest version and has slightly different Python API and CLI.
