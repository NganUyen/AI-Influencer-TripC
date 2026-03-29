# Video AI Influencer Pipeline Status

Last verified: 2026-03-29 (UTC)

This document records the real repo status of the Telegram-driven Video AI Influencer pipeline after the March 29, 2026 audit and repair pass.

It replaces any claim that the lane was already fully complete before the approved-package handoff was repaired.

## Scope

This status covers the split-screen AI influencer video lane in `Project/python_services/`:

- Telegram `video-ai` pre-production flow
- `CreativeDirectorService` concept and beat planning
- approved-package handoff into production
- `ShortVideoWorkflow`
- top-half media generation and browser capture
- bottom-half TTS / talking-head path
- final split-screen assembly

## Executive Summary

The pipeline is now materially more complete than it was before this repair pass.

Before the fixes:

- Telegram could reach `ApprovedProductionPackage`, but stopped there
- production could run through the old manual script-approval path
- the approved-package production path existed only partially and was broken by contract drift and missing wiring

After the fixes:

- Telegram `video-ai` can hand off an approved package into `/api/workflows/start-video`
- `/api/workflows/start-video` can pass `approved_package` into `ShortVideoWorkflow`
- the worker registers the approved-package activity
- `ScriptService` now consumes the real `ApprovedProductionPackageContract`
- browser-capture storage uses the correct upload path
- per-scene timing now propagates from beat durations into video assembly
- internal test coverage for this lane is green

Important boundary:

- the codebase is now in a strong repo-green state for this lane
- final production sign-off still requires one real staging E2E run against deployed API + Temporal + storage + provider credentials

## Status Before The Repair Pass

The repo had a stable pre-production lane but an incomplete production handoff.

What worked before:

- Telegram session and skill flow
- persona selection and scoping
- `ConceptBrief` generation
- `BeatSheet` generation
- concept and beat approvals
- in-session `ApprovedProductionPackage`
- the old `ShortVideoWorkflow` path without approved package

What was broken before:

- `ScriptService.generate_script_from_package()` expected the wrong package and beat fields
- `generate_script_from_approved_package_activity` existed but was not registered in the worker
- Telegram `video-ai` stopped at `package_ready` and did not start production
- `/api/workflows/start-video` did not accept or forward `approved_package`
- browser-capture used the wrong storage method
- browser-capture bypassed canonical media persistence
- beat timing was discarded and flattened to constant durations
- `video-ai` persona fetch omitted `owner_key`
- dead creative workflow/activity code remained in the tree

In practical terms, the pre-production lane was real, but the approved-package production lane was not reliable enough for actual use.

## Status After The Repair Pass

### Approved-package production handoff

The pipeline now has a real approved-package path:

1. Telegram `video-ai` collects and approves pre-production inputs
2. `CreativeDirectorService` produces:
   - `ConceptBrief`
   - `BeatSheet`
   - `ApprovedProductionPackage`
3. `VideoAISkill` calls `/api/workflows/start-video`
4. `/api/workflows/start-video` forwards `approved_package` into `ShortVideoWorkflow`
5. `ShortVideoWorkflow` invokes `generate_script_from_approved_package_activity`
6. `ScriptService.generate_script_from_package()` builds a valid `ScriptContract`
7. media generation / browser capture runs
8. TTS and optional talking-head path runs
9. split-screen assembly runs with scene durations

### Key repairs

#### 1. Contract mapping repaired

`services/script_service.py` now reads:

- `package["beat_sheet"]`
- `bottom_half_message`
- `overlay_text`
- `top_half_target`
- `top_half_capture_hint`
- `duration_sec`

This replaced the old broken references to:

- `approved_beat_sheet`
- `narration_draft`
- `onscreen_text`
- `visual_concept`
- `duration_hint`

#### 2. Worker registration repaired

`worker.py` now imports and registers `generate_script_from_approved_package_activity`, so the approved-package branch is actually callable by Temporal.

#### 3. Telegram now hands off to production

`skills/video_ai.py` no longer stops at a dead-end package-ready state.

