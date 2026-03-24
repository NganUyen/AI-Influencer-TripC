#!/usr/bin/env bash

set -euo pipefail

wait_for_http() {
    local url="$1"
    local label="$2"
    local timeout_seconds="${3:-90}"

    URL="${url}" LABEL="${label}" TIMEOUT_SECONDS="${timeout_seconds}" node <<'NODE'
const url = process.env.URL;
const label = process.env.LABEL;
const timeoutSeconds = Number(process.env.TIMEOUT_SECONDS || "90");
const deadline = Date.now() + timeoutSeconds * 1000;

async function poll() {
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, {
        redirect: "manual",
        signal: AbortSignal.timeout(5000),
      });
      if (
        (response.status >= 200 && response.status < 400) ||
        response.status === 401
      ) {
        process.exit(0);
      }
    } catch (_error) {
      // Keep retrying until the timeout expires.
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  console.error(`${label} did not become ready at ${url}`);
  process.exit(1);
}

poll().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
NODE
}

export NODE_OPTIONS="${NODE_OPTIONS:-${POSTIZ_NODE_OPTIONS:---max-old-space-size=512}}"
export POSTIZ_BACKEND_READINESS_URL="${POSTIZ_BACKEND_READINESS_URL:-http://127.0.0.1:3000/public/v1/integrations}"
export POSTIZ_FRONTEND_READINESS_URL="${POSTIZ_FRONTEND_READINESS_URL:-http://127.0.0.1:5000/}"
export POSTIZ_STARTUP_TIMEOUT_SECONDS="${POSTIZ_STARTUP_TIMEOUT_SECONDS:-120}"

cd /app

pm2 delete all >/dev/null 2>&1 || true
nginx
pnpm run prisma-db-push

pm2 start /bin/sh --name backend --restart-delay 5000 -- -lc "cd /app/apps/backend && exec pnpm start"
wait_for_http "${POSTIZ_BACKEND_READINESS_URL}" "Postiz backend API" "${POSTIZ_STARTUP_TIMEOUT_SECONDS}"

pm2 start /bin/sh --name frontend --restart-delay 5000 -- -lc "cd /app/apps/frontend && exec pnpm start"
wait_for_http "${POSTIZ_FRONTEND_READINESS_URL}" "Postiz frontend" "${POSTIZ_STARTUP_TIMEOUT_SECONDS}"

pm2 start /bin/sh --name orchestrator --restart-delay 5000 -- -lc "cd /app/apps/orchestrator && exec pnpm start"

exec pm2 logs --raw
