#!/usr/bin/env bash
set -eux

COMMAND="${1:-}"
export LOCUST_FILE=${LOCUST_FILE:-http_locustfile.py}

if [[ "$COMMAND" == "bash" ]]; then
  exec /bin/bash
elif [[ "$COMMAND" == "run-master" ]]; then
  echo "Starting locust-master..."
  exec /app/.venv/bin/locust -f "${LOCUST_FILE}" --master --web-host 0.0.0.0
elif [[ "$COMMAND" == "run-worker" ]]; then
  echo "Starting locust-worker..."
  export MASTER_HOST=${MASTER_HOST:-127.0.0.1}
  export WORKER_PROCESSES=${WORKER_PROCESSES:-1}
  exec /app/.venv/bin/locust -f "${LOCUST_FILE}" --master-host "${MASTER_HOST}" --worker --processes "${WORKER_PROCESSES}"
else
  echo "Invalid component. What do you want to run?"
  exit 1
fi