Instead, when the package is complete, it posts to `/api/workflows/start-video` and stores the result in the skill output/session artifacts.

`services/telegram_renderer.py` was updated so the user-facing completion state reflects workflow start success or failure, rather than always claiming production has not started.

#### 4. API payload now supports approved packages

`api/workflows.py` now includes `approved_package` in `StartVideoRequest` and forwards it into workflow args.

This is the main API bridge between pre-production and production.

#### 5. Browser capture storage path repaired

`activities/media_activities.py` no longer calls the non-existent `upload_file()` path and now uses the correct media persistence flow.

The browser-capture lane also received a defensive `None` check on upload results.

#### 6. Timing now survives production

Beat durations are no longer discarded.

The pipeline now carries timing from:

- `BeatContract.duration_sec`
- scene timestamp calculation in `ScriptService`
- `scene_durations` in the split-screen assembly input
- per-scene timing logic in `activities/video_activities.py`

#### 7. Persona fetch scoping repaired

`skills/video_ai.py` now passes `owner_key` when reading persona and readiness data, aligning the Telegram lane with scoped persona access.

#### 8. API validation tightened

`/api/workflows/start-video` now conditionally requires `heygen_avatar_id` when `talking_head_optional=False`.

This keeps validation aligned with actual workflow behavior without blocking fallback-friendly runs.

#### 9. Dead code cleaned up

The old creative workflow lane was not part of the real production path and was removed from active wiring. Stale creative activity imports were also cleaned up.

## Files Updated In The Repair Pass

Core implementation files:

- `Project/python_services/services/script_service.py`
- `Project/python_services/worker.py`
- `Project/python_services/api/workflows.py`
- `Project/python_services/skills/video_ai.py`
- `Project/python_services/services/telegram_renderer.py`
- `Project/python_services/activities/media_activities.py`
- `Project/python_services/activities/video_activities.py`
- `Project/python_services/services/contracts.py`

Cleanup:

- `Project/python_services/activities/__init__.py`
- deleted: `Project/python_services/activities/creative_activities.py`
- deleted earlier in the repair sequence: `Project/python_services/workflows/creative_to_video_workflow.py`

Validation tooling:

- `Project/python_services/scripts/e2e_video_ai_pipeline.py`

## Test Coverage Added Or Updated

The repair pass also updated tests so they validate the real contracts instead of stale fake schemas.

Updated or added tests:

- `Project/python_services/tests/test_script_service_top_half.py`
- `Project/python_services/tests/test_media_activities_top_half.py`
- `Project/python_services/tests/test_video_ai_preproduction.py`
- `Project/python_services/tests/test_telegram_renderer.py`
- `Project/python_services/tests/test_workflows_api.py`
- `Project/python_services/tests/test_media_storage_service.py`
- `Project/python_services/tests/test_e2e_video_ai_pipeline.py`

What these tests now cover:

- approved-package contract validity
- script generation from real beat fields
- browser-capture persistence branch
- Telegram production handoff behavior
- renderer behavior for workflow started / workflow failed states
- workflow API support for `approved_package`
- conditional `heygen_avatar_id` validation
- E2E script contract correctness and workflow status parsing

Current repo test state at the end of this pass:

- `185 passed`

## What Is Now True

These statements are now accurate:

- pre-production is real
- approved-package handoff into production is real in code
- the worker and API wiring are present
- Telegram no longer stops at package-ready as a dead end
- the pipeline has targeted regression coverage for the repaired path

## What Is Still Not Proven

These statements should not be made yet:

- "production-ready has been proven in a real deployed environment"
- "Telegram to final video has been validated end-to-end without mocks"

Why that boundary still matters:

- internal tests are green, but they still run inside repo-controlled conditions
- final sign-off requires a deployed environment with:
  - API server
  - Temporal server and worker
  - database and storage
  - real persona data
  - valid provider credentials

## Staging E2E Validation

The repo now contains a deploy-time validation script:

- `Project/python_services/scripts/e2e_video_ai_pipeline.py`

Purpose:

- verify persona readiness via API
- fetch persona via API
- start `/api/workflows/start-video` with a valid approved package
- verify workflow status through the workflow status API

