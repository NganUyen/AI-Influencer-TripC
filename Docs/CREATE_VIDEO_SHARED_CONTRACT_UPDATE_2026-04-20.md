# Create Video Shared Contract Update

Last verified: 2026-04-20 (UTC)

This document summarizes the recent Step 2 refactor in the dashboard `Create Video` flow.

## Goal

The previous Step 2 UI mixed two different ideas:

- backend plans are created per persona
- the review UI exposed a pseudo-global contract seeded from only the first persona card

That created a mismatch between actual backend behavior and what users saw in the editor.

The updated goal is:

- one shared contract editor for users
- approval still remains per persona
- shared contract is authored in English
- selected persona lanes stay aligned to that shared contract while preserving persona-specific language metadata and execution path

## What Changed

### 1. Shared contract became the Step 2 source of truth

Step 2 no longer derives its editable contract from the first card only.

Instead:

- `CreateVideoTab.tsx` owns a dedicated `sharedContractDraft`
- the shared draft contains `scriptText` and `scenesText`
- save operations patch the same shared payload into every editable backend plan

Files:

- `Project/components/dashboard/CreateVideoTab.tsx`
- `Project/types/video-planning.ts`

### 2. Review UI is now explicitly split into two layers

Step 2 now has:

- `Shared Video Contract`
- `Persona Targets`

`Shared Video Contract` is the master English draft that users edit once.

`Persona Targets` shows the selected persona lanes and keeps these controls per persona:

- approve
- reject
- upload final video for human-phone lanes

This keeps the UX simple without pretending the backend stores only one plan record.

Files:

- `Project/components/dashboard/create-video/CreateVideoReviewStep.tsx`
- `Project/app/create-video.css`

### 3. Persona metadata is surfaced more clearly

Each persona target now exposes language metadata in the review UI.

This makes the shared-contract rule explicit:

- one English master contract
- multiple persona lanes
- each lane still carries persona-specific language identity

File:

- `Project/adapters/create-video-adapter.ts`

### 4. Divergent backend drafts are called out

If backend jobs arrive with different contract payloads across personas, Step 2 now detects that mismatch and shows a warning that the editor is becoming the single shared contract source.

This avoids silently masking a backend divergence.

## UX Improvements Added

The review screen now includes:

- a stronger shared-contract title and subtitle
- an explicit note that the contract is shared across all selected personas
- language summary text for selected persona lanes
- summary pills for persona count, language lanes, ready outputs, and upload-required lanes
- saved vs unsaved shared contract status
- a `Revert to backend draft` action
- a `Save shared edits` action that disables when there are no pending changes

## Logic Cleanup

The refactor also removed a few hidden risks in the Step 2 state model.

### Removed stale local override behavior

Previously, local card state could keep overriding refreshed backend values.

Now the shared draft is the intended contract authority for Step 2 editing, and persona cards stay synced to that shared draft.

### Safer persona action targeting

Approve/reject actions now target cards by `planId || jobId` instead of relying only on `planId`.

This reduces the risk of incorrect updates when `planId` is missing or duplicated in intermediate UI states.

### Cleaner save semantics

Saving no longer depends on whichever card happened to carry the latest local script preview.

All Step 2 save operations now serialize the shared contract draft directly.

## Session Fixes Added

The recent session also cleaned up the Step 2 control flow and made the development experience easier to debug.

### Dev-friendly toaster feedback

The create-video flow now uses more explicit toast messages for the main Step 2 actions:

- source validation / review-job creation warnings are shown with context
- shared-contract saves confirm that the draft was synced to editable persona plans
- approval success says how many persona plans moved forward
- partial approval failures call out which persona lanes stayed behind
- delete failures surface the plan IDs that could not be removed

### Reject now opens a confirmation modal

Reject is no longer a silent local state change.

Instead, the UI now asks the user whether they want to:

- keep editing the shared contract
- delete the selected plan(s) and return to Setup

This is intentionally softer than a hard delete flow, but still makes the destructive choice explicit.

### Deletion returns to Setup

When the user confirms delete, the frontend now calls the existing backend delete route for the selected plan IDs, clears Step 2 state, and returns the flow to Setup.

This gives users a fast recovery path if they do not want to keep a rejected plan.

### Approval failures are less opaque

The review-engine approve endpoint no longer collapses all downstream failures into a generic 500.

If workflow startup fails after the plan is approved, the API now logs the failure with plan/user context and returns a clearer 503 response that includes the exception type and message.

### Small UI polish for the confirm modal

The reject/delete modal was softened visually and in copy so it feels like a guided decision rather than a hard-stop error screen.

## Pipeline And Setup Improvements Added

The recent session also addressed the most immediate create-video setup latency problems.

### 1. Create-plan now reuses validated page review data

Previously, the flow did this twice:

- `POST /review-engine/source/validate`
- `POST /review-engine/jobs`

Both paths could trigger the same expensive `WebsiteReviewService.review_url()` pipeline.

The setup flow now keeps the validated `page_review_data` payload in frontend state and sends it back during job creation.

Backend `create_jobs()` now:

- accepts `page_review_data`
- validates/coerces it into `WebPageReviewContract`
- skips the second live website review when the payload is usable
- falls back to live review only when cached/validated payload is missing or invalid

