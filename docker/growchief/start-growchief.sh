#!/bin/sh

set -eu

cd /usr/src/app

pm2 delete all >/dev/null 2>&1 || true
pnpm run prisma-db-push

pm2 start pnpm --name backend --cwd /usr/src/app/apps/backend -- start-pm2
pm2 start pnpm --name orchestrator --cwd /usr/src/app/apps/orchestrator -- start-pm2

exec pm2 logs --raw