Example usage:

```powershell
cd Project/python_services
python scripts/e2e_video_ai_pipeline.py --persona-id <persona_id> --owner-key telegram:<chat_id> --api-base <api_base>
```

This script is intended as a staging or post-deploy smoke test and should be kept until a stronger automated deployed integration test replaces it.

## Post-Deploy Runbook

Use this runbook after the PR is merged and the backend/worker have been redeployed.

### Preconditions

Confirm these are true in the deployed environment:

- API server is up
- Temporal server is up
- Temporal worker is up and running the current image/commit
- database and storage credentials are valid
- `INTERNAL_API_TOKEN` is available
- at least one persona exists that is intended for this lane

Recommended persona requirements:

- `status = ready`
- `tts_voice` is present
- `heygen_avatar_id` is present if you want to validate the talking-head-required path

### Step 1. Verify the deployed API is reachable

Example:

```powershell
curl -H "Authorization: Bearer <INTERNAL_API_TOKEN>" <api_base>/health
```

If this fails, do not continue with workflow validation yet.

### Step 2. Validate persona readiness only

Run the E2E script in validation mode first:

```powershell
cd Project/python_services
python scripts/e2e_video_ai_pipeline.py --persona-id <persona_id> --owner-key telegram:<chat_id> --api-base <api_base> --skip-workflow
```

Expected outcome:

- persona lookup succeeds
- readiness check succeeds
- API validation branch behaves as expected

Use this step to catch:

- wrong `owner_key`
- missing persona
- missing `tts_voice`
- missing `heygen_avatar_id` for strict talking-head validation
- auth token issues

### Step 3. Start the approved-package production path

When Step 2 passes, run the real workflow test:

```powershell
cd Project/python_services
python scripts/e2e_video_ai_pipeline.py --persona-id <persona_id> --owner-key telegram:<chat_id> --api-base <api_base> --timeout 120
```

Expected outcome:

- `/api/workflows/start-video` accepts the request
- a `workflow_id` is returned
- workflow state advances beyond `queued`

Healthy states include:

- `queued`
- `generating_script_from_package`
- `generating_assets`
- `assembling`
- `waiting_final_decision`
- `completed`

### Step 4. Inspect worker logs if the workflow does not advance

If the script reports failure or stalls, check:

- API logs
- worker logs
- Temporal UI for the workflow history

Focus on these failure classes first:

- contract validation errors
- activity registration errors
- media storage/upload errors
- provider credential errors
- persona readiness / missing fields

### Step 5. Confirm the user-visible Telegram outcome

For the real Telegram-driven lane, confirm:

- the `video-ai` flow reaches package approval
- Telegram reports that production started
- the workflow id or success/failure state is visible in the final Telegram completion message
- preview/follow-up messages arrive as expected for the workflow result

### Step 6. Sign-off rule

Treat the pipeline as deploy-verified only when all of the following are true:

- Step 2 passes
- Step 3 passes
- worker logs show no runtime contract/storage/activity failures
- Telegram UX reflects production start correctly
- at least one approved-package run completes successfully in the deployed environment

### Notes For PR / Redeploy

Use this exact sequence:

1. merge PR
2. redeploy API and worker together
3. run `--skip-workflow`
4. run full E2E workflow validation
5. inspect logs and Temporal history if needed
6. only then mark the lane as deploy-verified

Do not delete the E2E script during this rollout. Keep it in the repo as the current smoke-test tool for this lane until a stronger deployed integration test replaces it.

## Recommended Sign-Off Rule

Use this rule going forward:

- repo status: green
- pipeline status in code: repaired
- production sign-off: only after one successful deployed E2E run for the approved-package path

## Recommended Reading

Read these documents together:

1. `Docs/PREPRODUCTION_VIDEO_V1.md`
2. `Docs/VIDEO_AI_INFLUENCER_PIPELINE_STATUS_2026-03-29.md`
3. `Docs/WORKFLOWS_AND_AUTOMATION.md`
4. `Docs/OPERATIONS_RUNBOOK.md`
