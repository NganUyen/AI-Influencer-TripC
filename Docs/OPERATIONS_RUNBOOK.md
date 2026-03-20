# Operations Runbook

Last verified: 2026-03-20 (Asia/Bangkok)

This runbook is the canonical internal-v1 operations guide for the current VPS deployment.

If you are starting from a completely empty VPS, read [VPS_ZERO_TO_PRODUCTION_GUIDE.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/VPS_ZERO_TO_PRODUCTION_GUIDE.md) first.
For the known baseline of the existing `ai-influencer` host, also see [VPS.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/VPS.md).

If only `ai-influencer.tripc.ai` is available and the extra hostnames are not being set up, use [SINGLE_DOMAIN_VPS_DEPLOY.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/SINGLE_DOMAIN_VPS_DEPLOY.md) instead of the multi-host topology below.

## Production Topology

Public HTTPS entrypoints:

- `https://ai-influencer.tripc.ai` -> Next.js frontend on `127.0.0.1:3000`
- `https://api.ai-influencer.tripc.ai` -> FastAPI backend on `127.0.0.1:8000`
- `https://connector.ai-influencer.tripc.ai` -> ChatGPT connector on `127.0.0.1:8010`

Private or localhost-only services:

- Temporal gRPC/UI -> `127.0.0.1:7233` / `127.0.0.1:8080`
- OpenClaw control UI -> `127.0.0.1:8081`
- Postiz -> `127.0.0.1:3100`
- GrowChief -> `127.0.0.1:3200`
- Postgres and Redis stay internal to Docker only

Repo assets that back this layout:

- `docker-compose.production.yml`
- `deploy/nginx/ai-influencer.reverse-proxy.conf`
- `deploy/nginx/ai-influencer.single-domain.conf`
- `deploy/vps/deploy-production.sh`
- `deploy/vps/apply-chatgpt-connector-migration.sh`
- `deploy/vps/backup-stack.sh`
- `deploy/vps/restore-stack.sh`
- `deploy/vps/healthcheck.sh`
- `deploy/vps/rollback-release.sh`

## Production Env Contract

Start from `Project/.env.example`, then copy it to `Project/.env.production` on the VPS.

Production values that must be set for internal v1:

- `POSTGRES_PASSWORD=<real password>`
- `FRONTEND_PUBLIC_URL=https://ai-influencer.tripc.ai`
- `BACKEND_PUBLIC_URL=https://api.ai-influencer.tripc.ai`
- `CHATGPT_CONNECTOR_PUBLIC_URL=https://connector.ai-influencer.tripc.ai`
- `OPENAI_OAUTH_REDIRECT_URI=https://connector.ai-influencer.tripc.ai/oauth/callback`
- `CHATGPT_CONNECTOR_SESSION_SECRET=<real secret>`
- `CHATGPT_CONNECTOR_DATABASE_URL=<ai_influencer postgres url>`
- `POSTIZ_WEBHOOK_SECRET=<real secret>`
- `GROWCHIEF_WEBHOOK_SECRET=<real secret>`
- `CORS_ORIGINS=https://ai-influencer.tripc.ai,https://api.ai-influencer.tripc.ai,https://connector.ai-influencer.tripc.ai`

## Release Baseline

Backend:

```bash
cd Project/python_services
set DEBUG=true&& python -m pytest tests\test_media_api.py tests\test_chatgpt_connector_auth.py tests\test_chatgpt_connector_tools.py tests\test_chatgpt_connector_app.py tests\test_quota_monitor_service.py tests\test_quota_api.py tests\test_proxy_manager_service.py tests\test_accounts_api.py tests\test_services.py tests\test_content_api.py tests\test_analytics_api.py tests\test_distribution_activities.py tests\test_workflows_api.py tests\test_worker_imports.py
```

Frontend:

```bash
cd Project
npm test -- --runInBand app/api/routes.test.ts app/dashboard/page.test.tsx
```

Compose validation:

```bash
docker compose -f docker-compose.yml config
docker compose -f docker-compose.production.yml config
```

## VPS Rollout

1. Bootstrap the host:

```bash
sudo bash setup-vps.sh
```

2. Copy and fill the production env file:

```bash
cd /opt/ai-influencer/repo
cp Project/.env.example Project/.env.production
```

3. Install the nginx config:

```bash
sudo cp deploy/nginx/ai-influencer.reverse-proxy.conf /etc/nginx/sites-available/ai-influencer.conf
sudo ln -sf /etc/nginx/sites-available/ai-influencer.conf /etc/nginx/sites-enabled/ai-influencer.conf
sudo nginx -t
sudo systemctl reload nginx
```

4. Start or update the stack:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/deploy-production.sh
```

5. Apply the connector link migration:

```bash
cd /opt/ai-influencer/repo
./deploy/vps/apply-chatgpt-connector-migration.sh
```

6. Run smoke checks:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/healthcheck.sh
```

## Routine Ops

Create a backup:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/backup-stack.sh
```

Restore a backup:

```bash
cd /opt/ai-influencer/repo
./deploy/vps/restore-stack.sh ./backups/<timestamp>
```

Rollback to a known git tag or commit:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/rollback-release.sh <git-ref>
```

Recreate stale containers after compose or schema drift:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml down --remove-orphans
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml up -d --build
```

## Manual Internal-v1 Acceptance

Run these with real credentials and callbacks:

1. Start a weekly workflow and confirm strategy -> Telegram approval -> media generation -> publish -> webhook -> dashboard.
2. Hit `/api/quota/summary` after real provider calls and confirm the `API Usage` panel changes.
3. Start a real connector session and confirm tool calls reach OpenClaw while shell execution stays blocked.
4. Use the accounts API to refresh proxies, build an onboarding plan, execute it, and confirm `browser_profiles` plus `social_accounts` persistence.
5. Validate the dashboard retry path for a failed publish item.
6. Restart backend and worker during a long-running workflow and confirm Temporal resumes correctly.

## Security And Hardening

- Keep UFW limited to `22`, `80`, and `443`.
- Keep app containers bound to `127.0.0.1` unless a service is intentionally private-admin via SSH tunnel.
- Disable SSH root login fully after a non-root sudo user with key auth is confirmed.
- Verify `certbot renew --dry-run` succeeds.
- Rotate `CHATGPT_CONNECTOR_SESSION_SECRET`, `JWT_SECRET_KEY`, webhook secrets, and database passwords before the first real operator run.

## Known Remaining Manual Work

- Real OAuth/client registration for the ChatGPT connector still must be completed outside the repo.
- Real provider credentials and webhook callback registration still must be configured in production.
- Facebook-first human-assisted onboarding still needs live operator execution to count as accepted.
