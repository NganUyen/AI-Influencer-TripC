# VPS Deployment Log - 2026-03-20

Last updated: 2026-03-20 UTC

This log records the important work completed to adapt this repository to the current public upstreams and deploy it on the VPS with Docker.

## Scope

- Repo path: `/opt/ai-influencer/repo`
- Public domain: `https://ai-influencer.tripc.ai`
- Deployment model: single-domain nginx + Docker Compose

## Important Work Completed

### 1. Read and aligned with repo deployment docs

- Reviewed the `Docs/` folder and the repo deployment scripts before changing runtime assumptions.
- Kept the single-domain topology documented in:
  - `Docs/SINGLE_DOMAIN_VPS_DEPLOY.md`
  - `Docs/VPS_ZERO_TO_PRODUCTION_GUIDE.md`
  - `deploy/nginx/ai-influencer.single-domain.conf`

### 2. Replaced stale upstream assumptions

- Removed reliance on dead or outdated public image references and stale service contracts.
- Adapted the repo to the current public upstream direction for:
  - OpenClaw
  - Postiz
  - GrowChief
  - Temporal UI

### 3. OpenClaw deployment adaptation

- Switched from stale image assumptions to a source-built public OpenClaw runtime in:
  - `docker/openclaw/Dockerfile`
- Added runtime config and workspace bind mounts under:
  - `.docker-data/openclaw/config`
  - `.docker-data/openclaw/workspace`
- Verified the OpenClaw gateway/control UI on:
  - `127.0.0.1:8081`

### 4. Backend and connector path-prefix support

- Patched the backend and ChatGPT/OpenAI connector for the single-domain path-prefix deployment:
  - `/backend`
  - `/connector`
- Files updated:
  - `Project/python_services/main.py`
  - `Project/python_services/chatgpt_connector/app.py`

### 5. Service adapter rewrites for public upstreams

- Updated Python service adapters to the current public-facing API direction:
  - `Project/python_services/services/openclaw_service.py`
  - `Project/python_services/services/postiz_service.py`
  - `Project/python_services/services/growchief_service.py`
- Updated related tests and connector tool behavior.

### 6. Production compose fixes

- Fixed production `env_file` fallback so ad-hoc deploys use `Project/.env.production` instead of the sample env.
- Updated compose wiring for:
  - OpenClaw
  - Postiz
  - GrowChief
  - backend
  - worker
  - frontend
- Files updated:
  - `docker-compose.production.yml`
  - `docker-compose.yml`

### 7. GrowChief compatibility fix

- Current public GrowChief `latest` pulls a Prisma 7 CLI at startup and fails against its Prisma 6-era schema.
- Added a compatibility wrapper image in:
  - `docker/growchief/Dockerfile`
- The fix pins startup-time Prisma commands to Prisma `6.13.0`.

### 8. Social publishing Temporal sidecar cluster

- Added a dedicated sidecar stack for Postiz/GrowChief upstream expectations:
  - `social-temporal-postgres`
  - `social-temporal-elasticsearch`
  - `social-temporal`
- This isolates their Temporal/Elasticsearch requirements from the main app Temporal cluster.

### 9. Temporal UI modernization

- The repo previously assumed the main `temporalio/auto-setup` container served the UI on `:8080`.
- Updated the stack to use a dedicated `temporalio/ui` container while preserving the operator URL:
  - `127.0.0.1:8080`

### 10. Frontend build/runtime fixes

- Updated frontend Docker build base to Node 20.
- Fixed Next.js 16 route handler typing changes.
- Removed obsolete Next config flags that blocked production build.
- Files updated:
  - `Project/Dockerfile.frontend`
  - `Project/next.config.js`
  - `Project/app/api/content/retry/[contentId]/route.ts`
  - `Project/app/api/workflows/approve/[workflowId]/route.ts`
  - `Project/app/api/workflows/status/[workflowId]/route.ts`

### 11. Production env and settings fixes

- Generated and preserved production-safe runtime secrets for:
  - Postgres
  - JWT/app tokens
  - connector secret
  - OpenClaw gateway token
- Fixed settings validation for blank optional quota env values in:
  - `Project/python_services/config/settings.py`

### 12. Connector database migration

- Applied the ChatGPT connector link migration with:
  - `deploy/vps/apply-chatgpt-connector-migration.sh`

### 13. Validation completed

- Verified local operator/admin endpoints:
  - `127.0.0.1:3000`
  - `127.0.0.1:8000/health`
  - `127.0.0.1:8010/health`
  - `127.0.0.1:8080`
  - `127.0.0.1:8081`
  - `127.0.0.1:3100`
  - `127.0.0.1:3200`
