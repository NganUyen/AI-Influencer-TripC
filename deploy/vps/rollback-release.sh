#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <git-ref>"
    exit 1
fi

TARGET_REF="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFAULT_ENV_FILE="${REPO_ROOT}/Project/.env.production"

export PROJECT_ENV_FILE="${PROJECT_ENV_FILE:-${DEFAULT_ENV_FILE}}"

cd "${REPO_ROOT}"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Refusing to rollback with a dirty worktree."
    exit 1
fi

git fetch --tags origin
git checkout "${TARGET_REF}"
resolved_image_tag="$(git rev-parse HEAD)"

echo "Rolling back images to tag ${resolved_image_tag}"
SYNC_REPO_BEFORE_DEPLOY=0 \
AUTO_IMAGE_TAG_FROM_GIT=0 \
BUILD_APP_IMAGES_FROM_REPO=0 \
IMAGE_TAG="${IMAGE_TAG:-${resolved_image_tag}}" \
    "${SCRIPT_DIR}/deploy-production.sh"
