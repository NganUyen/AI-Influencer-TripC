# Architecture

Last verified: 2026-03-24 (UTC)

This repo implements a customer-facing growth automation product with a separate operator surface and a self-hosted workflow/publishing stack.

## Product Split

- customer app: sign-in, brand onboarding, AI backbone settings, social account connection scaffolding, assistant threads, campaigns, approvals, and content views
- ops console: workflow monitoring, approval actions, retry actions, analytics summary, and quota visibility
- backend API: FastAPI routes for both customer and internal operations
- worker: Temporal workflows and activities for strategy, media, approval, publishing, and engagement
- connector: a separate ChatGPT-facing OpenClaw connector with its own auth/session flow

## System View

```text
Customer Browser
  -> Next.js app (`Project/`)
  -> `/api/customer/*` proxy routes
  -> FastAPI customer routes
  -> PostgreSQL + Temporal + provider services

Operator Browser
  -> Next.js ops UI
  -> admin proxy routes in `app/api/*`
  -> FastAPI internal routes
  -> Temporal client + persistence services

Temporal Worker
  -> workflow/activity modules
  -> OpenClaw, Telegram, storage, Postiz, GrowChief, media providers

ChatGPT
  -> connector service (`chatgpt_connector/`)
  -> safe OpenClaw task wrappers
  -> OpenClaw gateway
```

## Main Runtime Components

- frontend: Next.js App Router app in `Project/`
- backend API: FastAPI app in `Project/python_services/main.py`
- workflow worker: Temporal worker in `Project/python_services/worker.py`
- connector: separate FastAPI app in `Project/python_services/chatgpt_connector/app.py`
- app database: PostgreSQL `ai_influencer`
- support stack: Temporal, Redis, OpenClaw, Postiz, GrowChief, provider-side Temporal cluster, and related Docker services

## Request And Control Flows

### Customer flow

1. The browser signs in with Supabase Auth.
2. The frontend stores the customer access token in `customer-auth-store.ts`.
3. Customer UI requests go to Next.js catch-all proxy routes under `app/api/customer/[...path]/route.ts`.
4. The proxy forwards the `Authorization` header to FastAPI `/api/customer/*`.
5. FastAPI validates the bearer token, resolves or upserts the user record, and reads or writes PostgreSQL state.
6. Campaign launch actions can start Temporal-backed automation.

### Operator flow

1. The operator logs in through the internal token flow in `store/auth-store.ts`.
2. The ops UI calls Next.js admin proxy routes such as `/api/workflows/list` and `/api/content/stats`.
3. Next.js validates `APP_ADMIN_TOKEN`, then forwards to FastAPI with `x-internal-api-token`.
4. FastAPI internal routes return workflow, content, analytics, quota, and media/provider data.

### Workflow flow

1. FastAPI starts or signals a Temporal workflow.
2. The Temporal worker executes activities against AI/media/provider services.
3. Activity results are stored in PostgreSQL, storage, or provider systems.
4. Provider webhooks and Telegram callbacks update workflow state and customer-facing status.

### ChatGPT connector flow

1. ChatGPT calls the connector manifest at `/mcp`.
2. The connector performs an OAuth-like bootstrap flow through `/oauth/start` and `/oauth/callback`.
3. Connector sessions are resolved by signed session tokens and optional persisted link records in `public.chatgpt_oauth_links`.
4. Only a constrained set of OpenClaw tools is exposed; shell execution is intentionally blocked.

## Auth And Trust Boundaries

- customer auth: Supabase bearer token validated on `/api/customer/*`
- operator auth: `APP_ADMIN_TOKEN` at the Next.js edge for the ops console
- service-to-service auth: `INTERNAL_API_TOKEN` forwarded from Next.js to FastAPI internal routes
- provider webhooks: secret verification for Postiz and GrowChief webhook endpoints
- Telegram callbacks: secret-token verification on the Telegram webhook endpoint
- connector sessions: signed session tokens plus optional persisted identity links

## Data Model

- application state lives in PostgreSQL `ai_influencer`
- customer identity comes from Supabase Auth, but the repo keeps its own `public.users` row as the relational anchor
- generated media defaults to a public Supabase Storage bucket, with S3-compatible fallback support
- Postiz, GrowChief, and Temporal have service-specific databases that are not the canonical product data model

## Degraded And Partial Modes

- the backend can start when Temporal is unavailable; workflow-triggering features degrade until Temporal reconnects
- the ops proxy routes can return structured fallback payloads when backend read-only endpoints are unreachable
- many provider flows are implemented but still depend on real external credentials and operator bootstrap work

## Key Files

- `Project/app/dashboard/page.tsx`
- `Project/components/customer-dashboard.tsx`
- `Project/app/ops/page.tsx`
- `Project/components/ops-console.tsx`
- `Project/python_services/main.py`
- `Project/python_services/worker.py`
- `Project/python_services/chatgpt_connector/app.py`
- `Project/supabase/schema.sql`
- `docker-compose.yml`
- `docker-compose.production.yml`
