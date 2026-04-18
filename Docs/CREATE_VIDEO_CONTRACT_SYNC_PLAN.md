# Create Video Contract Sync Plan

Last verified: 2026-04-18 (UTC)

This plan locks the canonical FE/BE contract for the web create-video flow so implementers do not invent ad hoc mappings.

## Summary

- Web UI and customer API use external text `persona_id` values.
- UI mode labels stay separate from backend execution values.
- The create request, persisted plan shape, and job list shape must round-trip the same user-visible state.
- Any visible setup field must either persist end to end or be removed from the UI.

## Canonical Identifiers And Modes

### Persona identifier

- Canonical external persona identifier: text `persona_id`
- Web UI uses text `persona_id`
- Customer API uses text `persona_id`
- Persisted plan records use text `persona_id`
- DB UUID row ids are internal only and must not appear in the web contract

### Mode model

- Frontend mode ids remain UX-only:
  - `ai_auto`
  - `ai_remote`
  - `human_phone`

- Backend execution values remain API-only:
  - `ai_autonomous`
  - `user_upload`

- Required mapping:
  - `ai_auto` -> `ai_autonomous`
  - `human_phone` -> `user_upload`
  - `ai_remote` stays disabled and is never posted until backend support exists

## Canonical Create Request

`POST /api/customer/review-engine/jobs`

```json
{
  "source_url": "https://example.com",
  "objective": "Drive signups",
  "target_personas": ["basic-american-host", "global-cn-wei"],
  "input_mode": "ai_autonomous",
  "publish_to_tiktok": false,
  "creative_preferences": {
    "brief": "Optional additional direction",
    "background": "studio-soft",
    "movement_style": "Natural",
    "gesture_intensity": 50,
    "music_mood": "None",
    "music_volume": 70
  }
}
```

Rules:

- `input_mode` uses backend values only
- `creative_preferences` is optional, but if the UI exposes a field it must map into this object
- `ai_remote` is blocked at the UI layer and must never be submitted

## Canonical Persisted Plan Shape

Public plan record shape:

```json
{
  "plan_id": "uuid",
  "persona_id": "basic-american-host",
  "source_url": "https://example.com",
  "objective": "Drive signups",
  "script_text": "Narration text",
  "scenes_data": [],
  "status": "generated",
  "publish_settings": {},
  "creative_preferences": {
    "brief": "Optional additional direction",
    "background": "studio-soft",
    "movement_style": "Natural",
    "gesture_intensity": 50,
    "music_mood": "None",
    "music_volume": 70
  },
  "workflow_id": null,
  "approved_at": null,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

Rules:

- `plan_id` is the stable public identifier for plan records
- `persona_id` remains text
- `creative_preferences` must round-trip on create, update, and list/read paths
- `publish_settings` remains a separate object from `creative_preferences`

## Canonical Job/List Response Expectations

`GET /api/customer/review-engine/jobs` must return a stable hybrid plan/workflow item shape.

Required fields:

- `job_id`
- `plan_id`
- `workflow_id`
- `status`
- `current_step`
- `progress`
- `input_mode`
- `source_url`
- `objective`
- `persona`
- `script`
- `production`
- `publish`
- `creative_preferences`
- timestamps

Required status coverage:

- `generated`
- `upload_required`
- `approved`
- `in_progress`
- `completed`
- `failed`

Rules:

- pre-workflow items must still include `plan_id`
- `workflow_id` may be `null` for pre-workflow items
- response shape must stay stable across generated, approved, running, completed, and upload-required states
- `creative_preferences` must be echoed back for dashboard summary and edit flows

## Frontend State Decisions

- Gesture intensity becomes controlled state
- Music volume becomes controlled state
- Summary panel only shows fields that round-trip through the canonical state
- The new dashboard flow no longer depends on demo adapters after contract sync

Frontend type rules:

- keep UI mode ids separate from backend execution values
- keep setup state aligned with `creative_preferences`
- remove any type that implies demo-only review or render behavior once real mapping exists

## API And Type Changes To Lock

- `POST /api/customer/review-engine/jobs`
  - add `creative_preferences`
  - keep `input_mode` canonical to backend values only

- `GET /api/customer/review-engine/jobs`
  - return stable plan/workflow hybrid items with `plan_id`
  - return `creative_preferences`

- `POST /api/customer/review-engine/plans`
  - accept text `persona_id`
  - accept `creative_preferences`

- `PATCH /api/customer/review-engine/plans/{plan_id}`
  - accept `creative_preferences`
  - preserve existing fields when only part of the object changes

## Acceptance Criteria

- Every visible field in setup either persists end to end or is explicitly removed from the UI.
- FE types, API payloads, and backend request models use the same naming and allowed values.
- No unsupported mode can accidentally reach the backend.
- `creative_preferences` round-trips through create, update, list, and read flows.
