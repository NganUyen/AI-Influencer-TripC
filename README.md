# AI Influencer Factory

Last verified: 2026-04-18 (UTC)

AI Influencer Factory is a full-stack automation repo for customer-facing campaign planning and operator-managed workflow execution. The current codebase combines a Next.js app, a FastAPI backend, Temporal workflows, and a self-hosted support stack built around OpenClaw, Postiz, GrowChief, PostgreSQL, Redis, Docker Compose, and Supabase for auth/storage.

## Current Stage

The repo is past the original blueprint phase and now has a real product split:

- customer app for sign-in, brand onboarding, assistant threads, campaign review, and launch
- internal ops console for workflow monitoring, approvals, retries, analytics, and quota visibility
- backend/customer APIs plus a separate ChatGPT-facing OpenClaw connector
- production-oriented deployment assets for a private self-hosted runtime

The strongest implemented slice today is:

1. customer onboarding and planning in the web app
2. review-first campaign approval and Temporal launch
3. operator monitoring and retry flows
4. persisted publish, webhook, and quota state in PostgreSQL

The main remaining gaps are live provider registration, deeper native publishing adapters, and more end-to-end validation with real credentials.

## Repository Layout

```text
repo/
|-- Docs/                      Canonical project docs
|-- Project/
|   |-- app/                   Next.js App Router frontend
|   |-- components/            Customer and ops UI
|   |-- lib/                   Frontend API and auth helpers
|   |-- python_services/       FastAPI app, worker, workflows, services
|   |-- store/                 Zustand stores
|   |-- supabase/              Schema and migrations used by the repo DB
|   `-- README.md              Frontend-focused guide
|-- deploy/                    nginx and VPS scripts
|-- docker/                    Custom service images and helpers
|-- docker-compose.yml         Local stack
`-- docker-compose.production.yml
```

## Main Entry Points

- landing page: `Project/app/page.tsx`
- customer workspace: `Project/app/dashboard/page.tsx`
- operator console: `Project/app/ops/page.tsx`
- frontend proxy routes: `Project/app/api/...`
- backend API: `Project/python_services/main.py`
- Temporal worker: `Project/python_services/worker.py`
- weekly workflow: `Project/python_services/workflows/weekly_marketing_workflow.py`
- short-video workflow: `Project/python_services/workflows/short_video_workflow.py`
- daily-story workflow: `Project/python_services/workflows/daily_story_workflow.py`

## Local Development

Start with [Docs/START_HERE.md](./Docs/START_HERE.md). It covers:

- prerequisites
- env setup
- frontend-only boot
- frontend plus backend boot
- minimal workflow infrastructure
- full Docker stack

Quick commands:

```bash
cd Project
npm install
npm run dev
```

```bash
cd Project/python_services
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Production And Operations

Use [Docs/OPERATIONS_RUNBOOK.md](./Docs/OPERATIONS_RUNBOOK.md) for:

- VPS bootstrap
- multi-host and single-domain topology
- `.env.production` setup
- deploy, migration, and smoke-check steps
- Postiz and GrowChief bootstrap
- backup, restore, rollback, and security notes

## Documentation Map

Canonical docs now live in `Docs/`:

- [Docs/README.md](./Docs/README.md)
- [Docs/START_HERE.md](./Docs/START_HERE.md)
- [Docs/ARCHITECTURE.md](./Docs/ARCHITECTURE.md)
- [Docs/REPOSITORY_MAP.md](./Docs/REPOSITORY_MAP.md)
- [Docs/FRONTEND.md](./Docs/FRONTEND.md)
- [Docs/BACKEND_API.md](./Docs/BACKEND_API.md)
- [Docs/WORKFLOWS_AND_AUTOMATION.md](./Docs/WORKFLOWS_AND_AUTOMATION.md)
- [Docs/VIDEO_CREATION_CURRENT_STATE.md](./Docs/VIDEO_CREATION_CURRENT_STATE.md)
- [Docs/CREATE_VIDEO_WEB_INTEGRATION_PLAN.md](./Docs/CREATE_VIDEO_WEB_INTEGRATION_PLAN.md)
- [Docs/CREATE_VIDEO_CONTRACT_SYNC_PLAN.md](./Docs/CREATE_VIDEO_CONTRACT_SYNC_PLAN.md)
- [Docs/CREATE_VIDEO_BACKEND_RELIABILITY_PLAN.md](./Docs/CREATE_VIDEO_BACKEND_RELIABILITY_PLAN.md)
- [Docs/INTEGRATIONS.md](./Docs/INTEGRATIONS.md)
- [Docs/db.md](./Docs/db.md)
- [Docs/ENVIRONMENT_REFERENCE.md](./Docs/ENVIRONMENT_REFERENCE.md)
- [Docs/OPERATIONS_RUNBOOK.md](./Docs/OPERATIONS_RUNBOOK.md)
- [Project/README.md](./Project/README.md)
- [Project/python_services/README.md](./Project/python_services/README.md)

Historical design notes, refactor plans, QA writeups, and one-off analysis docs are archived in [Docs/archive/](./Docs/archive/README.md).

Rule:

- keep only this `README.md` as repo-root documentation
- keep current documentation in `Docs/`
- keep active implementation plans in `Docs/`
- move temporary or historical notes into `Docs/archive/`

## Testing

Frontend:

```bash
cd Project
npm test
```

Backend:

```bash
cd Project/python_services
pytest
```
