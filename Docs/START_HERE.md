# Start Here

Last verified: 2026-04-18 (UTC)

This is the fastest way to get the repo running locally without digging through old design docs.

## What This Repo Is

There are four main local runtimes:

- frontend: Next.js app in `Project/`
- backend API: FastAPI app in `Project/python_services/`
- worker: Temporal worker in `Project/python_services/worker.py`
- support stack: PostgreSQL, Temporal, Redis, OpenClaw, Postiz, GrowChief, and the connector via Docker Compose

## Prerequisites

- Node.js `18+`
- npm
- Python `3.11`
- Docker with Compose support

## First-Time Setup

1. Copy the env template:

```bash
cd /opt/ai-influencer/repo
cp Project/.env.example Project/.env.local
```

2. Fill in the minimum local values in `Project/.env.local`:

- `NEXT_PUBLIC_API_URL=http://localhost:3000`
- `PYTHON_BACKEND_URL=http://localhost:8000`
- `TEMPORAL_ADDRESS=localhost:7233`
- `OPENCLAW_API_URL=http://localhost:8081`
- `POSTIZ_API_URL=http://localhost:3100`
- `GROWCHIEF_API_URL=http://localhost:3200`

3. Install frontend dependencies:

```bash
cd /opt/ai-influencer/repo/Project
npm install
```

4. Create the backend virtualenv:

```bash
cd /opt/ai-influencer/repo/Project/python_services
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Database Model

The repo currently uses:

- Supabase Postgres as the long-lived application database
- Supabase Auth for customer sign-in and session validation
- local Postgres containers only for disposable local bootstrap and service databases

A fresh local Postgres volume can still bootstrap `Project/supabase/schema.sql` through Docker Compose for disposable development. For the canonical database model and migration rules, use [db.md](./db.md) and [../Project/supabase/README.md](../Project/supabase/README.md).

## Fastest Path A: Frontend Only

Use this when you only need to inspect the UI shell.

```bash
cd /opt/ai-influencer/repo/Project
npm run dev
```

Open `http://localhost:3000`.

## Fastest Path B: Frontend Plus Backend API

Use this for most UI and API work that does not require workflow execution.

Backend:

```bash
cd /opt/ai-influencer/repo/Project/python_services
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd /opt/ai-influencer/repo/Project
npm run dev
```

Open:

- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/docs`

Note: the backend can start without Temporal, but workflow-triggering actions will be degraded until Temporal is available.

## Path C: Minimal Workflow Infrastructure

Use this when you need actual Temporal-backed workflow execution.

Start the minimum Docker services:

```bash
cd /opt/ai-influencer/repo
docker compose up -d postgres temporal redis
```

Then run:

```bash
cd /opt/ai-influencer/repo/Project/python_services
source .venv/bin/activate
python worker.py
```

And in separate terminals:

```bash
cd /opt/ai-influencer/repo/Project/python_services
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

```bash
cd /opt/ai-influencer/repo/Project
npm run dev
```

## Path D: Full Local Stack

Use this when you need the whole platform running locally.

```bash
cd /opt/ai-influencer/repo
docker compose up -d --build
```

Main URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- backend docs: `http://localhost:8000/docs`
- Temporal UI: `http://localhost:8080`
- OpenClaw control UI: `http://localhost:8081`
- ChatGPT connector: `http://localhost:8010`
- Postiz: `http://localhost:3100`
- GrowChief: `http://localhost:3200`

Stop it with:

```bash
cd /opt/ai-influencer/repo
docker compose down
```

## Daily Dev Flow

For most work:

1. start `postgres`, `temporal`, and `redis`
2. start the backend API
3. start the worker only if your task needs workflows
4. start the frontend

## Quick Health Checks

```bash
curl -fsS http://localhost:3000/ >/dev/null
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8010/health
curl -fsS http://localhost:8081/healthz
```

## Common Gotchas

- use Python `3.11` for the backend virtualenv
- keep the backend venv in `Project/python_services/.venv`
- `DEBUG` must be a boolean like `true` or `false`
- workflow actions will fail or degrade if `TEMPORAL_ADDRESS` is unreachable
- real customer OAuth, Postiz, GrowChief, Telegram, and media providers need valid external credentials before those paths can be fully exercised

## Read Next

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [REPOSITORY_MAP.md](./REPOSITORY_MAP.md)
- [FRONTEND.md](./FRONTEND.md)
- [BACKEND_API.md](./BACKEND_API.md)
- [WORKFLOWS_AND_AUTOMATION.md](./WORKFLOWS_AND_AUTOMATION.md)
- [VIDEO_CREATION_CURRENT_STATE.md](./VIDEO_CREATION_CURRENT_STATE.md)
- [INTEGRATIONS.md](./INTEGRATIONS.md)
- [db.md](./db.md)
- [ENVIRONMENT_REFERENCE.md](./ENVIRONMENT_REFERENCE.md)
- [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)
- [../Project/README.md](../Project/README.md)
- [../Project/python_services/README.md](../Project/python_services/README.md)
