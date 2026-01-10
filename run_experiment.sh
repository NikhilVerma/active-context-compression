#!/bin/bash
set -e

# Load .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set Docker host
export DOCKER_HOST=unix:///Users/nikhilverma/.orbstack/run/docker.sock

# Run experiment
uv run python scripts/run_final_experiment.py
