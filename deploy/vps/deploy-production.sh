#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.production.yml"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"
DEFAULT_DEPLOY_BRANCH="main"
DEFAULT_REPO_NAMESPACE="ghcr.io/nganuyen"
EXTERNAL_GHCR_NAMESPACE="${GHCR_NAMESPACE:-}"
EXTERNAL_IMAGE_TAG="${IMAGE_TAG:-}"
EXTERNAL_OPENCLAW_IMAGE="${OPENCLAW_IMAGE:-}"
EXTERNAL_DOCKER_CLEANUP_AFTER_DEPLOY="${DOCKER_CLEANUP_AFTER_DEPLOY:-}"
EXTERNAL_DOCKER_CLEANUP_BEFORE_PULL="${DOCKER_CLEANUP_BEFORE_PULL:-}"
EXTERNAL_DEPLOY_BRANCH="${DEPLOY_BRANCH:-}"
EXTERNAL_SYNC_REPO_BEFORE_DEPLOY="${SYNC_REPO_BEFORE_DEPLOY:-}"
EXTERNAL_BUILD_APP_IMAGES_FROM_REPO="${BUILD_APP_IMAGES_FROM_REPO:-}"
EXTERNAL_AUTO_IMAGE_TAG_FROM_GIT="${AUTO_IMAGE_TAG_FROM_GIT:-}"

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
if [[ -n "${EXTERNAL_DOCKER_CLEANUP_BEFORE_PULL}" ]]; then
    export DOCKER_CLEANUP_BEFORE_PULL="${EXTERNAL_DOCKER_CLEANUP_BEFORE_PULL}"
fi
if [[ -n "${EXTERNAL_DEPLOY_BRANCH}" ]]; then
    export DEPLOY_BRANCH="${EXTERNAL_DEPLOY_BRANCH}"
fi
if [[ -n "${EXTERNAL_SYNC_REPO_BEFORE_DEPLOY}" ]]; then
    export SYNC_REPO_BEFORE_DEPLOY="${EXTERNAL_SYNC_REPO_BEFORE_DEPLOY}"
fi
if [[ -n "${EXTERNAL_BUILD_APP_IMAGES_FROM_REPO}" ]]; then
    export BUILD_APP_IMAGES_FROM_REPO="${EXTERNAL_BUILD_APP_IMAGES_FROM_REPO}"
fi
if [[ -n "${EXTERNAL_AUTO_IMAGE_TAG_FROM_GIT}" ]]; then
    export AUTO_IMAGE_TAG_FROM_GIT="${EXTERNAL_AUTO_IMAGE_TAG_FROM_GIT}"
fi

sync_repo_before_deploy="$(printf '%s' "${SYNC_REPO_BEFORE_DEPLOY:-0}" | tr '[:upper:]' '[:lower:]')"
build_app_images_from_repo="$(printf '%s' "${BUILD_APP_IMAGES_FROM_REPO:-0}" | tr '[:upper:]' '[:lower:]')"
auto_image_tag_from_git="$(printf '%s' "${AUTO_IMAGE_TAG_FROM_GIT:-0}" | tr '[:upper:]' '[:lower:]')"
cleanup_before_pull="$(printf '%s' "${DOCKER_CLEANUP_BEFORE_PULL:-1}" | tr '[:upper:]' '[:lower:]')"

deploy_branch="${DEPLOY_BRANCH:-${DEFAULT_DEPLOY_BRANCH}}"
ghcr_namespace="${GHCR_NAMESPACE:-${DEFAULT_REPO_NAMESPACE}}"
frontend_probe_url="http://127.0.0.1:3000"

expected_frontend_api_url="${NEXT_PUBLIC_API_URL:-${FRONTEND_PUBLIC_URL:-http://localhost:3000}}"
expected_supabase_url="${NEXT_PUBLIC_SUPABASE_URL:-${SUPABASE_URL:-}}"
expected_supabase_anon_key="${NEXT_PUBLIC_SUPABASE_ANON_KEY:-${SUPABASE_KEY:-}}"
expected_supabase_publishable_key="${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:-${SUPABASE_PUBLISHABLE_KEY:-}}"
OPENCLAW_CONFIG_DIR="${REPO_ROOT}/.docker-data/openclaw/config"
OPENCLAW_WORKSPACE_DIR="${REPO_ROOT}/.docker-data/openclaw/workspace"

cd "${REPO_ROOT}"

prepare_openclaw_volume_permissions() {
    echo "Preparing OpenClaw bind-mount permissions..."
    mkdir -p "${OPENCLAW_CONFIG_DIR}" "${OPENCLAW_WORKSPACE_DIR}"
    chown -R 1000:1000 "${OPENCLAW_CONFIG_DIR}" "${OPENCLAW_WORKSPACE_DIR}"
    chmod -R u+rwX,g+rX,o-rwx "${OPENCLAW_CONFIG_DIR}" "${OPENCLAW_WORKSPACE_DIR}"
}

maybe_cleanup_before_pull() {
    if [[ "${cleanup_before_pull}" =~ ^(1|true|yes)$ ]]; then
        echo "Running Docker cleanup before image operations..."
        "${SCRIPT_DIR}/docker-cleanup.sh"
        echo
    fi
}

if [[ "${sync_repo_before_deploy}" =~ ^(1|true|yes)$ ]]; then
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        echo "Refusing to sync branch because tracked local changes exist in ${REPO_ROOT}."
        echo "Commit/stash local changes, or set SYNC_REPO_BEFORE_DEPLOY=0 for this run."
        exit 1
    fi

    echo "Syncing repository to origin/${deploy_branch}..."
    git fetch origin --prune
    git checkout "${deploy_branch}"
    git pull --ff-only origin "${deploy_branch}"
