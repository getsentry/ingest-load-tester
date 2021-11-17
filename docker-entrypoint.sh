#!/usr/bin/env bash
set -eux

COMMAND="${1:-}"
export LOCUST_FILE=${LOCUST_FILE:-simple_locustfile.py}

if [[ "$COMMAND" == "bash" ]]; then
  exec /bin/bash
elif [[ "$COMMAND" == "run-fake-sentry" ]]; then
  export UWSGI_LISTEN=${UWSGI_LISTEN:-1024}
  export UWSGI_PROCESSES=${UWSGI_PROCESSES:-8}
  echo "Starting fake-sentry..."
  exec python -m fake_sentry.fake_sentry
elif [[ "$COMMAND" == "run-master" ]]; then
  echo "Starting locust-master..."
  exec locust -f "${LOCUST_FILE}" --master
elif [[ "$COMMAND" == "run-worker" ]]; then
  echo "Starting locust-worker..."
  export MASTER_HOST=${MASTER_HOST:-127.0.0.1}
  exec locust -f "${LOCUST_FILE}" --master-host "${MASTER_HOST}" --worker
else
  echo "Invalid component. What do you want to run?"
  exit 1
fi
