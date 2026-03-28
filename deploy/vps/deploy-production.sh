#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"
EXTERNAL_GHCR_NAMESPACE="${GHCR_NAMESPACE:-}"
EXTERNAL_IMAGE_TAG="${IMAGE_TAG:-}"
EXTERNAL_OPENCLAW_IMAGE="${OPENCLAW_IMAGE:-}"
EXTERNAL_DOCKER_CLEANUP_AFTER_DEPLOY="${DOCKER_CLEANUP_AFTER_DEPLOY:-}"

export PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ ! -f "${PROJECT_ENV_FILE}" ]]; then
    echo "Missing production env file: ${PROJECT_ENV_FILE}"
    echo "Copy ${REPO_ROOT}/Project/.env.example to Project/.env.production and fill in real secrets first."
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "${PROJECT_ENV_FILE}"
set +a

if [[ -n "${EXTERNAL_GHCR_NAMESPACE}" ]]; then
    export GHCR_NAMESPACE="${EXTERNAL_GHCR_NAMESPACE}"
fi
if [[ -n "${EXTERNAL_IMAGE_TAG}" ]]; then
    export IMAGE_TAG="${EXTERNAL_IMAGE_TAG}"
fi
if [[ -n "${EXTERNAL_OPENCLAW_IMAGE}" ]]; then
    export OPENCLAW_IMAGE="${EXTERNAL_OPENCLAW_IMAGE}"
fi
if [[ -n "${EXTERNAL_DOCKER_CLEANUP_AFTER_DEPLOY}" ]]; then
    export DOCKER_CLEANUP_AFTER_DEPLOY="${EXTERNAL_DOCKER_CLEANUP_AFTER_DEPLOY}"
fi

echo "Using env file: ${PROJECT_ENV_FILE}"
echo "Pulling registry-backed production images..."
docker compose -f "${COMPOSE_FILE}" pull

echo "Starting production services..."
docker compose -f "${COMPOSE_FILE}" up -d
docker compose -f "${COMPOSE_FILE}" ps

cleanup_after_deploy="$(printf '%s' "${DOCKER_CLEANUP_AFTER_DEPLOY:-1}" | tr '[:upper:]' '[:lower:]')"
if [[ "${cleanup_after_deploy}" =~ ^(1|true|yes)$ ]]; then
    echo
    "${SCRIPT_DIR}/docker-cleanup.sh"
fi

echo
echo "If nginx has already been reloaded, run ${SCRIPT_DIR}/healthcheck.sh next."
