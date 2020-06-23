#!/usr/bin/env bash
set -eu

LOCUST_FILE="${1}"
LOCUST_WORKERS="${LOCUST_WORKERS:-4}"

cleanup() {
    pkill -f 'bin/locust -f' || true
}
trap cleanup EXIT SIGINT

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $SCRIPT_DIR/..
cleanup

echo 'Starting Locust Workers...'
for i in $(seq 1 $LOCUST_WORKERS); do
    .venv/bin/locust -f ${LOCUST_FILE} --slave &
done
sleep 0.5

echo 'Starting Locust Coordinator...'
.venv/bin/locust -f ${LOCUST_FILE} --master


