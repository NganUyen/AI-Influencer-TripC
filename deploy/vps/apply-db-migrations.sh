#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"
MIGRATIONS_DIR="${REPO_ROOT}/Project/supabase/migrations"

export PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ ! -d "${MIGRATIONS_DIR}" ]]; then
    echo "Missing migrations directory: ${MIGRATIONS_DIR}"
    exit 1
fi

if [[ -f "${PROJECT_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${PROJECT_ENV_FILE}"
    set +a
fi

mapfile -t migration_files < <(find "${MIGRATIONS_DIR}" -maxdepth 1 -type f -name '*.sql' | sort)

if [[ ${#migration_files[@]} -eq 0 ]]; then
    echo "No migration files found in ${MIGRATIONS_DIR}"
    exit 0
fi

for migration_file in "${migration_files[@]}"; do
    migration_name="$(basename "${migration_file}")"

    if [[ "${migration_name}" == "20260310_initial_schema.sql" ]]; then
        echo "Skipping ${migration_name}; the base schema is handled by Project/supabase/schema.sql during initial database bootstrap."
        continue
    fi

    echo "Applying ${migration_name}..."
    docker compose -f "${COMPOSE_FILE}" exec -T postgres \
        psql -v ON_ERROR_STOP=1 -U postgres -d ai_influencer < "${migration_file}"
done

echo "Applied post-initial database migrations to ai_influencer."
