# Project Status

Last verified: 2026-03-20 (Asia/Bangkok)

This document is the current implementation snapshot for the repo. It replaces the older
"planned next steps" view with a repo-grounded summary of what is implemented now, what was
verified, and what still needs external hardening.

## Snapshot

- Core delivery lane status: `Temporal/Postiz/GrowChief/dashboard` is through Phases 1-4 and now has production-oriented env and compose wiring.
- Additional workstreams now implemented at `v1`:
  - API quota monitoring
  - ChatGPT/OpenClaw connector scaffold
  - proxy-driven account onboarding substrate
- Current strongest product slice:
  - workflow orchestration
  - persisted publish and engagement state
  - dashboard operator controls
  - provider webhook sync
  - API usage visibility with exact remaining quota where supported
- Remaining work is now mostly:
  - external deployment/auth registration
  - manual containerized E2E validation
  - deeper platform-specific automation

## What Has Been Achieved

### Phase 1: Workflow and dashboard foundation

Completed:

- weekly workflow approval compatibility was restored
- Telegram approval state now persists across service instances
- rejection and timeout handling were corrected
- child publish workflows are started correctly
- workflow/content statuses are normalized for the dashboard
- Docker Compose issues were fixed for:
  - OpenClaw vs Temporal port collision
  - Postiz / GrowChief database bootstrap
  - proxy env mapping

Key outcomes:

- the worker can boot cleanly on the current workflow path
- the dashboard can poll meaningful content and workflow state
- Postgres bootstrap supports the multi-service stack more reliably

### Phase 2: Persisted publishing and engagement state

Completed:

- scheduled and published posts are now stored in the database
- Postiz publish results are normalized into a stable internal contract
- due posts are no longer accidentally re-scheduled at publish time
- publish metadata is persisted:
  - `platform_post_id`
  - provider post ID
  - `post_url`
  - publish method
  - publish error
- engagement snapshots are persisted
- GrowChief syndicate job history is persisted
- analytics summary is now database-backed instead of placeholder-only

Key outcomes:

- the dashboard no longer depends only on Temporal workflow history
- publish and engagement state are now first-class records
- analytics summary can be derived from persisted state

### Phase 3: Dashboard operator polish

Completed:

- persisted content items are enriched with live workflow details
- the dashboard now shows:
  - content status
  - workflow status
  - current step
  - scheduled and published timestamps
  - post links
  - publish method
  - publish error
  - engagement summary
  - syndicate job status
- failed persisted posts can now be retried from the dashboard
- retry starts a fresh `PostPublishingWorkflow`

Key outcomes:

- the dashboard is now an operator console, not just a workflow monitor
- operators can understand what happened to a post and react to failures

### Phase 4: Provider webhook sync and idempotent status handling

Completed:

- signed webhook endpoints now exist for:
  - Postiz
  - GrowChief
- optional webhook secrets were added:
  - `POSTIZ_WEBHOOK_SECRET`
  - `GROWCHIEF_WEBHOOK_SECRET`
- provider payloads are normalized into canonical internal event shapes
- repeated webhook deliveries are handled idempotently
- webhook sync updates existing DB records instead of creating duplicate state
- GrowChief webhook metrics can flow into persisted engagement snapshots

Key outcomes:

- the repo now has a real provider-sync path for production integrations
- provider status updates can reconcile dashboard state after async external events

### API quota monitoring v2

Completed:

- a backend-first quota monitor now exists in `Project/python_services/services/quota_monitor_service.py`
- quota data is stored in `public.analytics_events` with `event_type='api_usage'`
- the monitor supports DB-backed persistence with safe in-memory fallback
- provider summaries are exposed under `/api/quota/*`
- runtime usage instrumentation now exists at the wrapper boundary for:
  - OpenAI / Anthropic / Gemini via `AIService.generate_text()`
  - fal.ai via `FalAIService`
  - Google TTS via `GoogleTTSService.generate_audio()`
  - HeyGen via `create_*` and `get_video_status()`
- the dashboard now includes an `API Usage` panel
- provider summaries now distinguish:
  - exact provider-reported remaining quota
  - tracked remaining against configured limits
  - unsupported / unavailable live remaining quota
