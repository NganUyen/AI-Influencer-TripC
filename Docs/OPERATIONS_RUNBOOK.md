# Operations Runbook

Last verified: 2026-03-30 (UTC)

This is the canonical deployment and operations guide for the current repo. It replaces the older split across separate VPS, single-domain, database-plan, provider-bootstrap, and deployment-log docs.

## Supported Production Topologies

Recommended multi-host topology:

- `https://ai-influencer.tripc.ai` -> frontend
- `https://api.ai-influencer.tripc.ai` -> backend
- `https://connector.ai-influencer.tripc.ai` -> ChatGPT connector

Supported single-domain fallback:

- `https://ai-influencer.tripc.ai/` -> frontend
- `https://ai-influencer.tripc.ai/backend/` -> backend
- `https://ai-influencer.tripc.ai/connector/` -> ChatGPT connector

Private or localhost-only services in both cases:

- Temporal gRPC/UI
- OpenClaw control UI
- Postiz
- GrowChief
- PostgreSQL
- Redis

Clarification:

- this repo currently supports local/dev and production wiring; there is no separate infra-level preproduction deploy target
- when other docs say "pre-production" they refer to the video planning and approval lane, not a second VPS stack

## Repo Assets Used In Production

- `docker-compose.production.yml`
- `deploy/nginx/ai-influencer.reverse-proxy.conf`
- `deploy/nginx/ai-influencer.single-domain.conf`
- `deploy/vps/deploy-production.sh`
- `deploy/vps/docker-cleanup.sh`
- `deploy/vps/install-docker-maintenance-timer.sh`
- `deploy/vps/apply-db-migrations.sh`
- `deploy/vps/check-provider-apis.sh`
- `deploy/vps/check-telegram-openclaw.sh`
- `deploy/vps/healthcheck.sh`
- `deploy/vps/backup-stack.sh`
- `deploy/vps/restore-stack.sh`
- `deploy/vps/rollback-release.sh`
- `deploy/vps/systemd/ai-influencer-docker-cleanup.service`
- `deploy/vps/systemd/ai-influencer-docker-cleanup.timer`
- `Project/.env.example`
- `.github/workflows/publish-production-images.yml`

## Production Env Contract

Create `Project/.env.production` from `Project/.env.example`.

Minimum production values for the recommended multi-host topology:

```env
POSTGRES_PASSWORD=<real password>

FRONTEND_PUBLIC_URL=https://ai-influencer.tripc.ai
BACKEND_PUBLIC_URL=https://api.ai-influencer.tripc.ai
CHATGPT_CONNECTOR_PUBLIC_URL=https://connector.ai-influencer.tripc.ai
NEXT_PUBLIC_API_URL=https://ai-influencer.tripc.ai
PYTHON_BACKEND_URL=http://backend:8000
OPENAI_OAUTH_REDIRECT_URI=https://connector.ai-influencer.tripc.ai/oauth/callback
CORS_ORIGINS=https://ai-influencer.tripc.ai,https://api.ai-influencer.tripc.ai,https://connector.ai-influencer.tripc.ai
```

Routing note:

- `NEXT_PUBLIC_API_URL` is intentionally browser-facing and should resolve to the frontend host
- the Next.js app then proxies server-side requests to FastAPI through `PYTHON_BACKEND_URL`
- browser clients should not be wired directly to the private container-network FastAPI address

Minimum changes for the single-domain fallback:

```env
FRONTEND_PUBLIC_URL=https://ai-influencer.tripc.ai
BACKEND_PUBLIC_URL=https://ai-influencer.tripc.ai/backend
CHATGPT_CONNECTOR_PUBLIC_URL=https://ai-influencer.tripc.ai/connector
NEXT_PUBLIC_API_URL=https://ai-influencer.tripc.ai
PYTHON_BACKEND_URL=http://backend:8000
OPENAI_OAUTH_REDIRECT_URI=https://ai-influencer.tripc.ai/connector/oauth/callback
CORS_ORIGINS=https://ai-influencer.tripc.ai
```

Also set real values for:

