#!/usr/bin/env bash

set -euo pipefail

builder_prune_all="$(printf '%s' "${DOCKER_BUILDER_PRUNE_ALL:-1}" | tr '[:upper:]' '[:lower:]')"

echo "Docker disk usage before cleanup:"
docker system df

echo
echo "Pruning dangling Docker images..."
docker image prune -f

echo
if [[ "${builder_prune_all}" =~ ^(1|true|yes)$ ]]; then
    echo "Pruning all unused Docker build cache..."
    docker builder prune -af
else
    echo "Pruning dangling Docker build cache..."
    docker builder prune -f
fi

echo
echo "Docker disk usage after cleanup:"
docker system df
