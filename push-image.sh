#!/usr/bin/env bash
set -eux

if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Dirty working directory, exiting.'
  exit 1
fi

IMAGE="europe-west3-docker.pkg.dev/sentry-st-testing/main/ingest-load-tester"
TAG=$(git rev-parse HEAD)

docker build -t "${IMAGE}:${TAG}" .

docker push "${IMAGE}:${TAG}"