- Verified public endpoints:
  - `https://ai-influencer.tripc.ai`
  - `https://ai-influencer.tripc.ai/backend/health`
  - `https://ai-influencer.tripc.ai/connector/health`
- Ran the repo healthcheck successfully:
  - `PROJECT_ENV_FILE=./Project/.env.production ./deploy/vps/healthcheck.sh`

## Env Update Recorded On 2026-03-20

Updated `Project/.env.production` with the newly supplied concrete values for:

- Supabase URL / anon / publishable / service-role credentials
- Media provider credentials:
  - fal.ai
  - Google AI
  - Google TTS
  - HeyGen
- Proxy list entries:
  - `PROXY_1` through `PROXY_6`

Production-safe values were intentionally preserved where the supplied snippet used placeholders or development-only settings, including:

- production public URLs
- internal production database DSNs
- production Postgres password
- production OpenClaw token and runtime URL
- `DEBUG=false`
- `ENVIRONMENT=production`
- production JWT/app secrets

## Current Known State

- The Docker stack is deployed and healthy on this VPS.
- Upstream adaptation is in place for current public OpenClaw/Postiz/GrowChief/Temporal behavior.
- Real execution of some workflows still depends on filling any remaining placeholder third-party credentials in `Project/.env.production`.

## Redirect Loop Fix Recorded On 2026-03-20

- A public browser regression was reported after deployment:
  - `https://ai-influencer.tripc.ai` returned `ERR_TOO_MANY_REDIRECTS`
- Root cause:
  - the upstream edge proxy was already terminating HTTPS before forwarding requests to this VPS
  - the origin nginx `:80` server still forced `return 301 https://$host$request_uri;`
  - this created an endless HTTPS redirect loop at the edge
- Fix applied:
  - updated `deploy/nginx/ai-influencer.single-domain.conf` to respect `X-Forwarded-Proto`
  - only redirect plain HTTP requests that were not already forwarded as HTTPS
  - proxy `/`, `/backend/`, and `/connector/` directly on port `80` when the edge indicates the original request was HTTPS
  - forwarded the correct upstream protocol to the frontend/backend/connector services
- VPS action taken:
  - installed the updated nginx config to `/etc/nginx/sites-available/ai-influencer.conf`
  - validated config with `nginx -t`
  - reloaded nginx
- Validation after fix:
  - public `HEAD /` returned `HTTP/2 200`
  - local path-based health routes succeeded when simulated with:
    - `Host: ai-influencer.tripc.ai`
    - `X-Forwarded-Proto: https`
- Follow-up repo hardening:
  - updated `deploy/vps/healthcheck.sh` to force `curl --http1.1` for public edge checks because the edge occasionally triggers curl HTTP/2 framing errors during health probes despite healthy responses

## HeyGen Quota Fix Recorded On 2026-03-20

- Dashboard symptom:
  - the HeyGen provider card showed `Unknown` / `No provider quota data yet`
- Investigation findings:
  - live HeyGen quota refreshes were succeeding with `HTTP 200`
  - fresh quota snapshots were being stored in `public.analytics_events`
  - the quota summary code crashed while normalizing DB rows with:
    - `'str' object has no attribute 'get'`
- Root cause:
  - `asyncpg` can surface `JSONB` values as strings unless explicit codecs are registered
  - `Project/python_services/services/quota_monitor_service.py` assumed `row["metadata"]` was already a dict
- Fix applied:
  - added JSON-string parsing safeguards in `Project/python_services/services/quota_monitor_service.py`
  - added a regression test in `Project/python_services/tests/test_quota_monitor_service.py` for stringified quota snapshots
  - rebuilt and redeployed the `backend` and `temporal_worker` services
- Validation:
  - isolated quota monitor test suite passed:
    - `6 passed`
  - backend logs no longer show the quota parser warning
  - direct live summary inspection from the backend now reports:
    - provider: `heygen`
    - status: `ok`
    - remaining quota: `1127`
    - unit: `quota_units`

## Quota Status Label Adjustment Recorded On 2026-03-20

- Dashboard request:
  - show `Configured` instead of `Unknown` for providers that have API keys but do not expose live remaining quota yet
- Root cause:
  - the quota status fallback returned `unknown` whenever a provider was configured but had no snapshots, no live remaining value, and no configured monthly limit
- Fix applied:
  - updated `Project/python_services/services/quota_monitor_service.py` so this fallback now returns `configured`
  - added a regression test in `Project/python_services/tests/test_quota_monitor_service.py`
  - rebuilt and redeployed the `backend` and `temporal_worker` services
- Validation:
  - isolated quota monitor suite passed:
    - `6 passed`
  - direct backend summary inspection now reports:
    - `gemini`: `configured`
    - `fal_ai`: `configured`
    - `google_tts`: `configured`
    - `heygen`: `ok`
