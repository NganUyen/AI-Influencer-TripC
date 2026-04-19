# Approval + Top-Half Definitions

This document unifies the current behavior and definitions for:

- Approval flow (Telegram Save/Discard/Approve/Reject)
- Top-half generation flow (browser capture / AI fallback)

It is intended as an operational reference for debugging and implementation alignment.

## 1) Approval Definition

### 1.1 Core entities

- `public.approvals`
  - Stores durable approval requests and decisions.
  - Important fields: `id`, `workflow_id`, `approver_id`, `request_key`, `status`, `decision_payload`, timestamps.
- `public.workflows`
  - Tracks workflow runtime state.
  - `approvals.workflow_id` has FK to `workflows.workflow_id`.

### 1.2 Status/action mapping

Action to status mapping in approval state:

- `approve` -> `approved`
- `reject` -> `rejected`
- `save` -> `save`
- `discard` -> `discard`

### 1.3 Telegram callback contract

- Preferred callback format: `action:<approval_id>`
  - Examples: `save:3b2...`, `discard:3b2...`
- Legacy fallback format exists (`action_<chat_id>`), but should not be relied on for durable lookup.

### 1.4 Request lifecycle

1. `send_preview_to_telegram` calls `TelegramService.send_approval_request(...)`.
2. `ApprovalStateService.create_request(...)` inserts into `public.approvals`.
3. Telegram callback calls `TelegramService.apply_callback_payload(...)`.
4. `ApprovalStateService.apply_decision(...)` updates final status.

### 1.5 Known failure mode: "Approval request not found"

Common causes:

- Approval insert failed and runtime fell back to memory-only state.
- Workflow row not present in `public.workflows`, causing FK failure on `approvals.workflow_id`.
- Callback from stale message (legacy format, missing approval id).

Required guardrails:

- Ensure `workflows` row is written before final decision approval is created.
- Ensure `approver_id` is always a valid UUID mapped from Telegram link.
- Log DB exceptions before memory fallback so root cause is visible.

## 2) Top-Half Definition

### 2.1 Goal

Generate top-half visual assets per scene for final split-screen assembly.

### 2.2 Supported source types

- `public_page_capture` (strict browser capture)
- `authenticated_capture_later` (strict browser capture)
- `hybrid_candidate` (browser first, AI fallback)
- `ai_visual_fallback` (AI-only)
- `uploaded_demo_video` (extract segment from uploaded video)

Unknown types are normalized to `ai_visual_fallback` outside strict mode.

### 2.3 Execution model

- Entry activity: `generate_scene_images(scenes)`
- Per-scene processing runs concurrently with semaphore.
  - Env knob: `TOP_HALF_CAPTURE_CONCURRENCY` (default `2`)
- Browser capture has multi-attempt retry logic with progressive fallback.

### 2.4 Output contract per scene

Each scene should return:

- `image_url` (top-half media URL)
- `is_video` (must be `true` for strict browser paths)
- `generation_method`
- optional diagnostics (`fallback_triggered`, `browser_error`, `capture_metrics`)

### 2.5 Validation behavior before assembly

Workflow validates top-half assets before ffmpeg assembly:

- Missing URLs -> fail with scene asset mismatch.
- Non-video assets in strict lane -> fail.
- Scene count mismatch (durations vs media) -> fail.

This is currently fail-fast by design.

### 2.6 Performance-sensitive stages

Longest stages in practice:

- Browser top-half capture
- Talking-head generation
- Final ffmpeg split-screen assembly

Relevant timeouts in workflow:

- top-half generation activity: up to 10 minutes
- talking-head activity: up to 20 minutes
- split-screen assembly activity: up to 20 minutes

## 3) Combined Operational Checklist

When video is generated but Save/Discard fails:

1. Confirm media is present in `public.media_assets` for the workflow id.
2. Confirm workflow row exists in `public.workflows`.
3. Confirm approval row exists in `public.approvals`.
4. If (2) missing, create workflow state earlier in start flow.
5. If (3) missing, inspect approval insert path and fallback logs.

When top-half is slow or unstable:

1. Reduce `TOP_HALF_CAPTURE_CONCURRENCY` to `1`.
2. Validate `source_ref` reachability and login requirements.
3. Prefer `hybrid_candidate` where strict browser capture is not mandatory.
4. Inspect per-scene capture diagnostics for recurring failure patterns.

## 4) Recommended Near-Term Hardening

- Always persist `workflows` state before sending approval requests.
- Add explicit error logging around approval DB insert failures.
- Add optional fallback strategy to avoid memory-only approval state.
- Expose top-half stage duration metrics per scene for tuning.

## 5) Current Gap Checklist

This section tracks the current known gaps after local verification.

- `P0` Approval persistence is not stable for all workflows (`Approval request not found` observed).
- `P0` Workflow state is not always persisted to `public.workflows` from the start of each run.
- `P0` FK timing between `approvals.workflow_id` and `workflows.workflow_id` is still fragile.
- `P0` Fallback-to-memory paths do not emit enough structured logs for fast diagnosis.
- `P1` Top-half capture latency is variable (browser capture remains the main bottleneck).
- `P1` No stage timing dashboard yet (`script`, `top_half`, `talking_head`, `assembly`, `upload`).
- `P1` Metadata mismatch exists: `visibility` may be `private` while URL path is `public`.
- `P1` No robust recovery path for stale legacy callback messages.
- `P1` Integration coverage is missing for Telegram `save/discard` persistence scenarios.
- `P1` Publish flow should be re-verified end-to-end after approval persistence is fixed.

## 6) Notes

- Publishing UI mock mode has been removed and is now backend-driven.
- Remaining blockers are primarily backend workflow-state and approval durability issues.
