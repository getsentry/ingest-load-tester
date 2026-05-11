# Ingest-Load-Tester Kubernetes

This directory contains k8s deployments for both a master, a fleet of workers nodes, and a config map to define load test configuration.

# Usage

Before deploying these resources, be sure to update `.spec.replicas` and 
`.spec.template.spec.container.env.WORKER_PROCESSES` to ensure you have enough capacity 
to generate the desired load.

1. Define the test you want to run in `configmap.yaml`
2. Deploy the configmap, worker + master resources.
3. Iterate on the configuration and re-apply the config map
4. `rollout restart` the worker and master deployments to reload configuration.

# Building images

Images are built on each pull request and each change on `master`.
You don't need to build images to reconfigure a load test.