- `DATABASE_URL` for the Supabase Postgres application database
- connector auth/session secrets
- Supabase keys used by the customer auth path
- OpenAI and Anthropic keys
- Telegram credentials
- Postiz and GrowChief API keys plus webhook secrets
- proxy credentials
- media-provider credentials

Production image delivery values:

- `GHCR_NAMESPACE` defaults to `ghcr.io/nganuyen`
- `IMAGE_TAG` defaults to `latest`, but should be set to a published commit SHA when you want a deterministic rollout or rollback
- `OPENCLAW_IMAGE` can override the pinned upstream OpenClaw digest if you intentionally promote a different upstream release
- `DOCKER_CLEANUP_AFTER_DEPLOY=true` keeps post-deploy dangling-image and build-cache cleanup enabled
- `SYNC_REPO_BEFORE_DEPLOY=false` by default, so production deploy uses the current checked-out repo state unless you explicitly ask it to fast-forward a branch first
- `AUTO_IMAGE_TAG_FROM_GIT=false` by default, so production deploy does not guess an image tag from the local checkout unless you opt in
- `BUILD_APP_IMAGES_FROM_REPO=false` by default, so production deploy stays pull-only; set it only for an intentional emergency local-build path

## Database Reality

The customer-facing app database is now expected to live on Supabase Postgres.

Operational implications:

- `DATABASE_URL` in `Project/.env.production` must point at the Supabase Postgres application database
- local Docker Postgres in `docker-compose.production.yml` is only for service databases such as `postiz`, `growchief`, and Temporal internals
- `Project/supabase/migrations/*.sql` are the migration authority for long-lived environments
- `Project/supabase/schema.sql` is a disposable bootstrap snapshot, not the production migration path
- `Project/supabase/migrations/latest.sql` is a snapshot helper and must not be replayed during deploys
- back up the canonical application database before schema-changing rollouts

