# Create Video Web Integration Plan

Last verified: 2026-04-18 (UTC)

This plan defines how to turn the new dashboard `Create Video` UI into the canonical web create-video surface.

## Summary

- The dashboard create-video flow does **not** call, wrap, or proxy the Telegram `video-ai` skill.
- The web flow uses the authenticated review-engine HTTP routes plus shared backend services and workflows.
- `CreateVideoTab` becomes the canonical web surface.
- `LiveFeedTab` remains a short-term reference only until parity is complete.

## Current State

- `CreateVideoTab` is mostly placeholder/demo UI.
- `create-video-adapter.ts` returns demo plan cards and simulated render progress instead of real backend data.
- `CreateVideoSetupStep` only performs real source validation through `POST /api/customer/review-engine/source/validate`.
- `LiveFeedTab` is still the only fully wired web flow for:
  - `POST /api/customer/review-engine/jobs`
  - `PATCH /api/customer/review-engine/plans/{plan_id}`
  - `POST /api/customer/review-engine/plans/{plan_id}/approve`
  - `GET /api/customer/review-engine/jobs`
  - publish and upload actions

## Target Web Flow

1. Validate source URL through `POST /api/customer/review-engine/source/validate`.
2. Create persona jobs/plans through `POST /api/customer/review-engine/jobs`.
3. Show real backend-backed plan cards in step 2.
4. Save edits through `PATCH /api/customer/review-engine/plans/{plan_id}`.
5. Approve through `POST /api/customer/review-engine/plans/{plan_id}/approve`.
6. Poll `GET /api/customer/review-engine/jobs` for render and progress state.
7. Publish from the real job state only when backend capabilities say the action is available.

## Decisions

- `CreateVideoTab` owns the final web create-video experience.
- `LiveFeedTab` is transitional and should be deleted after the new tab reaches parity.
- `create-video-adapter.ts` must be deleted or fully replaced with real mapping logic; do not extend the demo fixture path.
- The web flow remains independent from the Telegram skill flow until the shared downstream workflow reaches its existing Telegram approval or preview stages.

## Required UI And Behavior Changes

- Step 1:
  - keep source validation in the new setup UI
  - keep unsupported modes visibly disabled
  - only enable continue when the source is validated and at least one persona is selected

- Step 2:
  - render real backend-backed plan cards
  - support plan edit and save using `plan_id`
  - show stable status labels from backend response, not demo status names

- Step 3:
  - remove simulated timers
  - poll `GET /api/customer/review-engine/jobs`
  - render progress, current step, and output readiness from the real job state

- Step 4:
  - expose only publish actions the backend can execute today
  - hide or disable unsupported publish actions instead of showing placeholders

- Data ownership:
  - `CreateVideoTab` should either receive preloaded jobs from `customer-dashboard.tsx` or fetch and poll them itself
  - the tab must preserve `plan_id` and `workflow_id` through the full flow

## Implementation Notes

- Reuse `LiveFeedTab` behavior as the source of truth for the first working integration.
- Move the real request and response handling into the new `CreateVideoTab` flow instead of maintaining two divergent web implementations.
- Do not introduce any dependency on Telegram skill session state, Telegram menus, or `video_ai.py` step transitions in the dashboard flow.

## Acceptance Criteria

- A user can complete source validate -> generate -> edit -> approve -> see progress entirely from the new `CreateVideoTab`.
- Refreshing the page preserves plan and workflow state in the new web tab.
- Step 2 uses backend plans, not demo fixtures.
- Step 3 uses backend progress, not simulated timers.
- Step 4 exposes only backend-supported publish actions.
- No create-video behavior depends on Telegram bot interaction until the workflow itself reaches its existing Telegram approval or preview stages.
