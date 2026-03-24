# AI Influencer Factory Backend

This directory contains the FastAPI application, Temporal worker, workflows, activities, service integrations, and tests that power both the customer app and the internal ops surface.

## What Lives Here

```text
python_services/
|-- activities/         Workflow activity implementations
|-- agents/             OpenClaw-related agent configuration
|-- api/                FastAPI route modules
|-- chatgpt_connector/  ChatGPT-facing OpenClaw connector
|-- config/             Settings and runtime configuration
|-- scripts/            Smoke and setup helpers
|-- services/           External service wrappers and persistence logic
|-- tests/              Pytest suite
|-- workflows/          Temporal workflow definitions
|-- main.py             FastAPI app entry point
`-- worker.py           Temporal worker entry point
```

## Current API Surface

Route groups mounted in `main.py`:

- `/health`
- `/api/workflows/*`
- `/api/media/*`
- `/api/accounts/*`
- `/api/analytics/*`
- `/api/content/*`
- `/api/quota/*`
- `/api/webhooks/*`
- `/api/personas/*`
- `/api/customer/*`

The `/api/customer/*` routes back the customer workspace for:

- brand profile management
- social account connect/disconnect scaffolding
- assistant threads and messages
- campaign creation, approval, and launch
- customer approvals and content views

## Current Workflow Surface

Registered worker workflows:

- `WeeklyMarketingWorkflow`
- `PostPublishingWorkflow`
- `EngagementSyndicateWorkflow`
- `ShortVideoWorkflow`
- `DailyStoryWorkflow`

The weekly workflow remains the main durable orchestration lane. The short-video and daily-story flows are present and wired into the worker, but still depend heavily on live provider configuration and operator validation.

## Setup

Prerequisites:

- Python `3.11`
- reachable Temporal server for workflow execution
- env values populated from `Project/.env.example`

Create the local environment:

```bash
cd Project/python_services
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The settings loader can read either:

- `Project/python_services/.env`
- `Project/.env.local`

## Run The API

```bash
cd Project/python_services
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

## Run The Worker

```bash
cd Project/python_services
source .venv/bin/activate
python worker.py
```

## Tests

Run the backend suite with:

```bash
cd Project/python_services
pytest
```

Current tests cover customer APIs, connector auth/tools, quota monitoring, content/workflow routes, distribution logic, and selected services.

## Current Limitations

- production-grade behavior still depends on external services such as OpenClaw, Postiz, GrowChief, Telegram, fal.ai, Google TTS, and HeyGen
- customer social OAuth requires real provider registrations and secrets outside the repo
- some publish paths still rely on the Postiz-backed bridge instead of direct native platform adapters
- manual full-stack acceptance is still required after infra or provider changes

## Related Docs

- [../../Docs/README.md](../../Docs/README.md)
- [../../Docs/CURRENT_REPO_STATUS.md](../../Docs/CURRENT_REPO_STATUS.md)
- [../../Docs/OPERATIONS_RUNBOOK.md](../../Docs/OPERATIONS_RUNBOOK.md)
