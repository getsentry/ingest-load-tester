# Load test development

## Overview
This document describes the infrastructure provided by the load-tests project and how to go about writing
and configuring your own load tests.

This document will not go into details about Locust, which is the program used for
load testing (https://docs.locust.io/en/stable/index.html), and assumes some basic familiarity with it.

If at any point in time you feel like there is something missing in the explanations it is likely that you
will find that information in the Locust documentation.

## Configurable Users

Load test tries to extend the infrastructure provided by locust by adding facilities to configure your load
tests via configuration files. Besides this it also contains utilities useful for testing Sentry infrastructure
(things like sending messages to http endpoints or kafaka queues).

At the center of this infrastructure is one function that can be used to create Users from yaml configuration
files:

    create_user_class(name:str, config_file_name:str, host=None, base_classes=None)

Will create a User class from the file `config_file_name`. The configuration for the User class will be
found under the key passed in the parameter `name`.

By default the base class of the class returned by `create_user_class` is `HttpUser`. If you need your class
derived from something else (it must have at least one class ultimately derived from `User`) you can pass a
tuple with the desired base classes.

The example below creates a configurable locust class derived from `User` and `KafkaProducerMixin`

```python
First = create_user_class("First", _config_path, base_classes=(User, KafkaProducerMixin))
```

A config file can contain configurations for multiple locusts.

Creating a load test will typically involve writing something like this:

```python
"""
my_load_test.py
"""
from locust import User

from infrastructure import (
    full_path_from_module_relative_path, create_user_class,
)
from infrastructure.kafka import KafkaProducerMixin


def task1(user):
    # we can use the user to implement desired functionality
    # if the user is derived from HttpUser we can use the client to send HTTP requests
    user.client.get("http://my_server/get-stuff")


def task2(user):
    # we can also use the user to get the configuration information for the current user
    user_params = user.get_params()


_config_path = full_path_from_module_relative_path(__file__, "config/MyLoadTest.yml")
LocustA = create_user_class("UserA", _config_path)
LocustB = create_user_class("UserB", _config_path)
```

The file above will create a locust file containing two user classes (`UserA` and `UserB`) that will be
configured from the file "config/MyLoadTest.yml"

The contents of the configuration file would look like this:

```yaml
users:
  UserA:
    wait_time: between(0.1, 0.2)
    num_projects: 10
    weight: 1
    tasks:
      my_load_test.task1:
        weight: 1
      my_load_test.task2:
        weight: 2
  UserB:
    wait_time: constant(0.1)
    num_projects: 10
    weight: 1
    tasks:
      - my_load_test.task1
      - my_load_test.task2
```

I the example above the first User configures the tasks by setting relative weights (in the example task 2 will
be executed twice as much as task1 by UserA).
The second User executes `task1` and `task2` with the same frequency.

The infrastructure also supports tasks that can be configured via the yaml configuration file.
In order to crate a task that receives configuration from yaml one needs to implement a task factory that will
receive the configuration information.
The example below illustrates this scenario.

```python
def task_factory1(task_params):
    def internal(user):
        pass # use the task params present in task_params

    return internal
```

`task_params` will receive the configuration dictionary for the task.
In order for the infrastructure to recognize when it deals with a task and when it deals with a task factory the
task configuration must be a dictionary configuration (like the one for `UserA` in the example above) and the
configuration dictionary must contain at least one field other than the `weight` field (which is used by normal
tasks). The example below illustrates using both tasks and task factories in a locust configuration:

```yaml
users:
  UserX:
    wait_time: between(0.1, 0.2)
    num_projects: 10
    weight: 1
    tasks:
      my_load_test.task1:
        weight: 1
      my_load_test.factory1:
        weight: 2
        some_param: some value
      my_load_test.factory2:
        xx: some value
```

In the example above, the infrastructure will assume that `my_load_test.task1` is a task function, because its
configuration only contains the `weight` field.

The infrastructure will consider both `my_load_test.factory1` and `my_load_test.factory1` task factories because
they both have parameters other than `weight`. When the infrastructure considers that it deals with a factory it
will call the factory passing it the configuration dictionary (e.g. `{"weight":2, "some_param":"some_ value"` for
`factory1` and `{"xx": "some value"}` for 'factory2'). The result from the factory should be a task function, i.e.
a `Callable[[User], Any]` .


## wait_time

A locust configuration can receive a `wait_time` function that specifies the time a locust waits between
task invocations (see Locust documentation https://docs.locust.io/en/stable/api.html#module-locust.wait_time).

The load-tests infrastructure permits configuring wait_times with the 3 build in locust functions: `between`, `constant`
and `constant_pacing` (see Locust documentation for details). The string value of the `wait_time` field will be passed
as is to a python `eval` with the local environment configured with the three functions mentioned above. So something
like `wait_time: between(0.1, 04)`  would work and would result in the task being configured with the function returned
by `locust.between(0.1, 0.4)`.
