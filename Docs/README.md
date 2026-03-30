# Documentation Guide

Last verified: 2026-03-30 (UTC)

This folder is the canonical documentation set for the repo as it exists today.

## Recommended Reading Order

1. [START_HERE.md](./START_HERE.md) for local setup and day-to-day development
2. [ARCHITECTURE.md](./ARCHITECTURE.md) for the big-picture system model
3. [REPOSITORY_MAP.md](./REPOSITORY_MAP.md) for where code lives
4. [FRONTEND.md](./FRONTEND.md) for the Next.js app, dashboard flows, and proxy layer
5. [BACKEND_API.md](./BACKEND_API.md) for FastAPI routes, auth, and service boundaries
6. [WORKFLOWS_AND_AUTOMATION.md](./WORKFLOWS_AND_AUTOMATION.md) for Temporal workflows, activities, approval paths, and the current short-video lane
7. [PREPRODUCTION_VIDEO_V1.md](./PREPRODUCTION_VIDEO_V1.md) for the Telegram `video-ai` concept-to-package contract
8. [INTEGRATIONS.md](./INTEGRATIONS.md) for OpenClaw, Postiz, GrowChief, Telegram, AI/media providers, storage, and proxies
9. [db.md](./db.md) for the application database and storage ownership model
10. [ENVIRONMENT_REFERENCE.md](./ENVIRONMENT_REFERENCE.md) for the env contract used across local and production runtime
11. [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) for VPS deployment, migrations, smoke checks, and production incident triage

## How To Use This Set

- start with `START_HERE.md` if you need the project running
- start with `ARCHITECTURE.md` if you need to understand the product and runtime split
- start with `REPOSITORY_MAP.md` if you are onboarding into the codebase
- use `FRONTEND.md`, `BACKEND_API.md`, and `WORKFLOWS_AND_AUTOMATION.md` as the implementation reference set
- use `PREPRODUCTION_VIDEO_V1.md` when changing the Telegram `video-ai` collection and package contract
- use `db.md` and `ENVIRONMENT_REFERENCE.md` when changing persistence or config
- use `OPERATIONS_RUNBOOK.md` for anything production-facing

## Focused Reference

- [ADR-001-pipeline-error-handling.md](./ADR-001-pipeline-error-handling.md) for the current decision record on short-video failure handling

## Related Entry Points Outside This Folder

- [../README.md](../README.md) for the top-level overview
- [../Project/README.md](../Project/README.md) for the frontend-focused quick guide
- [../Project/python_services/README.md](../Project/python_services/README.md) for the backend-focused quick guide
- [../Project/supabase/README.md](../Project/supabase/README.md) for SQL bootstrap and migration workflow
