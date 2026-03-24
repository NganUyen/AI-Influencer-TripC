# Current Repo Status

Last verified: 2026-03-24 (UTC)

This is the canonical snapshot of what the repo implements today.

## Summary

The project is now a customer-facing growth automation product with a separate internal ops surface, backed by a self-hosted workflow and publishing stack.

The repo is no longer best described as a concept or blueprint. The codebase contains:

- a real customer web app
- a real internal operator console
- a FastAPI backend with customer and internal APIs
- a Temporal worker with multiple registered workflows
- production Docker and VPS assets for the private support stack

## Product Surface

### Customer app

Implemented in `Project/app/dashboard` and `Project/components/customer-dashboard.tsx`:

- Supabase-backed customer session handling
- persisted brand profile management
- social account list plus OAuth start/callback scaffolding
- assistant threads, messages, and artifacts
- campaign draft, approval, and launch actions
- customer approvals and content views

### Internal ops

Implemented in `Project/app/ops` and `Project/components/ops-console.tsx`:

- workflow monitoring
- approval actions
- publish retry actions
- content and engagement summaries
- quota visibility

### Backend

Implemented in `Project/python_services/`:

- FastAPI route groups for workflows, media, accounts, analytics, quota, content, personas, webhooks, and customer APIs
- degraded startup when Temporal is unavailable
- direct PostgreSQL persistence through service-layer code
- separate ChatGPT-facing OpenClaw connector under `chatgpt_connector/`

### Workflows

Registered in the worker today:

- `WeeklyMarketingWorkflow`
- `PostPublishingWorkflow`
- `EngagementSyndicateWorkflow`
- `ShortVideoWorkflow`
- `DailyStoryWorkflow`

The weekly workflow remains the strongest durable orchestration lane. The short-video and story flows are implemented but still more integration-sensitive.

## Infrastructure Surface

The local and production compose files currently define:

- PostgreSQL
- Temporal plus Temporal UI
- a separate provider-side Temporal cluster for self-hosted social tools
- Redis
- OpenClaw
- ChatGPT connector
- Postiz
- GrowChief
- backend API
- Temporal worker
- frontend

Production deployment assets live under:

- `docker-compose.production.yml`
- `deploy/nginx/`
- `deploy/vps/`

## Database And Auth Reality

- the primary application data path is direct PostgreSQL, not Supabase-hosted Postgres
- `Project/supabase/schema.sql` and `Project/supabase/migrations/` are the checked-in schema sources
- post-bootstrap migrations must still be applied after deploy
- customer identity resolution is now session-based for `/api/customer/*`
- internal/admin paths remain separated from the customer surface

## Validation In Repo

Current checked-in automated coverage includes:

- frontend route and dashboard tests
- Zustand store tests
- backend tests for customer APIs
- backend tests for connector auth/tools/app behavior
- backend tests for quota monitoring
- backend tests for accounts, analytics, content, webhooks, services, distribution activities, and worker imports

## Current Limits

The repo is in a usable internal-v1 stage, but not yet a zero-touch public SaaS rollout.

Main remaining gaps:

- real provider OAuth/client registration outside the repo
- deeper native customer publishing adapters instead of the Postiz-backed bridge
- more end-to-end validation with real Postiz, GrowChief, Telegram, and media-provider credentials
- continued hardening around long-lived production data and migrations

## Recommended Reading Order

1. [START_HERE.md](./START_HERE.md)
2. [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)
3. [../Project/README.md](../Project/README.md)
4. [../Project/python_services/README.md](../Project/python_services/README.md)
