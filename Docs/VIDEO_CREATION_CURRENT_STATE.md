# Video Creation Current State

Last verified: 2026-04-20 (UTC)

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

What is live now:

- setup uses real `POST /api/customer/review-engine/source/validate`
- setup stores validated `page_review_data` in frontend state
- create-plan uses real `POST /api/customer/review-engine/jobs`
- create-plan forwards validated `page_review_data` so backend can skip duplicate source review on the happy path
- review step uses real plan patch/approve/upload flows

Important detail:

- `CreateVideoTab` is no longer only a presentation shell for setup/review actions
- the backend create-plan route is still synchronous overall, but it now avoids one duplicated review pass and runs per-persona generation concurrently

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
- return `normalized_url`, `page_title`, `suggested_objective`, `visible_features`, and full `page_review_data`

### 2. Review-engine job creation

Route:

- `POST /api/customer/review-engine/jobs`

Backend path:

- `api/customer.py` -> `AppReviewStudioService.create_jobs()`

Behavior:

- reuse `page_review_data` from setup when available
- fall back to live source review only if cached/validated payload is missing or invalid
- generate script data from the review plan
- create campaign draft data
- persist a `video_render_plans` row
- return review-engine job payloads to the frontend
- process target personas concurrently instead of strictly sequentially

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

### Backend contract status

Current request contract is partially aligned.

Resolved alignment:

- frontend modes are mapped into backend execution modes through the adapter
- validated `page_review_data` now flows from setup into create-plan
- `creative_preferences` flow into create-plan and plan persistence

Remaining mismatch areas:

- optional dashboard fields like `brief` are still UI-only
- background, movement, gesture, and music are only partially represented through `creative_preferences`
- `ai_remote` is still intentionally unsupported in backend submit flow

## Known Gaps And Bugs

### Dashboard wiring gap

- the old `LiveFeedTab` still exists, but setup/review actions are now wired in `CreateVideoTab`
- long-lived render/publish behavior still needs careful end-to-end verification in the new tab

### Setup latency and timeout risk

- `source/validate` is intentionally expensive because it performs real content review, not only URL normalization
- `jobs` previously duplicated the same source review and was a major latency multiplier
- that duplicated review pass is now removed on the normal validated-setup path
- create-plan can still be slow in worst-case environments because AI generation remains synchronous inside the request

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

1. Finish hardening the new `CreateVideoTab` around polling, publish, and failure-state visibility.
2. Decide which optional setup fields belong in the persisted backend contract.
3. Consider moving create-plan to a true async batch model if upstream timeouts still occur.
4. Fix `video_render_plans` persistence bugs before relying on the new web flow for all cases.
5. Either remove the dead manual-upload path or finish the missing job-type and approval handling.

## Related Docs

- [FRONTEND.md](./FRONTEND.md)
- [BACKEND_API.md](./BACKEND_API.md)
- [WORKFLOWS_AND_AUTOMATION.md](./WORKFLOWS_AND_AUTOMATION.md)
- [db.md](./db.md)
- [CREATE_VIDEO_SHARED_CONTRACT_UPDATE_2026-04-20.md](./CREATE_VIDEO_SHARED_CONTRACT_UPDATE_2026-04-20.md)
