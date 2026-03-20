#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
MIGRATION_FILE="${REPO_ROOT}/Project/supabase/migrations/20260320_chatgpt_connector_links.sql"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"

export PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ ! -f "${MIGRATION_FILE}" ]]; then
    echo "Missing migration file: ${MIGRATION_FILE}"
    exit 1
fi

if [[ -f "${PROJECT_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${PROJECT_ENV_FILE}"
    set +a
fi

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
    psql -U postgres -d ai_influencer < "${MIGRATION_FILE}"

echo "Applied connector link migration to ai_influencer."
