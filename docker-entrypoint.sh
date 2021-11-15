#!/usr/bin/env bash
set -eux

if [[ "${1:-}" == "bash" ]]; then
  exec /bin/bash
fi

export UWSGI_LISTEN=${UWSGI_LISTEN:-4096}
export UWSGI_PROCESSES=${UWSGI_PROCESSES:-16}

# Running only fake-sentry for now
exec python -m fake_sentry.fake_sentry