Canonical migration command:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/apply-db-migrations.sh
```

## Fresh VPS Bootstrap

1. Create DNS for the chosen topology.
2. Create a non-root sudo deploy user and confirm SSH key login works.
3. Clone the repo to `/opt/ai-influencer/repo`.
4. Make scripts executable:

```bash
cd /opt/ai-influencer/repo
chmod +x setup-vps.sh deploy/vps/*.sh
```

5. Bootstrap the host:

```bash
cd /opt/ai-influencer/repo
sudo bash setup-vps.sh
```

6. Copy the env file:

```bash
cd /opt/ai-influencer/repo
cp Project/.env.example Project/.env.production
```

7. Install the nginx config that matches the topology:

```bash
sudo cp deploy/nginx/ai-influencer.reverse-proxy.conf /etc/nginx/sites-available/ai-influencer.conf
```

Or for the single-domain topology:

```bash
sudo cp deploy/nginx/ai-influencer.single-domain.conf /etc/nginx/sites-available/ai-influencer.conf
```

8. Enable and reload nginx:

```bash
sudo ln -sf /etc/nginx/sites-available/ai-influencer.conf /etc/nginx/sites-enabled/ai-influencer.conf
sudo nginx -t
sudo systemctl reload nginx
```

9. Issue or renew the TLS certificates needed for the selected public hosts.

## Deploy Or Update The Stack

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production IMAGE_TAG=<published-commit-sha> ./deploy/vps/deploy-production.sh
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/apply-db-migrations.sh
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/healthcheck.sh
```

This is the standard rollout order for both fresh and existing environments.

The deploy script now pulls registry-backed images from GHCR before starting containers by default. It only rebuilds images locally on the VPS if you explicitly set `BUILD_APP_IMAGES_FROM_REPO=true`.

## Provider Bootstrap And Admin Access

Keep Postiz and GrowChief private. Access them through SSH tunnels instead of public routes.

Example tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 -L 8081:127.0.0.1:8081 -L 3100:127.0.0.1:3100 -L 3200:127.0.0.1:3200 deploy@<VPS_IP>
```

Then use:

- `http://localhost:8080` for Temporal UI
- `http://localhost:8081` for OpenClaw control UI
- `http://localhost:3100` for Postiz
- `http://localhost:3200` for GrowChief

Bootstrap checklist:

1. run `healthcheck.sh` and `check-provider-apis.sh`
2. run `check-telegram-openclaw.sh` to verify OpenClaw health and Telegram webhook wiring
3. create or confirm the operator admin account in Postiz and GrowChief
4. rotate or create the Postiz and GrowChief API keys
5. register webhook targets on the public backend
6. set `POSTIZ_INTEGRATION_MAP` and `GROWCHIEF_WORKFLOW_MAP` when multiple active integrations/workflows exist
7. rerun the provider checks

Webhook targets:

- multi-host: `https://api.ai-influencer.tripc.ai/api/webhooks/postiz`
- multi-host: `https://api.ai-influencer.tripc.ai/api/webhooks/growchief`
- single-domain: `https://ai-influencer.tripc.ai/backend/api/webhooks/postiz`
- single-domain: `https://ai-influencer.tripc.ai/backend/api/webhooks/growchief`

### OpenClaw Auth Bootstrap

If OpenClaw is up but model execution fails because auth is missing, use the lightweight bootstrap path:

1. authenticate locally with `openclaw models auth login --provider openai-codex`
2. copy `auth-profiles.json` into the production `openclaw` container or bound config volume
3. fix ownership/permissions for `/home/node/.openclaw`
4. restart the `openclaw` service
5. verify with `node openclaw.mjs models list` inside the container

Keep this as a recovery/bootstrap procedure, not as a daily workflow.

## Routine Operations

Backup:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/backup-stack.sh
```

Restore:

```bash
cd /opt/ai-influencer/repo
./deploy/vps/restore-stack.sh ./backups/<timestamp>
```

Rollback:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/rollback-release.sh <git-ref>
```

The rollback helper resolves the requested git ref to its commit SHA and redeploys that published image tag without rebuilding on the VPS.

Install the weekly Docker cleanup timer:

```bash
cd /opt/ai-influencer/repo
sudo ./deploy/vps/install-docker-maintenance-timer.sh
```

Rebuild after compose drift:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml down --remove-orphans
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml pull
PROJECT_ENV_FILE=./Project/.env.production docker compose -f docker-compose.production.yml up -d
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/docker-cleanup.sh
```

Provider API check:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/check-provider-apis.sh
```

Telegram/OpenClaw check:

```bash
cd /opt/ai-influencer/repo
PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/check-telegram-openclaw.sh
```

Video pipeline quick triage:

1. confirm the backend, worker, and Temporal UI are healthy with `healthcheck.sh`
2. inspect `/api/workflows/status/<workflow_id>` or Temporal history for the failing workflow
3. if the short-video lane failed, check worker logs for `SceneAssetMismatchError`, `send_telegram_error_notification`, and checkpoint logs `CP1`, `CP2`, `CP3`, `CP5`, `CP6`, `CP7`
4. if top-half assets degraded to fallback unexpectedly, inspect browser-capture warnings and storage fallback behavior before retrying
5. if Telegram notifications are missing, rerun `check-telegram-openclaw.sh` and verify bot/webhook credentials before retrying the workflow

## First Live Acceptance

Run at least one real end-to-end path with production credentials:

1. create or launch a campaign
2. confirm review or Telegram approval works as expected
3. confirm the publish request reaches Postiz
4. confirm the webhook updates backend/dashboard state
5. confirm quota and content status surfaces update
6. restart backend or worker once during a long-running flow and confirm Temporal recovery still works
7. for the Telegram video lane, run the approved-package smoke path before sign-off when that lane changed

## Security And Hardening

- keep public firewall exposure limited to `22`, `80`, and `443`
- keep app services bound to `127.0.0.1` unless intentionally private-admin
- disable SSH root login after confirming key-based sudo-user access
- rotate database passwords, webhook secrets, connector session secrets, and JWT/admin tokens before real operator use
- verify certificate renewal works

## Known Remaining Manual Work

- real external OAuth registration for the customer social providers
- real ChatGPT/OpenAI connector registration
- operator-owned Postiz and GrowChief account/bootstrap work
- repeated end-to-end validation whenever provider contracts or production schema change
