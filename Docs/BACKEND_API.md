# Backend And API

Last verified: 2026-03-24 (UTC)

The backend is a FastAPI application plus a separate ChatGPT-facing connector, backed by PostgreSQL and a Temporal worker.

## Runtime Entry Points

- `Project/python_services/main.py`: FastAPI app for customer, internal, webhook, and media routes
- `Project/python_services/worker.py`: Temporal worker registration and activity execution
- `Project/python_services/chatgpt_connector/app.py`: separate connector FastAPI app
- `Project/python_services/config/settings.py`: env-backed runtime settings and production-safety validation

## Backend Behavior

`main.py` currently provides:

- CORS configuration from `CORS_ORIGINS`
- security headers on every request
- sanitized 5xx error responses
- degraded startup if Temporal is unavailable
- mounted route groups for customer, ops, media, workflow, webhook, analytics, quota, and persona traffic

## Auth Model By Route Family

### Internal routes

These route groups require `x-internal-api-token` through `Depends(require_internal_api_token)`:

- `/api/workflows/*`
- `/api/media/*`
- `/api/accounts/*`
- `/api/analytics/*`
- `/api/content/*`
- `/api/quota/*`
- `/api/personas/*`

They are normally reached through the Next.js admin proxy layer.

### Customer routes

`/api/customer/*`:

- expect a bearer token
- validate the token against Supabase Auth
- resolve or upsert the related `public.users` record
- scope reads and writes to the customer identity

### Webhook routes

- `/api/webhooks/postiz`: verifies `POSTIZ_WEBHOOK_SECRET`
- `/api/webhooks/growchief`: verifies `GROWCHIEF_WEBHOOK_SECRET`
- `/api/webhooks/telegram`: verifies the Telegram webhook secret token

### Public health routes

- `/`
- `/health`

## Route Surface

### Workflows

Routes in `api/workflows.py`:

- `POST /api/workflows/start-weekly`
- `POST /api/workflows/start-video`
- `POST /api/workflows/approve/{workflow_id}`
- `GET /api/workflows/status/{workflow_id}`
- `GET /api/workflows/list`
- `POST /api/workflows/cancel/{workflow_id}`

These routes start, signal, inspect, list, and cancel Temporal workflows.

### Customer API

Routes in `api/customer.py`:

- `GET/PUT /api/customer/brand`
- `GET /api/customer/social-accounts`
- `POST /api/customer/social-accounts/{platform}/oauth/start`
- `GET /api/customer/social-accounts/{platform}/oauth/callback`
- `POST /api/customer/social-accounts/{social_account_id}/disconnect`
- `GET/POST /api/customer/assistant/threads`
- `GET/POST /api/customer/assistant/threads/{thread_id}/messages`
- `GET/PUT /api/customer/ai-backbone`
- `POST /api/customer/ai-backbone/chatgpt/oauth/link`
- `POST /api/customer/ai-backbone/chatgpt/oauth/disconnect`
- `GET/POST /api/customer/campaigns`
- `POST /api/customer/campaigns/{campaign_id}/approve`
- `POST /api/customer/campaigns/{campaign_id}/launch`
- `GET /api/customer/content`
- `GET /api/customer/approvals`

This is the main product API used by the customer dashboard.

### Content, analytics, quota, and media

- content: list persisted content, retry publish, and fetch content stats
- analytics: post-level and summary analytics views
- quota: provider usage, limits, and snapshot endpoints
- media: generate image, video, audio, carousel, and inspect storage
- `POST /api/media/generate/image` now preserves backward compatibility (`url`, `images`) while also returning provider/source URLs and stable storage metadata when persistence succeeds

### Accounts and personas

- accounts: proxy inventory, lease/refresh, onboarding plan and execute, stealth account helpers, direct platform connection helpers
- personas: CRUD plus readiness checks for persona-driven video flows

## Service Layer Map

### Customer and product services

- `customer_auth_service.py`: Supabase session validation and app-user resolution
- `brand_profile_service.py`: brand profile persistence
- `assistant_service.py`: threads, messages, and artifacts
- `customer_campaign_service.py`: campaign creation, approval, launch, and listing
- `customer_ai_backbone_service.py`: AI backbone settings and connector link metadata
- `account_connection_service.py`: OAuth state, callback handling, and connected account metadata
- `customer_token_vault.py`: encrypted storage for customer platform tokens

### Provider and infra services

- `openclaw_service.py`: OpenClaw task execution
- `postiz_service.py`: publishing bridge and schedule state handling
- `growchief_service.py`: engagement workflow integration
- `telegram_service.py`: Telegram delivery
- `telegram_subscriber_service.py`: Telegram subscriber persistence
- `storage_service.py`: Supabase or S3-compatible media storage
- `proxy_manager_service.py`: proxy inventory and lease state
- `quota_monitor_service.py`: provider-usage aggregation and alert thresholds

### Media and content services

- `ai_service.py`: direct model/provider calls and quota extraction
- `fal_service.py`: fal.ai media generation integration
- `image_generation_service.py`: canonical image-generation pipeline used by the media API and worker/skill callers
- `google_tts_service.py`: text-to-speech
- `heygen_service.py`: talking-head video generation
- `script_service.py`: structured script generation
- `carousel_service.py`: rendered carousel image generation
- `content_scenes_service.py`: scene generation helpers
- `publisher_service.py`: publishing coordination
- `content_persistence_service.py`: content, workflow, and engagement persistence helpers

## ChatGPT Connector

The connector is intentionally separate from the main FastAPI app.

Current routes:

- `GET /health`
- `GET /mcp`
- `POST /oauth/start`
- `POST /oauth/callback`
- `GET /sessions/{session_id}`
- `POST /mcp`

Important constraints:

- connector sessions are signed and time-limited
- durable identity links can be stored in `public.chatgpt_oauth_links`
- the connector only exposes safe OpenClaw tasks
- `shell_command` is explicitly blocked

## Tests

The backend test suite includes:

- customer API routes
- accounts, analytics, content, quota, and webhook routes
- distribution and storage services
- connector auth, app, store, and tool behavior
- worker import and integration-shape tests

Run them with:

```bash
cd /opt/ai-influencer/repo/Project/python_services
pytest
```
