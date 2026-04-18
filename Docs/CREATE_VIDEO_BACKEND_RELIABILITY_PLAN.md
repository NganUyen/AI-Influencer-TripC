# Create Video Backend Reliability Plan

Last verified: 2026-04-18 (UTC)

This plan defines the schema and service fixes required to make the web create-video flow reliable.

## Summary

- `video_render_plans` must use external text `persona_id`, not a UUID foreign key.
- Plans must persist the data needed to survive refreshes, edits, approval, and workflow start.
- Job listing must merge pre-workflow plan state and active workflow state into one stable feed.
- The manual upload lane must become a real supported state in the same review-engine lane.

## Schema Decisions

### `video_render_plans.persona_id`

- Keep column name: `persona_id`
- Change storage type and usage to external text persona key
- Stop treating it as a UUID foreign key to `public.personas(id)`
- Resolve personas by:
  - `user_id` scope first
  - system/global persona fallback second

### Required new persisted fields

Add these plan-level persisted fields:

- `creative_preferences JSONB NOT NULL DEFAULT '{}'::jsonb`
- `page_review_data JSONB NOT NULL DEFAULT '{}'::jsonb`

Keep and correctly persist:

- `publish_settings`
- `approved_at`
- `workflow_id`
- timestamps

### Migration strategy

Implement one ordered migration that:

1. Adds `persona_id_text TEXT`
2. Backfills `persona_id_text` by joining existing `video_render_plans.persona_id` UUID values to `public.personas.id` and reading `public.personas.persona_id`
3. Fails the migration if any existing row cannot be resolved to a text `persona_id`
4. Drops the UUID foreign-key dependency
5. Replaces the old UUID column with the text column while keeping the final column name `persona_id`
6. Adds indexes needed for `(user_id, persona_id)` and workflow lookup
7. Adds `creative_preferences` and `page_review_data`

## Service And Workflow Fixes

### Plan persistence

- Persist `publish_settings` during plan creation
- Persist `creative_preferences` on create and update
- Persist `approved_at` during approval
- Persist `page_review_data` from source review so workflow startup does not reconstruct a dummy page-review object

### Workflow start-from-plan

- `start_workflow_from_plan()` must rebuild the review input from persisted plan data, especially:
  - normalized source URL
  - page title
  - access level
  - login-required signal
  - assumptions
  - risks
  - visible features or flows when available

- Approval must start exactly one workflow for a plan
- Approval must preserve plan metadata and attach the resulting `workflow_id` back to the same plan

### Job listing and state merge

- `list_jobs()` must merge:
  - generated plan rows from `video_render_plans`
  - active workflow rows from `public.workflows`

- Merge key rules:
  - use `plan_id` as the stable public identity
  - if a workflow row references a `plan_id`, merge that workflow state into the existing plan-backed item
  - generated-but-not-started plans stay visible with `workflow_id = null`

- Stable states to support:
  - `generated`
  - `upload_required`
  - `approved`
  - `in_progress`
  - `completed`
  - `failed`

### Manual upload lane

- `user_upload` is a supported plan/job state inside the same review-engine lane
- Creating a `user_upload` plan sets status to `upload_required`
- Upload attaches the stored media reference to the existing plan/job entity
- Upload must not require a separate `app_review_upload` workflow record to exist first
- After upload succeeds, the plan returns to the normal review-engine approval path

### Failure-path fix

- Remove the `script_payload = None` then `.get(...)` crash path
- Lock one fallback behavior:
  - if script generation fails for `ai_autonomous`, create no plan and return a surfaced hard failure for that persona
  - if the requested mode is `user_upload`, create an `upload_required` plan without script payload

This avoids silently downgrading autonomous generation into a different mode.

## Public API And Internal Model Changes

- `POST /api/customer/review-engine/jobs`
  - accept `creative_preferences`
  - treat `persona_id` inputs as text ids only

- `POST /api/customer/review-engine/plans`
  - accept text `persona_id`
  - accept `creative_preferences`

- `PATCH /api/customer/review-engine/plans/{plan_id}`
  - update `creative_preferences`
  - update `publish_settings`
  - persist `approved_at` through the normal service path

- `GET /api/customer/review-engine/jobs`
  - return stable plan/workflow hybrid items with `plan_id`
  - include `creative_preferences`

## Test Plan

- Web happy path with `ai_auto`
  - validate URL
  - select personas
  - generate plans
  - edit a plan
  - approve
  - see progress
  - publish if allowed

- Web happy path with `human_phone`
  - generate upload-required plan
  - upload media
  - approve after upload
  - continue through the same render and publish lane

- Unsupported `ai_remote`
  - visible in UI as unavailable
  - cannot be posted to backend

- State persistence
  - refresh after generation keeps plans visible
  - refresh after approval keeps the same plan-backed item visible with workflow-linked state

- Data integrity
  - global/system personas and customer personas both resolve correctly
  - `publish_settings`, `creative_preferences`, and `approved_at` persist correctly
  - `page_review_data` is sufficient to start the workflow without a dummy placeholder object
  - script-generation failure does not crash the request path

- Compatibility
  - Telegram `video-ai` flow still works unchanged
  - existing workflow start API still accepts approved-package and confirmed review-plan inputs

## Acceptance Criteria

- Creating a plan never fails because of persona UUID/text mismatch.
- Approving a plan preserves plan metadata and starts exactly one workflow.
- Listing jobs shows generated, approved, in-progress, completed, failed, and upload-required items consistently.
- Manual upload works in the same review-engine lane and does not depend on a never-created job type.