fi

repo_commit_sha="$(git rev-parse --short=12 HEAD)"

if [[ "${auto_image_tag_from_git}" =~ ^(1|true|yes)$ ]]; then
    export IMAGE_TAG="${repo_commit_sha}"
elif [[ -z "${IMAGE_TAG:-}" ]]; then
    export IMAGE_TAG="latest"
fi

export GHCR_NAMESPACE="${ghcr_namespace}"

echo "Deploy source commit: ${repo_commit_sha}"
echo "Deploy branch: ${deploy_branch}"
echo "Image namespace: ${GHCR_NAMESPACE}"
echo "Image tag: ${IMAGE_TAG}"

echo "Using env file: ${PROJECT_ENV_FILE}"
maybe_cleanup_before_pull

if [[ "${build_app_images_from_repo}" =~ ^(1|true|yes)$ ]]; then
    echo "Building app images from repository source..."

    frontend_api_url="${NEXT_PUBLIC_API_URL:-${FRONTEND_PUBLIC_URL:-}}"
    frontend_supabase_url="${NEXT_PUBLIC_SUPABASE_URL:-${SUPABASE_URL:-}}"
    frontend_supabase_anon_key="${NEXT_PUBLIC_SUPABASE_ANON_KEY:-${SUPABASE_KEY:-}}"
    frontend_supabase_publishable_key="${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:-${SUPABASE_PUBLISHABLE_KEY:-}}"
    frontend_telegram_bot_url="${NEXT_PUBLIC_TELEGRAM_BOT_URL:-}"
    frontend_telegram_bot_username="${NEXT_PUBLIC_TELEGRAM_BOT_USERNAME:-}"
    if [[ -z "${frontend_telegram_bot_username}" && -n "${frontend_telegram_bot_url}" ]]; then
        frontend_telegram_bot_username="${frontend_telegram_bot_url##*/}"
    fi

    docker build --pull \
        -f "${REPO_ROOT}/Project/python_services/Dockerfile" \
        --target api-runtime \
        -t "${GHCR_NAMESPACE}/ai-influencer-python-api:${IMAGE_TAG}" \
        "${REPO_ROOT}/Project/python_services"

    docker build --pull \
        -f "${REPO_ROOT}/Project/python_services/Dockerfile" \
        --target worker-runtime \
        -t "${GHCR_NAMESPACE}/ai-influencer-python-worker:${IMAGE_TAG}" \
        "${REPO_ROOT}/Project/python_services"

    docker build --pull \
        -f "${REPO_ROOT}/Project/Dockerfile.frontend" \
        --target runtime \
        --build-arg NEXT_PUBLIC_API_URL="${frontend_api_url}" \
        --build-arg NEXT_PUBLIC_SUPABASE_URL="${frontend_supabase_url}" \
        --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY="${frontend_supabase_anon_key}" \
        --build-arg NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="${frontend_supabase_publishable_key}" \
        --build-arg NEXT_PUBLIC_TELEGRAM_BOT_URL="${frontend_telegram_bot_url}" \
        --build-arg NEXT_PUBLIC_TELEGRAM_BOT_USERNAME="${frontend_telegram_bot_username}" \
        -t "${GHCR_NAMESPACE}/ai-influencer-frontend:${IMAGE_TAG}" \
        "${REPO_ROOT}/Project"

    docker build --pull \
        -f "${REPO_ROOT}/docker/postiz/Dockerfile" \
        -t "${GHCR_NAMESPACE}/ai-influencer-postiz:${IMAGE_TAG}" \
        "${REPO_ROOT}"

    docker build --pull \
        -f "${REPO_ROOT}/docker/growchief/Dockerfile" \
        -t "${GHCR_NAMESPACE}/ai-influencer-growchief:${IMAGE_TAG}" \
        "${REPO_ROOT}"
    echo "Pulling infrastructure images..."
    docker compose -f "${COMPOSE_FILE}" pull \
        postgres temporal temporal-ui social-temporal-postgres social-temporal-elasticsearch social-temporal redis openclaw
else
    echo "Pulling registry-backed production images..."
    docker compose -f "${COMPOSE_FILE}" pull
fi

echo "Starting production services..."
prepare_openclaw_volume_permissions
docker compose -f "${COMPOSE_FILE}" up -d
docker compose -f "${COMPOSE_FILE}" ps

echo "Verifying frontend runtime public config..."
auth_html=""
runtime_public_config=""
for attempt in {1..30}; do
    if auth_html="$(curl -fsS "${frontend_probe_url}/auth" 2>/dev/null)"; then
        if [[ "${auth_html}" == *"/api/runtime-config"* ]]; then
            break
        fi
    fi
    sleep 2
done

[[ "${auth_html}" == *"/api/runtime-config"* ]] || {
    echo "Frontend /auth page did not include the runtime public config script." >&2
    exit 1
}

for attempt in {1..30}; do
    if runtime_public_config="$(curl -fsS "${frontend_probe_url}/api/runtime-config" 2>/dev/null)"; then
        if [[ "${runtime_public_config}" == *"NEXT_PUBLIC_API_URL\":\"${expected_frontend_api_url}"* ]]; then
            break
        fi
    fi
    sleep 2
done

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

cleanup_after_deploy="$(printf '%s' "${DOCKER_CLEANUP_AFTER_DEPLOY:-1}" | tr '[:upper:]' '[:lower:]')"
if [[ "${cleanup_after_deploy}" =~ ^(1|true|yes)$ ]]; then
    echo
    "${SCRIPT_DIR}/docker-cleanup.sh"
fi

echo
echo "If nginx has already been reloaded, run ${SCRIPT_DIR}/healthcheck.sh next."
