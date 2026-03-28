#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"
ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

FRONTEND_URL="${FRONTEND_PUBLIC_URL:-https://ai-influencer.tripc.ai}"
BACKEND_URL="${BACKEND_PUBLIC_URL:-https://api.ai-influencer.tripc.ai}"
CONNECTOR_URL="${CHATGPT_CONNECTOR_PUBLIC_URL:-https://connector.ai-influencer.tripc.ai}"

echo "Checking docker services..."
docker compose -f "${COMPOSE_FILE}" ps

echo "Checking public endpoints..."
# The public edge in front of this VPS can negotiate HTTP/2 in a way that
# sporadically trips curl health probes even when the responses are healthy.
curl --http1.1 -fsS "${FRONTEND_URL}" > /dev/null
curl --http1.1 -fsS "${BACKEND_URL}/health" > /dev/null
curl --http1.1 -fsS "${CONNECTOR_URL}/health" > /dev/null

echo "Checking frontend runtime public config..."
runtime_public_config="$(curl -fsS http://127.0.0.1:3000/api/runtime-config)"
expected_frontend_api_url="${NEXT_PUBLIC_API_URL:-${FRONTEND_PUBLIC_URL:-http://localhost:3000}}"
expected_supabase_url="${NEXT_PUBLIC_SUPABASE_URL:-${SUPABASE_URL:-}}"
expected_supabase_anon_key="${NEXT_PUBLIC_SUPABASE_ANON_KEY:-${SUPABASE_KEY:-}}"
expected_supabase_publishable_key="${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:-${SUPABASE_PUBLISHABLE_KEY:-}}"

[[ "${runtime_public_config}" == *"NEXT_PUBLIC_API_URL\":\"${expected_frontend_api_url}"* ]] || {
    echo "Frontend runtime config is missing NEXT_PUBLIC_API_URL=${expected_frontend_api_url}" >&2
    exit 1
}

if [[ -n "${expected_supabase_url}" ]]; then
    [[ "${runtime_public_config}" == *"NEXT_PUBLIC_SUPABASE_URL\":\"${expected_supabase_url}"* ]] || {
        echo "Frontend runtime config is missing NEXT_PUBLIC_SUPABASE_URL=${expected_supabase_url}" >&2
        exit 1
    }
fi

if [[ -n "${expected_supabase_publishable_key}" ]]; then
    [[ "${runtime_public_config}" == *"NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY\":\"${expected_supabase_publishable_key}"* ]] || {
        echo "Frontend runtime config is missing NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY" >&2
        exit 1
    }
elif [[ -n "${expected_supabase_anon_key}" ]]; then
    [[ "${runtime_public_config}" == *"NEXT_PUBLIC_SUPABASE_ANON_KEY\":\"${expected_supabase_anon_key}"* ]] || {
        echo "Frontend runtime config is missing NEXT_PUBLIC_SUPABASE_ANON_KEY" >&2
        exit 1
    }
fi

echo "Checking localhost admin endpoints..."
curl -fsS http://127.0.0.1:8080 > /dev/null
curl -fsS http://127.0.0.1:8081/healthz > /dev/null
curl -fsS http://127.0.0.1:3100 > /dev/null
curl -fsS http://127.0.0.1:3200 > /dev/null

echo "Checking private provider APIs from inside the backend network..."
"${SCRIPT_DIR}/check-provider-apis.sh"

echo "Checking Telegram webhook + OpenClaw readiness..."
bash "${SCRIPT_DIR}/check-telegram-openclaw.sh"

echo "All smoke checks passed."
