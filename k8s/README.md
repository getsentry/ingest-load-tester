# Ingest-Load-Tester Kubernetes

This directory contains k8s deployments for a locust master, a fleet of worker
nodes, a ConfigMap for load-test configuration, and a Secret for API tokens.

## Prerequisites

### Create the Secret

API tokens are stored in a Kubernetes Secret. Create it **before** deploying
the other resources:

```sh
kubectl create secret generic load-tester-secrets -n load-test \
  --from-literal=sentry-auth-token='<your-sentry-auth-token>'
```

Alternatively, edit `secret.yaml` and replace the `REPLACE_ME` placeholder
values, then apply it with `kubectl apply -f secret.yaml`.

The `SENTRY_AUTH_TOKEN` env var is read by organization profiles in
`locust.config.yml` (via `auth_token_env_var`).

## Usage

Before deploying, update `worker.yaml`:
- `.spec.replicas` -- number of worker pods
- `WORKER_PROCESSES` env var -- number of locust worker processes per pod

### Sizing guidelines

Total Locust workers = `replicas` x `WORKER_PROCESSES`. Each worker process
runs one set of user classes and generates load independently.

| Setting | What it controls | Constraint |
|---|---|---|
| `WORKER_PROCESSES` | Processes per pod | Should not exceed the pod's CPU request (default: 6 CPU, 6 processes). Over-subscribing CPU causes workers to bottleneck on the load generator itself. |
| `.spec.replicas` | Number of worker pods | Scale this to increase total capacity. Each pod requests 6 CPU / 4Gi memory by default. |

**Read API tasks** (e.g. OrganizationGroupIndex, OrganizationEvents) are I/O-bound
-- workers spend most of their time waiting for responses. The default 1:1
process-to-CPU ratio is conservative; you may be able to run more processes per
CPU for read-heavy workloads.

**Ingest tasks** (e.g. TransactionEvents, RandomEvents) are more CPU-bound
-- workers spend time generating event payloads. Keep `WORKER_PROCESSES` at or
below the CPU request.

Start with a small replica count, observe throughput and CPU usage in the Locust
web UI (port 8089), and scale up `replicas` until you hit your target RPS or the
system under test saturates.

Steps:
1. Create the secret (see above)
2. Define the test configuration in `configmap.yaml`
3. Deploy all resources: `kubectl apply -f k8s/`
4. To change configuration, update and re-apply the ConfigMap, then
   `kubectl rollout restart deployment locust-master locust-worker`

## Building images

Images are built on each pull request and each change on `master`.
You don't need to build images to reconfigure a load test.
