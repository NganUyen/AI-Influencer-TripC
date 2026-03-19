#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <git-ref>"
    exit 1
fi

TARGET_REF="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Refusing to rollback with a dirty worktree."
    exit 1
fi

git fetch --tags origin
git checkout "${TARGET_REF}"
"${SCRIPT_DIR}/deploy-production.sh"
