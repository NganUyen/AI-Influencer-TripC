# AI Influencer Factory

AI Influencer Factory is a full-stack marketing orchestration repo with a Next.js frontend, a FastAPI backend, and Temporal workflows that coordinate strategy generation, approval, media generation, publishing, and follow-up engagement.

## Current State

The strongest implemented path today is the Temporal-driven weekly workflow plus the dashboard surfaces that poll workflow/content state and send approval actions. Media generation endpoints and service wrappers are present. Some areas are still partial or placeholder, especially personas, connected-account management, and summary analytics.

## Repository Layout

```text
AI-Influencer-TripC/
|-- Docs/                      Project docs, blueprint, notes, and change tracking
|-- Project/
|   |-- app/                   Next.js App Router frontend
|   |-- components/            Shared React components
|   |-- config/                Frontend configuration and constants
|   |-- lib/                   Frontend API and utility helpers
|   |-- python_services/       FastAPI app, Temporal worker, workflows, activities
|   |-- store/                 Zustand stores
|   |-- supabase/              Schema, seed data, and migrations
|   `-- README.md              Frontend-focused docs
|-- docker-compose.yml         Local multi-service stack
`-- README.md                  This file
```

## Main Entry Points

- Frontend app: `Project/app/page.tsx`
- Dashboard: `Project/app/dashboard/page.tsx`
- Frontend API proxies: `Project/app/api/...`
- Backend API: `Project/python_services/main.py`
- Temporal worker: `Project/python_services/worker.py`
- Weekly workflow: `Project/python_services/workflows/weekly_marketing_workflow.py`

## Quick Start

### Option 1: Docker Compose

From the repository root:

```bash
docker-compose up -d --build
```

This starts PostgreSQL, Temporal, Redis, the OpenClaw gateway/control UI, Postiz, GrowChief, the FastAPI backend, the Temporal worker, and the Next.js frontend.

Default local URLs:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`
- Temporal UI: `http://localhost:8080`
- OpenClaw Control UI: `http://localhost:8081`
- Postiz: `http://localhost:3100`
- GrowChief: `http://localhost:3200`

### Option 2: Run Services Manually

Frontend:

```bash
cd Project
npm install
npm run dev
```

Backend API:

```bash
cd Project/python_services
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Temporal worker:

```bash
cd Project/python_services
.venv\Scripts\activate
python worker.py
```

You will also need a reachable Temporal server plus the environment variables described in `Project/.env.example`.

## Environment Setup

- Frontend/shared env template: `Project/.env.example`
- Docker uses: `Project/.env.local`
- Backend settings load a local `.env` file when running directly from `Project/python_services`

Typical local setup is:

1. Copy `Project/.env.example` to `Project/.env.local`.
2. For direct backend runs, copy the same values into `Project/python_services/.env`.
3. Fill in required keys for Supabase, OpenAI/Anthropic, fal.ai, storage, Telegram, and any self-hosted service URLs.

## Development Commands

Frontend:

```bash
cd Project
npm run dev
npm run build
npm run lint
npm run type-check
npm test
```

Backend:

```bash
cd Project/python_services
pytest
python worker.py
uvicorn main:app --reload --port 8000
```

## What Is Implemented

- Next.js landing page, dashboard, and auth screen
- Frontend proxy routes for workflow and content endpoints
- FastAPI routes for workflows, content views, media generation, accounts, and analytics
- Temporal workflow orchestration for weekly marketing, post publishing, and engagement syndicate flows
- Activity modules for strategy, approval, distribution, media, and video work
- Jest tests for dashboard and frontend proxy routes
- Pytest coverage for workflow/content APIs, distribution activities, and selected services

## Known Gaps

- `README.md` and older project docs historically drifted from the implementation; check `Docs/` for architecture/background and the service-specific READMEs for current usage.
- `/api/personas`, `/api/accounts/connect/{platform}`, `/api/accounts/list`, and `/api/analytics/summary` are not fully implemented yet.
- The dashboard currently works best as a workflow monitor and approval surface; richer scheduled-post and analytics views are still thin.
- External behavior depends on third-party or self-hosted service contracts such as OpenClaw, Postiz, GrowChief, fal.ai, and PlayHT.

## Documentation Map

- `Docs/START_HERE.md`
- `Docs/AI Influencer Factory Technical Blueprint.md`
- `Docs/Ally Dev - Note.md`
- `Docs/RESTRUCTURING_SUMMARY.md`
- `Docs/VPS.md`
- `Project/README.md`
- `Project/python_services/README.md`
- `Project/supabase/README.md`

## Testing

Frontend tests:

```bash
cd Project
npm test
```

Backend tests:

```bash
cd Project/python_services
pytest
```
