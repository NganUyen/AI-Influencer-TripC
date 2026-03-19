# AI Influencer Factory Backend

This directory contains the FastAPI application, Temporal worker, workflow definitions, activity modules, service integrations, tests, and helper scripts for the backend side of the project.

## What Lives Here

```text
python_services/
|-- activities/         Workflow activity implementations
|-- agents/             OpenClaw-related agent definitions
|-- api/                FastAPI route modules
|-- config/             Settings and runtime configuration
|-- scripts/            Persona setup and smoke-test helpers
|-- services/           External service wrappers
|-- tests/              Pytest suite
|-- workflows/          Temporal workflows
|-- main.py             FastAPI app entry point
|-- worker.py           Temporal worker entry point
`-- requirements.txt    Python dependencies
```

## Implemented Surfaces

FastAPI routes currently mounted in `main.py`:

- `/health`
- `/api/workflows/start-weekly`
- `/api/workflows/approve/{workflow_id}`
- `/api/workflows/status/{workflow_id}`
- `/api/workflows/list`
- `/api/workflows/cancel/{workflow_id}`
- `/api/content/list`
- `/api/content/stats`
- `/api/media/generate/image`
- `/api/media/generate/video`
- `/api/media/generate/audio`
- `/api/media/voices`
- `/api/media/storage/list`
- `/api/accounts/stealth/create`
- `/api/accounts/stealth/{account_id}`
- `/api/accounts/connect/{platform}` (placeholder response)
- `/api/accounts/list` (placeholder response)
- `/api/analytics/engagement/{platform}/{post_id}`
- `/api/analytics/post/{post_id}`
- `/api/analytics/summary` (placeholder response)
- `/api/personas`

## Workflows

`workflows/weekly_marketing_workflow.py` currently defines:

- `WeeklyMarketingWorkflow`
- `PostPublishingWorkflow`
- `EngagementSyndicateWorkflow`

The weekly workflow is the main implemented orchestration path:

1. Generate strategy
2. Request Telegram approval
3. Wait for a Temporal signal
4. Generate media
5. Upload assets
6. Schedule posts
7. Start child publishing workflows
8. Trigger engagement tracking

## Setup

### Prerequisites

- Python 3.11
- A reachable Temporal server
- Environment variables populated from `Project/.env.example`

### Local Environment

From this directory:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `python_services/.env` with the values needed by `config/settings.py`. A practical way to do that is to copy values from `Project/.env.example`.

The settings loader also falls back to `Project/.env.local` when you run commands from `python_services`, so you can use the repo-level env file directly if that is where you keep your local secrets.

Important:

- `DEBUG` must be a boolean value such as `true` or `false`. Values like `release` will cause settings validation to fail before the app or tests start.
- The local backend and worker environment should use Python `3.11` to match the Docker image and pinned dependency set. Python `3.13` currently fails on a clean install because several dependencies in this repo are pinned for the 3.11 runtime.

## Run the API

```bash
cd Project/python_services
.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

Docs will be available at `http://localhost:8000/docs`.

From the `Project` root on Windows, you can also use:

```bash
run-backend.cmd
```

## Run the Worker

```bash
cd Project/python_services
.venv\Scripts\activate
python worker.py
```

The worker expects Temporal plus the required external service configuration to be reachable.

From the `Project` root on Windows, you can also use:

```bash
run-worker.cmd
```

## Tests

Run the backend test suite with:

```bash
cd Project/python_services
pytest
```

Current tests cover workflow APIs, content APIs, selected service wrappers, and distribution activities.

## Helper Scripts

The `scripts/` folder includes smoke and setup helpers for areas that are still integration-heavy, including:

- persona setup/check scripts
- strategy smoke tests
- storage smoke tests
- script/TTS/HeyGen smoke tests
- content assembly smoke tests

Use them as targeted integration helpers once the related environment variables are configured.

## Current Gaps

- Persona endpoints in `main.py` still return placeholder data.
- Account connect/list endpoints are not fully wired to persistence yet.
- Analytics summary is still a stub.
- End-to-end behavior depends heavily on external services such as OpenClaw, Postiz, GrowChief, fal.ai, PlayHT, Telegram, and R2-compatible storage.

## Local Docker Stack

The repository root includes `docker-compose.yml`, which can run the backend API and worker alongside PostgreSQL, Temporal, Redis, OpenClaw, Mission Control, Postiz, GrowChief, and the frontend.

From the repo root:

```bash
docker-compose up -d --build
```
