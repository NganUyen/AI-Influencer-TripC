#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "apply-chatgpt-connector-migration.sh now applies all post-initial database migrations."
"${SCRIPT_DIR}/apply-db-migrations.sh"
