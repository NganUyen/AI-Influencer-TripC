#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <backup-directory>"
    echo "Restore into a fresh or manually cleaned stack for the safest result."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
BACKUP_ROOT="$1"

for required in ai_influencer.sql postiz.sql growchief.sql browser_profiles.tar.gz; do
    if [[ ! -f "${BACKUP_ROOT}/${required}" ]]; then
        echo "Missing ${BACKUP_ROOT}/${required}"
        exit 1
    fi
done

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d ai_influencer < "${BACKUP_ROOT}/ai_influencer.sql"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d postiz < "${BACKUP_ROOT}/postiz.sql"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d growchief < "${BACKUP_ROOT}/growchief.sql"
docker compose -f "${COMPOSE_FILE}" exec -T temporal_worker \
    sh -c 'rm -rf /app/browser_profiles/* && tar -C /app -xzf -' < "${BACKUP_ROOT}/browser_profiles.tar.gz"

echo "Restore completed from ${BACKUP_ROOT}"