- exact remaining quota is now wired for:
  - OpenAI via `x-ratelimit-*` response headers
  - Anthropic via `anthropic-ratelimit-*` response headers
  - HeyGen via the provider remaining-quota endpoint
- the dashboard now shows:
  - remaining quota left
  - remaining requests left where provided
  - reset timing where provided
  - source-aware messaging instead of generic `Unknown`
- placeholder-style API keys such as `your_openai_key` are now treated as not configured instead of configured-but-unknown

Key outcomes:

- operators can see usage state and warning levels in the main dashboard
- quota visibility is now tied to the actual runtime call boundaries
- supported providers can now expose exact remaining quota in the dashboard instead of usage-only summaries
- unsupported providers now fail honestly with explicit fallback messaging
- prompts and API keys are intentionally excluded from quota metadata

Current limitations inside this lane:

- Gemini, Google TTS, and fal.ai still rely on tracked usage and configured limits in the current integration
- OpenClaw-mediated calls are still not quota-instrumented, so workflows that stay inside OpenClaw will not automatically populate provider quota usage

### ChatGPT/OpenClaw connector v1

Completed:

- a separate connector package now exists under `Project/python_services/chatgpt_connector/`
- the connector exposes a constrained MCP-style surface for:
  - `openclaw_execute_task`
  - `openclaw_get_task_status`
  - `openclaw_cancel_task`
- the connector has OAuth-style session/link scaffolding
- connector identity links can now persist via `chatgpt_oauth_links` when the DB schema/migration is applied
- shell execution is intentionally blocked at the connector boundary
- a dedicated `chatgpt_connector` service was added to both compose files
- connector env placeholders were added to `.env.example`

Key outcomes:

- the internal API-key-based OpenClaw integration remains intact
- the ChatGPT-facing trust boundary is now separate from the main FastAPI app
- the repo is ready for external routing and auth registration work

### Proxy/account onboarding foundation v1

Completed:

- proxy inventory parsing now supports:
  - `PROXY_INVENTORY`
  - `PROXY_1..N`
  - fallback IPRoyal-derived auth entries
- sticky proxy leasing is implemented in `ProxyManagerService`
- region-aware onboarding plans now exist for:
  - TikTok
  - Facebook
  - YouTube
- browser sessions can now persist per-account storage state under `browser_profiles`
- the accounts API is now a concrete planning/execution surface instead of a placeholder
- account registry rows can now be stored in `public.social_accounts`

Key outcomes:

- the repo now has a real proxy/account substrate instead of raw env strings
- YouTube is treated conservatively as a primary OAuth path in v1
- TikTok and Facebook are positioned as the first browser-bootstrap targets

### Media API cleanup

Completed:

- the stale `PlayHTService` media API drift was removed
- `api/media.py` now uses `GoogleTTSService`
- audio generation and voice listing now follow the active TTS implementation

Key outcomes:

- the media route no longer references a missing service export
- the repo no longer carries that previously documented runtime drift

## Current Product Surface

### Frontend

Implemented in `Project/`:

- Next.js dashboard
- local API proxy routes
- Zustand content store
- dashboard approval and retry actions
- persisted content rendering with publish and engagement details
- API usage panel for provider quota state, remaining quota, and source-aware fallback messaging
- frontend Jest coverage for dashboard and route proxies

### Backend

Implemented in `Project/python_services/`:

- FastAPI app
- Temporal client / worker integration
- degraded-mode backend startup when Temporal is unavailable
- weekly workflow orchestration
- content, workflow, analytics, quota, account, retry, and webhook APIs
- ChatGPT/OpenClaw connector app
- proxy inventory / lease / onboarding planning services

Operational bootstrap improvements also now exist:

- root launchers:
  - `Project/run-backend.cmd`
  - `Project/run-worker.cmd`
- startup/onboarding docs:
  - `Docs/START_HERE.md`
  - `Docs/OPERATIONS_RUNBOOK.md`
- current repo status / handoff docs:
  - `Docs/CURRENT_REPO_STATUS.md`

### Persistence / data

Implemented via `Project/supabase/` plus service-layer persistence:

- `content`
- `postiz_schedules`
- `engagement_action_logs`
- `analytics_events`
- `social_accounts`
- workflow-linked metadata used by the dashboard, retry path, quota summaries, and account registry state

## Verification Status

Verified in this implementation pass:

- backend targeted suites: `67 passed`
- frontend targeted suites: `13 passed`
- compose config validation:
  - `docker compose -f docker-compose.yml config`
  - `docker compose -f docker-compose.production.yml config`

Additional later verification after the quota/remaining-quota upgrade:

- backend quota/services targeted suites: `19 passed`
- frontend dashboard targeted suite: `3 passed`
- live backend quota summary now returns exact remaining HeyGen quota when the provider endpoint is reachable

Verified coverage includes:

- workflow APIs
- content APIs
- analytics APIs
- quota APIs and quota service behavior
- proxy manager and accounts APIs
- ChatGPT connector auth, tools, and app surface
- media API
- distribution activities
- service wrappers
- dashboard rendering
- route proxies
- webhook auth and normalization behavior

## What Is Still Open

### External deployment and auth completion

Still needed:

- public HTTPS exposure for the ChatGPT connector
- real OAuth/client registration and connector metadata registration
- apply the connector-link migration in deployed databases so the durable link store is active outside fresh-schema environments

### Manual integrated validation

Still needed:

- run the full stack with real provider credentials
- execute workflow -> publish -> webhook -> dashboard manually
- validate connector access from the intended external surface
- validate proxy-assisted account onboarding against real operator workflows
- validate exact remaining-quota behavior end-to-end for OpenAI and Anthropic with real non-placeholder API keys

### Deeper platform automation

Still needed:

- first real human-assisted TikTok or Facebook bootstrap flow
- actual browser-flow checkpoint handling for CAPTCHA / email / SMS challenges
- a production decision on whether YouTube remains OAuth-only or later gets a broader operator flow

### Quota-monitoring hardening

Still needed:

- if this becomes operator-heavy, add rollups or indexes for `api_usage` events
- if budget enforcement becomes necessary, add alerts / notifications / caps
- if exact billing matters, replace best-effort usage estimates with provider-specific billing integration
- decide whether OpenClaw should emit quota telemetry or whether downstream provider usage must be surfaced from OpenClaw itself
- if Gemini / Google TTS / fal.ai require true provider-side remaining quota, add provider-specific quota/billing integrations beyond the current wrapper-level tracking

## Known Remaining Risks

- quota monitoring still is not provider-billing truth
- exact remaining quota is only available today for providers that expose it through response headers or a live endpoint in the current integration
- OpenClaw-driven usage can still bypass quota capture
- connector auth/session state is implemented and DB-capable for identity links, but still not externally deployed
- proxy/account onboarding is a safe foundation, not full autonomous multi-platform account creation
- real DB persistence still depends on `asyncpg` being installed in the runtime
- the Postgres init script only affects fresh DB volumes
- compose validation succeeded, but live container startup and cross-service manual E2E were not run in this pass
- Temporal local startup required a compose fix from `DB=postgresql` to `DB=postgres12`; this is now fixed in repo, but any stale local containers should be recreated if they still reference the old configuration
- `docker compose config` currently emits warnings about:
  - obsolete `version` keys in compose files
  - blank optional shell vars when not exported in the shell environment
  - local Docker config file access on this machine

## Recommended Next Steps

Recommended order from here:

1. deploy and externally register the ChatGPT connector
2. run manual containerized E2E validation with real webhook callbacks and provider credentials
3. build the first real human-assisted TikTok or Facebook bootstrap flow on top of the proxy/account substrate
4. add quota alerts or rollups only after real operator usage patterns are known

## Helpful Reading Order

For a new contributor:

1. read this file
2. read `Docs/AI Influencer Factory Technical Blueprint.md` for original intent
3. inspect:
  - `Project/python_services/workflows/weekly_marketing_workflow.py`
  - `Project/python_services/activities/distribution_activities.py`
  - `Project/python_services/services/content_persistence_service.py`
  - `Project/python_services/services/quota_monitor_service.py`
  - `Project/python_services/services/proxy_manager_service.py`
  - `Project/python_services/chatgpt_connector/app.py`
  - `Project/python_services/api/content.py`
  - `Project/python_services/api/quota.py`
  - `Project/python_services/api/accounts.py`
  - `Project/python_services/api/webhooks.py`
  - `Project/app/dashboard/page.tsx`
4. run the targeted backend and frontend tests before making changes