This removes one full expensive review pass from the normal happy path.

### 2. Persona generation is now concurrent

The original create-plan path processed target personas sequentially.

That meant total request time scaled linearly with persona count because each persona could trigger:

- persona resolution
- AI script generation
- optional campaign creation
- plan persistence

The backend now runs persona job creation through `asyncio.gather(...)` so the per-persona work can happen concurrently instead of one-by-one.

This does not change the public result shape, but it reduces wall-clock latency for multi-persona plan creation.

### 3. Timing instrumentation was added around the heavy path

The backend now logs timing for:

- create-job prerequisites
- per-persona script generation
- per-persona completion
- total create-jobs duration

This gives a direct way to trace future slowdowns instead of debugging only from frontend symptoms like `504`.

### 4. Setup feature display is compact again

The source-validation UI no longer expands the full visible-feature list inline inside the setup card.

It now shows:

- extracted feature count in the setup section
- extracted feature count in the summary panel
- a `View details` action that opens a modal with the full extracted feature list

The modal reuses the existing create-video modal pattern rather than adding a new visual system.

## Files Touched

- `Project/components/dashboard/CreateVideoTab.tsx`
- `Project/components/dashboard/create-video/CreateVideoReviewStep.tsx`
- `Project/adapters/create-video-adapter.ts`
- `Project/types/video-planning.ts`
- `Project/app/create-video.css`
- `Project/python_services/api/customer.py`
- `Project/python_services/services/app_review_studio_service.py`
- `Project/components/dashboard/create-video/CreateVideoSetupStep.tsx`
- `Project/components/dashboard/create-video/CreateVideoSummaryPanel.tsx`
- `Project/lib/review-engine.ts`

## Verification

Commands run:

- `npm run build`
- `python -m py_compile "D:\coding\AI-Influencer-TripC\Project\python_services\api\customer.py" "D:\coding\AI-Influencer-TripC\Project\python_services\services\app_review_studio_service.py"`
- `npm run type-check`

Results:

- `npm run build`: passed
- `python -m py_compile ...`: passed
- `npm run type-check`: still fails, but only from pre-existing test/type issues outside this Step 2 refactor

Existing unrelated failures:

- `app/api/routes.test.ts`
- `app/auth/page.test.tsx`
- `app/dashboard/page.test.tsx`

## Remaining Known Gaps

This update only addressed the shared-contract review experience.

It does not yet fix:

- create-video polling errors being silent during interval refresh
- backend debug detail not being exposed through create-video routes
- deeper backend architectural mismatch where persistence is still per persona instead of a true single stored contract record
- long-running create-plan requests can still hit upstream timeout in worst-case environments because the endpoint is still synchronous overall, even though one heavy review pass was removed and per-persona generation is now concurrent

## Current Product Meaning

After this update, the intended user-facing model is:

- user edits one shared contract in English
- selected personas inherit that contract direction
- user approves persona lanes individually
- approved lanes continue into the existing backend workflow model

This is a UI and state-model alignment fix, not a backend data-model unification.

## Session Extension: Audio Library + Movement Overlay (2026-04-20)

The same session also introduced managed audio grouping and setup-summary demos for create-plan.

### Audio Asset Structure

Audio assets are now grouped for easier ownership and lookup:

- backend BGM library:
  - `Project/python_services/assets/audio_library/bgm/`
- backend movement library:
  - `Project/python_services/assets/audio_library/movement/`
- frontend demo BGM:
  - `Project/public/create-video-demos/bgm/`
- frontend demo movement:
  - `Project/public/create-video-demos/movement/`

Each backend group has its own `library.json` manifest.

### Backend Integration

`BackgroundMusicService` now supports grouped libraries:

- `list_tracks(group="bgm" | "movement")`
- `select_track(group=..., profile=..., max_duration_seconds=...)`
- backward-compatible fallback for legacy BGM manifest

`VideoAudioPolicyContract` now supports movement overlay controls:

- `movement_overlay_enabled`
- `movement_library_profile`
- `movement_overlay_volume`

`build_split_screen_video` now supports optional movement overlay:

- load movement track by profile
- mix narration/BGM base with movement audio through ffmpeg `amix`
- fail open if movement mix fails (continues with base audio)

### Frontend Setup + Summary

Create-plan setup now uses centralized options (`setup-options.ts`) for:

- background presets
- gesture style metadata
- music mood metadata

Summary panel now shows:

- selected background + movement + music labels
- audio demo player for selected music mood
- gesture preview + movement audio demo player
- selected persona chips

### API Surface

New authenticated route:

- `GET /api/customer/review-engine/audio-library`
  - returns grouped `bgm` and `movement` tracks (public metadata for UI)

### Verification Status (this extension)

- FE `npm run type-check`: fails due pre-existing unrelated test/type issues.
- Python pytest: not executable in current environment because no working Python runtime is available on PATH.
- Added/updated tests for new behavior:
  - `Project/python_services/tests/test_background_music_service.py`
  - `Project/python_services/tests/test_video_activities_bgm_fallback.py`
  - `Project/python_services/tests/test_app_review_studio_service.py`
