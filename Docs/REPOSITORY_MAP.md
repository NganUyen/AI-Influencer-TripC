# Repository Map

Last verified: 2026-03-24 (UTC)

This is the quickest codebase map for someone new to the repo.

## Top-Level Layout

```text
repo/
|-- Docs/                          Canonical docs set
|-- Project/                       Product application code
|   |-- app/                       Next.js routes and API proxies
|   |-- components/                Customer and ops UI
|   |-- config/                    Frontend feature flags and platform metadata
|   |-- lib/                       Frontend API/auth helpers
|   |-- python_services/           FastAPI app, worker, workflows, services, tests
|   |-- store/                     Zustand stores
|   |-- supabase/                  Base schema, migrations, and seed SQL
|   `-- types/                     Shared TypeScript types
|-- deploy/                        nginx configs and VPS scripts
|-- docker/                        Custom Docker build contexts and helper assets
|-- docker-compose.yml             Local stack
`-- docker-compose.production.yml  Production stack
```

## Frontend Code

- `Project/app/page.tsx`: landing page
- `Project/app/auth/page.tsx`: customer sign-in and sign-up flow
- `Project/app/dashboard/page.tsx`: customer workspace route
- `Project/app/ops/login/page.tsx`: operator login route
- `Project/app/ops/page.tsx`: operator console route
- `Project/app/api/`: Next.js proxy layer for customer and ops traffic
- `Project/components/customer-dashboard.tsx`: main customer app experience
- `Project/components/ops-console.tsx`: main internal ops experience
- `Project/lib/api-client.ts`: admin API client with bearer token wiring
- `Project/lib/customer-api.ts`: customer proxy request helper
- `Project/lib/supabase.ts`: Supabase browser client
- `Project/store/customer-auth-store.ts`: customer session state
- `Project/store/auth-store.ts`: operator token state
- `Project/store/content-store.ts`: workflow/content state for the ops surface

## Backend Code

- `Project/python_services/main.py`: FastAPI app entrypoint
- `Project/python_services/worker.py`: Temporal worker entrypoint
- `Project/python_services/api/`: route modules
- `Project/python_services/services/`: persistence, provider, and helper services
- `Project/python_services/activities/`: Temporal activity implementations
- `Project/python_services/workflows/`: Temporal workflow definitions
- `Project/python_services/chatgpt_connector/`: separate connector app
- `Project/python_services/config/settings.py`: runtime settings contract
- `Project/python_services/tests/`: pytest coverage for APIs, services, webhooks, connector logic, and worker imports

## Backend Subdirectories

### `api/`

- `accounts.py`: account connection, proxies, onboarding, and stealth-account endpoints
- `analytics.py`: analytics summary and engagement routes
- `content.py`: content listing, retry, and stats routes
- `customer.py`: customer-facing brand, account, assistant, campaign, approval, and content routes
- `media.py`: image, video, audio, storage, and carousel generation routes
- `personas.py`: persona CRUD and readiness routes
- `quota.py`: provider quota and snapshot routes
- `telegram_webhook.py`: Telegram subscription and callback handling
- `webhooks.py`: provider webhook ingestion
- `workflows.py`: start, status, approve, list, and cancel workflow routes

### `services/`

- customer/domain services: `brand_profile_service.py`, `assistant_service.py`, `customer_campaign_service.py`, `customer_ai_backbone_service.py`, `customer_auth_service.py`, `account_connection_service.py`
- provider/services: `postiz_service.py`, `growchief_service.py`, `openclaw_service.py`, `telegram_service.py`, `storage_service.py`, `proxy_manager_service.py`
- media/AI helpers: `ai_service.py`, `fal_service.py`, `google_tts_service.py`, `heygen_service.py`, `script_service.py`, `carousel_service.py`, `content_scenes_service.py`
- persistence and registries: `database_service.py`, `content_persistence_service.py`, `persona_registry_service.py`, `customer_token_vault.py`, `telegram_subscriber_service.py`, `skill_session_store.py`

### `activities/`

- `strategy_activities.py`: planning and content prompt generation
- `media_activities.py`: image, video, audio, storage, and scene generation
- `distribution_activities.py`: scheduling, publishing, and engagement tracking
- `approval_activities.py`: Telegram approvals, script review, and publish decisions
- `story_activities.py`: daily story generation and approval fan-out
- `video_activities.py`: split-screen assembly

### `chatgpt_connector/`

- `app.py`: connector FastAPI surface
- `auth.py`: session signing and OAuth-like bootstrap
- `store.py`: durable ChatGPT link persistence
- `tools.py`: safe OpenClaw task wrappers
- `models.py`: connector request and response models

## Data And Schema Assets

- `Project/supabase/schema.sql`: full bootstrap schema
- `Project/supabase/migrations/`: incremental schema changes
- `Project/supabase/seed.sql`: disposable local/staging seed data
- `docker/postgres/init/00_create_service_databases.sql`: service database bootstrap

## Deployment And Infra

- `deploy/vps/deploy-production.sh`: build and start the production compose stack
- `deploy/vps/apply-db-migrations.sh`: apply incremental SQL migrations
- `deploy/vps/healthcheck.sh`: public and private smoke checks
- `deploy/vps/check-provider-apis.sh`: provider API reachability validation
- `deploy/vps/backup-stack.sh`: database and browser-profile backup
- `deploy/vps/restore-stack.sh`: restore backups
- `deploy/vps/rollback-release.sh`: git-based rollback helper
- `deploy/nginx/ai-influencer.reverse-proxy.conf`: multi-host nginx config
- `deploy/nginx/ai-influencer.single-domain.conf`: single-domain nginx config

## Start Here If You Are Debugging

- customer UI issue: `Project/components/customer-dashboard.tsx`
- ops UI issue: `Project/components/ops-console.tsx`
- proxy/auth issue: `Project/app/api/` plus `Project/store/*auth*.ts`
- workflow issue: `Project/python_services/workflows/` plus `activities/`
- provider issue: `Project/python_services/services/`
- schema issue: `Project/supabase/schema.sql` and `migrations/`
- deployment issue: `docker-compose.production.yml` plus `deploy/vps/`
