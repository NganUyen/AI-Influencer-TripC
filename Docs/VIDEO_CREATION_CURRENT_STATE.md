# Video Creation Current State

Last verified: 2026-04-18 (UTC)

This is the current-state reference for create-video behavior across the web dashboard, Telegram, backend review-engine routes, and the production workflow handoff.

## Scope

There are two real create-video entry surfaces in the repo today:

- dashboard web flow under `Create Video`
- Telegram `video-ai` pre-production flow

Both eventually target `ShortVideoWorkflow`.

## Current Surfaces

### Web dashboard flow

Main files:

- `Project/components/dashboard/CreateVideoTab.tsx`
- `Project/components/dashboard/create-video/CreateVideoSetupStep.tsx`
- `Project/components/dashboard/LiveFeedTab.tsx`
- `Project/components/customer-dashboard.tsx`

What is live now:

- dashboard preload calls `GET /api/customer/review-engine/setup`
- dashboard preload calls `GET /api/customer/review-engine/jobs`
- new setup UI calls `POST /api/customer/review-engine/source/validate`

What is still placeholder/demo in the new dashboard tab:

- persona plan generation cards
- review approval state
- render progress state
- publish step

Important detail:

- the old `LiveFeedTab` still contains the real wired client for `review-engine/jobs`, `review-engine/plans`, upload, and publish actions
- the new `CreateVideoTab` is mostly a presentation shell around local state

### Telegram flow

Main files:

- `Project/python_services/api/telegram_webhook.py`
- `Project/python_services/skills/video_ai.py`
- `Project/python_services/workflows/short_video_workflow.py`

What is live now:

- `video-ai` is the active Telegram create-video entry
- Telegram flow builds pre-production artifacts, then starts `/api/workflows/start-video`
- current flow supports the approved-package handoff into `ShortVideoWorkflow`

## Actual Backend Flow

### 1. Source review

Route:

- `POST /api/customer/review-engine/source/validate`

Backend path:

- `api/customer.py` -> `WebsiteReviewService.review_url()`

Behavior:

- normalize URL
- fetch visible page content through browser/Jina-backed review helpers
- return `normalized_url`, `page_title`, `suggested_objective`, and `visible_features`

### 2. Review-engine job creation

Route:

- `POST /api/customer/review-engine/jobs`

Backend path:

- `api/customer.py` -> `AppReviewStudioService.create_jobs()`

Behavior:

- review source page
- generate script data from the review plan
- create campaign draft data
- persist a `video_render_plans` row
- return review-engine job payloads to the frontend

### 3. Plan storage and approval

Routes:

- `GET/POST /api/customer/review-engine/plans`
- `GET/PATCH/DELETE /api/customer/review-engine/plans/{plan_id}`
- `POST /api/customer/review-engine/plans/{plan_id}/approve`

Backend path:

- `VideoPlanningService`
- `AppReviewStudioService.start_workflow_from_plan()`

Behavior:

- store or patch per-persona plan state
- approval triggers workflow startup
- successful approval starts `ShortVideoWorkflow`

### 4. Production workflow

Main workflow:

- `Project/python_services/workflows/short_video_workflow.py`

High-level steps:

1. resolve script or approved-package input
2. generate audio and scene assets
3. optionally generate talking-head video
4. assemble final split-screen video
5. deliver preview through Telegram
6. wait for publish/save decision

## Frontend Input Contract Today

### New dashboard setup state

Defined in:

- `Project/types/video-planning.ts`

Collected in the UI:

- `sourceUrl`
- `objective`
- `selectedPersonaIds`
- `selectedMode`
- `brief`
- `selectedBackground`
- `selectedMovementStyle`
- `selectedMusicMood`

Shown in UI but not persisted in setup state:

- gesture intensity slider
- music volume slider

### Backend contract mismatch

Current backend request models for review-engine jobs do not fully match the new dashboard setup state.

Important mismatches:

- frontend modes are `ai_auto | ai_remote | human_phone`
- backend execution modes are `ai_autonomous | user_upload`
- optional dashboard fields like `brief`, `background`, `movement`, and `music` are not part of the review-engine request model

## Known Gaps And Bugs

### Dashboard wiring gap

- new `CreateVideoTab` only performs real source validation
- real create/review/render/publish actions still live in `LiveFeedTab`

### Plan persistence issues

- `video_render_plans.persona_id` is schema-level UUID-backed, but some service code still treats persona identifiers as text slugs
- `publish_settings` are passed into plan creation but not inserted into the table
- `approved_at` is set by approval code but filtered out by the generic update whitelist

### Manual upload lane gap

- review-engine upload endpoints exist
- service code expects an `app_review_upload` job type for manual upload
- current job creation path does not create that job type
- approval path still assumes autonomous workflow start

### Script fallback bug

- when script generation fails in `AppReviewStudioService.create_jobs()`, code can set `script_payload = None`
- later code still reads `script_payload.get(...)`

## Recommended Next Work

1. Wire the new `CreateVideoTab` to real `review-engine/jobs`, `review-engine/plans`, and approval endpoints.
2. Unify the mode contract between frontend and backend.
3. Decide which optional setup fields belong in the persisted backend contract.
4. Fix `video_render_plans` persistence bugs before relying on the new web flow.
5. Either remove the dead manual-upload path or finish the missing job-type and approval handling.

## Related Docs

- [FRONTEND.md](./FRONTEND.md)
- [BACKEND_API.md](./BACKEND_API.md)
- [WORKFLOWS_AND_AUTOMATION.md](./WORKFLOWS_AND_AUTOMATION.md)
- [db.md](./db.md)
