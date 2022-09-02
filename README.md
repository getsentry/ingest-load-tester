# ingest-load-tester

Legacy load testing tool for Relay.

### IMPORTANT NOTE
This is our legacy load tester, new tests should preferably be devloped in  [go-load-tester](https://github.com/getsentry/go-load-tester). 

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

On MacOS you will _probably_ need additional dependencies that can be installed with

    make setup-brew

WARNING: the command will run `brew` under the hood, that might have unforeseen consequences for your
local enviroment.

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

You can run other locust files directly just by setting up the venv using `make setup-venv` and calling:

    .venv/bin/locust -f <MY-LOCUST-FILE>

After starting a load test as described above locust will start a control web server from which
you can start various load test sessions. Just go with a browser to http://localhost.8089

You can also start a session without a web server by passing the `--no-web` flag, like in the
example below (that starts 4 users, with a spawn rate of 2 per second and runs for 20 seconds).

    .venv/bin/locust -f kafka_consumers_locustfile.py --no-web -u 4 -r 2 --run-time 20s --stop-timeout 10

Please consult the locust documentation for details: https://docs.locust.io/en/1.4.3/running-locust-without-web-ui.html


### Test Configuration

Locust uses a top level file, a python file to configure the tests.

`ingest-load-tester` which uses locust adds the facility to configure tests by using yaml files. Under the hood `ingest-load-tester` 
creates locust tests classes that are derived from `ConfigurableUser` class which in turn is derived from the locust `UserClass`.

The `ConfigurableUser` class adds functionality that allows the tests to be configured from a yaml file.

Two locust files are provided ([simple_locustfile.py](https://github.com/getsentry/ingest-load-tester/blob/master/simple_locustfile.py) and [kafka_consumers_locustfile.py](https://github.com/getsentry/ingest-load-tester/blob/master/kafka_consumers_locustfile.py)) and , and others can be easily added. The files have the following structure:
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

### session generator

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

### event generator

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
    
### transaction generator

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
