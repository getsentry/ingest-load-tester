#!/usr/bin/env bash
set -eux

if [[ "${1:-}" == "bash" ]]; then
  exec /bin/bash
fi

export UWSGI_LISTEN=${UWSGI_LISTEN:-1024}
export UWSGI_PROCESSES=${UWSGI_PROCESSES:-8}
export UWSGI_SOCKET=${UWSGI_SOCKET:-'0.0.0.0:8000'}

# Running only fake-sentry for now
exec python -m fake_sentry.fake_sentry
