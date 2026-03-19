#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"

export PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ ! -f "${PROJECT_ENV_FILE}" ]]; then
    echo "Missing production env file: ${PROJECT_ENV_FILE}"
    echo "Copy ${REPO_ROOT}/Project/.env.example to Project/.env.production and fill in real secrets first."
    exit 1
fi

echo "Using env file: ${PROJECT_ENV_FILE}"
docker compose -f "${COMPOSE_FILE}" up -d --build
docker compose -f "${COMPOSE_FILE}" ps

echo
echo "If nginx has already been reloaded, run ${SCRIPT_DIR}/healthcheck.sh next."
