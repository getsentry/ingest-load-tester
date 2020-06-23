#!/usr/bin/env bash
set -eux

# Enable job control
set -m

# Allow more open files
ulimit -n 100000

pkill -f toxiproxy-server || true
sleep 0.5

# Start the server
toxiproxy-server -config config.json &
sleep 1

LAT=${LAT:-500}

UP_LAT=$LAT
DOWN_LAT=$LAT

# Add the toxics
toxiproxy-cli toxic add --type latency -n up -a latency=$UP_LAT --upstream relay
toxiproxy-cli toxic add --type latency -n down -a latency=$DOWN_LAT --downstream relay

jobs
fg %1
