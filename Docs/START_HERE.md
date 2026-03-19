# Start Here

Last verified: 2026-03-20 (Asia/Bangkok)

This is the practical setup guide for getting the project running from zero on a local machine.

If you only read one file before starting the repo, read this one.

## What This Repo Contains

The project has three main local runtimes:

- frontend: Next.js app in `Project/`
- backend API: FastAPI app in `Project/python_services/`
- worker/infra: Temporal worker plus supporting services such as Temporal, Postgres, and Redis

If your goal is VPS rollout rather than local boot, jump to `Docs/VPS_ZERO_TO_PRODUCTION_GUIDE.md` and then `Docs/OPERATIONS_RUNBOOK.md`.

Important:

- the backend and worker are designed around Python `3.11`
- the backend Python environment should live in `Project/python_services/.venv`
- do not use the root `Project/.venv` for the backend
- the backend can now start without Temporal, but workflow actions will not work until Temporal is running

## Choose Your Starting Path

Use one of these paths depending on what you want to do:

1. UI only
   Best if you just want to see the frontend shell.

2. UI + backend API
   Best if you want the dashboard and API routes running locally, even if Temporal is still offline.

3. Full local stack
   Best if you want workflows, worker execution, and the supporting services.

## Prerequisites

Install these first:

- Node.js `18+`
- npm
- Python `3.11`
- Docker Desktop

Recommended on Windows:

- PowerShell
- Python path available at:
  `C:\Users\boizb\AppData\Local\Programs\Python\Python311\python.exe`

## Repo Layout You Will Actually Use

- [README.md](/e:/Projects/Works/AI-Influencer-TripC/README.md)
- [Project/README.md](/e:/Projects/Works/AI-Influencer-TripC/Project/README.md)
- [Project/python_services/README.md](/e:/Projects/Works/AI-Influencer-TripC/Project/python_services/README.md)
- [Docs/OPERATIONS_RUNBOOK.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/OPERATIONS_RUNBOOK.md)

Helpful runtime entry points:

- [Project/run-backend.cmd](/e:/Projects/Works/AI-Influencer-TripC/Project/run-backend.cmd)
- [Project/run-worker.cmd](/e:/Projects/Works/AI-Influencer-TripC/Project/run-worker.cmd)
- [Project/python_services/main.py](/e:/Projects/Works/AI-Influencer-TripC/Project/python_services/main.py)
- [Project/python_services/worker.py](/e:/Projects/Works/AI-Influencer-TripC/Project/python_services/worker.py)

## Step 1: Create the Frontend Env File

From the repo root:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC
Copy-Item .\Project\.env.example .\Project\.env.local
```

Then edit [Project/.env.local](/e:/Projects/Works/AI-Influencer-TripC/Project/.env.local).

For a local boot, the most important values are:

- `PYTHON_BACKEND_URL=http://localhost:8000`
- `TEMPORAL_ADDRESS=localhost:7233`
- `POSTIZ_API_URL=http://localhost:3100`
- `GROWCHIEF_API_URL=http://localhost:3200`

Notes:

- `Project/python_services/config/settings.py` now falls back to `../.env.local`, so the backend can use the repo-level env file directly.
- You do not need a separate `Project/python_services/.env` unless you specifically want one.

## Step 2: Install Frontend Dependencies

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
npm install
```

## Step 3: Create the Backend Python 3.11 Environment

This is the correct backend venv setup:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project\python_services
C:\Users\boizb\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Important:

- use `Project/python_services/.venv`
- do not install backend dependencies into `Project/.venv`

## Fastest Path A: Run the Frontend Only

Use this if you just want to examine the UI.

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
npm run dev
```

Open:

- `http://localhost:3000`

What to expect:

- the frontend will load
- API-backed widgets may show empty or degraded states if the backend is not running

## Fastest Path B: Run Frontend + Backend API

This is the best day-to-day dev starting point.

Backend terminal:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
.\run-backend.cmd
```

Frontend terminal:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
npm run dev
```

Open:

- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/docs`

What to expect:

- the backend now starts even if Temporal is offline
- workflow-triggering actions will still need Temporal
- dashboard read paths can degrade instead of killing the API

## Full Path C: Start the Minimal Workflow Infrastructure

If you want workflow execution to work, Temporal must be available at `localhost:7233`.

From the repo root:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC
docker compose up -d postgres temporal redis
```

Then start the backend:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
.\run-backend.cmd
```

Then start the worker:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
.\run-worker.cmd
```

