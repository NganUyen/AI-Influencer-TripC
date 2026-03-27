# Integrations

Last verified: 2026-03-24 (UTC)

This repo is integration-heavy. The main product logic depends on several external systems, plus a few self-hosted services that act like external dependencies from the app's point of view.

## Identity, Auth, And Storage

### Supabase Auth

- used for customer sign-in and session validation
- the frontend uses Supabase browser auth
- the backend validates Supabase bearer tokens and maps them to `public.users`

### Supabase Storage

- default storage backend for generated media
- expects a public bucket named `media`
- can be replaced with S3-compatible storage when `STORAGE_PROVIDER=s3`

### S3-Compatible / R2 Fallback

- supported through `storage_service.py`
- requires the `R2_*` env contract
- useful only when media intentionally should not live in Supabase Storage

## OpenClaw And ChatGPT Connector

### OpenClaw

- runs as a self-hosted gateway service
- used for strategy, analysis, and browser-oriented task execution
- configured through `OPENCLAW_API_URL`, `OPENCLAW_API_KEY`, and related settings

### ChatGPT connector

- separate FastAPI app under `chatgpt_connector/`
- exposes an MCP-style manifest and tool surface
- performs an OAuth-like bootstrap flow for ChatGPT session binding
- persists identity links in `public.chatgpt_oauth_links`

Connector tool surface today:

- `openclaw_execute_task`
- `openclaw_get_task_status`
- `openclaw_cancel_task`

Important constraint:

- shell execution is intentionally not exposed through the connector

## Publishing And Engagement

### Postiz

- used for official publishing and schedule management
- backend integration lives in `postiz_service.py`
- webhook target: `/api/webhooks/postiz`
- environment includes `POSTIZ_API_URL`, `POSTIZ_API_KEY`, `POSTIZ_WEBHOOK_SECRET`, and optional `POSTIZ_INTEGRATION_MAP`

### GrowChief

- used for engagement and syndicate-style automation
- backend integration lives in `growchief_service.py`
- webhook target: `/api/webhooks/growchief`
- environment includes `GROWCHIEF_API_URL`, `GROWCHIEF_API_KEY`, `GROWCHIEF_WEBHOOK_SECRET`, and optional `GROWCHIEF_WORKFLOW_MAP`

### Customer social OAuth scaffolding

Configured providers today:

- LinkedIn
- Facebook
- Twitter
- YouTube

The repo includes connection scaffolding and token handling, but real production use still depends on external provider app registration and secrets.

## Messaging And Approvals

### Telegram

- used for workflow approvals, script approval, preview review, and subscriber-based story decisions
- webhook handling lives in `api/telegram_webhook.py`
- subscriber state lives in `public.telegram_subscribers`
- helper services include `telegram_service.py`, `telegram_renderer.py`, and `telegram_subscriber_service.py`

## AI And Media Providers

### OpenAI and Anthropic

- used for text generation and other AI-backed steps through `ai_service.py` and OpenClaw-backed flows
- quota information is also derived from provider responses where possible

### fal.ai

- media generation integration through `fal_service.py`
- used by image and video-related activities

### Google TTS

- text-to-speech integration through `google_tts_service.py`
- used by the short-video pipeline

### HeyGen

- talking-head avatar video generation through `heygen_service.py`
- used when persona configuration includes a compatible avatar

## Proxies And Browser Automation

### IPRoyal / proxy inventory

- configured through `IPROYAL_*`, `PROXY_*`, and locale/timezone defaults
- managed by `proxy_manager_service.py`
- used where provider/browser automation requires region-aware routing

### Browser automation

- `browser_automation.py` plus provider-side services handle browser-driven tasks
- browser profiles are backed up and restored by the VPS scripts

## Operational Caveats

- many integrations are implemented behind a stable internal interface but still need real external credentials to be exercised
- Postiz and GrowChief should stay private and be accessed through SSH tunnels in production
- provider contracts, webhook payloads, and real-world OAuth setups still require end-to-end acceptance tests after changes
