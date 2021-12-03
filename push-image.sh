#!/usr/bin/env bash
set -eux

if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Dirty working directory, exiting.'
  exit 1
fi

IMAGE="us.gcr.io/sentryio/ingest-load-tester"
# uncomment next line to push to sentry testing repo
# IMAGE="europe-west3-docker.pkg.dev/sentry-st-testing/main/ingest-load-tester"
TAG=$(git rev-parse HEAD)

docker build -t $IMAGE:$TAG .

docker push $IMAGE:$TAG