Then start the frontend:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
npm run dev
```

URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- backend docs: `http://localhost:8000/docs`
- Temporal UI: `http://localhost:8080`

## Full Path D: Start the Entire Docker Stack

If you want the whole local platform:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC
docker compose up --build
```

Main URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- Temporal UI: `http://localhost:8080`
- OpenClaw Mission Control: `http://localhost:8081`
- ChatGPT connector: `http://localhost:8010`
- Postiz: `http://localhost:3100`
- GrowChief: `http://localhost:3200`

Stop it with:

```powershell
docker compose down
```

## Recommended Daily Dev Flow

For most work, use this order:

1. start Docker Desktop
2. start `postgres`, `temporal`, and `redis`
3. start backend with [run-backend.cmd](/e:/Projects/Works/AI-Influencer-TripC/Project/run-backend.cmd)
4. start worker with [run-worker.cmd](/e:/Projects/Works/AI-Influencer-TripC/Project/run-worker.cmd) if your task needs workflows
5. start frontend with `npm run dev`

## Health Checks

Use these to confirm the system is really up:

Frontend:

```powershell
curl http://localhost:3000
```

Backend:

```powershell
curl http://localhost:8000/health
```

Temporal port:

```powershell
netstat -ano | findstr :7233
```

## Common Problems

### 1. `Could not import module "main"`

Cause:

- you started `uvicorn main:app` from `Project/` instead of `Project/python_services/`

Fix:

- use [run-backend.cmd](/e:/Projects/Works/AI-Influencer-TripC/Project/run-backend.cmd)
- or `cd Project/python_services` before running `uvicorn main:app`

### 2. `ModuleNotFoundError: No module named 'temporalio'`

Cause:

- backend dependencies were not installed into `Project/python_services/.venv`

Fix:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project\python_services
C:\Users\boizb\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Backend starts, then logs Temporal connection refused

Cause:

- Temporal is not running on `localhost:7233`

Fix:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC
docker compose up -d postgres temporal redis
```

### 4. Worker fails with Temporal connection refused

Cause:

- same as above: Temporal is offline

Fix:

- start the minimal Docker infrastructure first

### 5. Frontend shows many `/api/... 500` errors

Cause:

- backend is not running
- or backend was started from the wrong folder

Fix:

- start the backend through [run-backend.cmd](/e:/Projects/Works/AI-Influencer-TripC/Project/run-backend.cmd)
- keep `PYTHON_BACKEND_URL=http://localhost:8000`

### 6. PowerShell says `Unable to initialize device PRN`

Cause:

- PowerShell split a Python `-c` command at `;`

Fix:

- quote the whole Python snippet:

```powershell
.\.venv\Scripts\python.exe -c "import worker; print('worker_import_ok')"
```

### 7. `DEBUG=release` crashes settings

Current behavior:

- backend settings now normalize `release`, `prod`, and `production` to `false`

Recommended value:

```text
DEBUG=true
```

## Verification Commands

Backend targeted tests:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project\python_services
.\.venv\Scripts\python.exe -m pytest tests\test_media_api.py tests\test_chatgpt_connector_auth.py tests\test_chatgpt_connector_tools.py tests\test_chatgpt_connector_app.py tests\test_quota_monitor_service.py tests\test_quota_api.py tests\test_proxy_manager_service.py tests\test_accounts_api.py tests\test_services.py tests\test_content_api.py tests\test_analytics_api.py tests\test_distribution_activities.py tests\test_workflows_api.py tests\test_worker_imports.py
```

Frontend targeted tests:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC\Project
npm test -- --runInBand app/api/routes.test.ts app/dashboard/page.test.tsx
```

Compose validation:

```powershell
cd E:\Projects\Works\AI-Influencer-TripC
docker compose -f docker-compose.yml config
docker compose -f docker-compose.production.yml config
```

## What Works Without Temporal

These still work:

- frontend shell
- backend startup
- backend docs page
- many read-only dashboard surfaces in degraded mode

These still require Temporal:

- starting workflows
- workflow approval signals
- retrying failed publish workflows
- running the worker for real workflow execution

## What To Read Next

After this file:

1. [CURRENT_REPO_STATUS.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/CURRENT_REPO_STATUS.md)
2. [OPERATIONS_RUNBOOK.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/OPERATIONS_RUNBOOK.md)
3. [AI Influencer Factory Technical Blueprint.md](/e:/Projects/Works/AI-Influencer-TripC/Docs/AI%20Influencer%20Factory%20Technical%20Blueprint.md)
