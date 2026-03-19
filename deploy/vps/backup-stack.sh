#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${1:-${REPO_ROOT}/backups/${TIMESTAMP}}"

mkdir -p "${BACKUP_ROOT}"

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    pg_dump -U postgres ai_influencer > "${BACKUP_ROOT}/ai_influencer.sql"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    pg_dump -U postgres postiz > "${BACKUP_ROOT}/postiz.sql"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    pg_dump -U postgres growchief > "${BACKUP_ROOT}/growchief.sql"
docker compose -f "${COMPOSE_FILE}" exec -T temporal_worker \
    tar -C /app -czf - browser_profiles > "${BACKUP_ROOT}/browser_profiles.tar.gz"

if [[ -n "${PROJECT_ENV_FILE:-}" && -f "${PROJECT_ENV_FILE}" ]]; then
    cp "${PROJECT_ENV_FILE}" "${BACKUP_ROOT}/env.snapshot"
fi

echo "Backup completed at ${BACKUP_ROOT}"
