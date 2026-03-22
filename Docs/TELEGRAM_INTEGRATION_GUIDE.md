# TELEGRAM_INTEGRATION_GUIDE

## 1. What Already Exists

Skill package files under `Project/python_services/skills/`:

- `base.py`
- `definitions.py`
- `image_scene.py`
- `quota_inspector.py`
- `persona_inspector.py`
- `persona_creator.py`
- `video_ai.py`
- `weekly_planner.py`
- `carousel.py`
- `long_post.py`
- `__init__.py`

Telegram/OpenClaw routing files now implemented under `Project/python_services/services/` and `Project/python_services/api/`:

- `api/telegram_webhook.py`
- `services/skill_session_store.py`
- `services/skill_dispatcher.py`
- `services/telegram_renderer.py`
- `services/step_config.py`
- `services/telegram_service.py` approval callback bridge

Canonical backend APIs already usable by the current skill layer:

- `POST /api/media/generate/image`
- `POST /api/media/carousel`
- `POST /api/workflows/start-video`
- `POST /api/workflows/start-weekly`
- `GET /api/personas`
- `POST /api/personas`
- `GET /api/personas/{persona_id}`
- `PATCH /api/personas/{persona_id}`
- `GET /api/personas/{persona_id}/readiness`
- `GET /api/quota/summary`
- `GET /api/quota/providers/{provider}`

Approval/runtime primitives already exist in the skill layer:

- `SkillControl.workflow_id`
- `SkillControl.approval_required`
- `SkillStatus.waiting_approval`

Current Telegram entrypoints already working:

- `/start` -> welcome + quick actions
- `/media` -> main media menu
- `/cancel` -> clear active skill session
- callback routing for `menu_*`, `skill_*`, `option::*`, `action::*`
- approval callback routing for `approve_*`, `reject_*`, `edit_*`, `save_*`, `discard_*`
- daily-story callback routing for `post_tiktok`, `post_shorts`, `skip`, `status_check`, `help`

Current automated coverage:

- `tests/test_media_api.py`
- `tests/test_workflows_api.py`
- local Telegram/skill cleanup verification was run before repository cleanup

## 2. What Still Needs To Be Built

### `skill_session_store.py`

- move from in-memory fallback to production Redis-only operation if strict durability is required
- add session expiry refresh and observability
- add recovery path for malformed session payloads

### `telegram_webhook.py`

- richer attachment handling for photo/document uploads during persona creation
- webhook-side status polling helpers for long-running workflows
- more precise user-facing branching for unknown callback payloads

### `skill_dispatcher.py`

- per-skill post-processing for richer output cards
- workflow status poll/retry behavior after `waiting_approval`
- support more regenerate branches without resetting the whole session

### `telegram_renderer.py`

- send media groups/previews for carousel slides instead of text-only preview summaries
- render persona cards and quota views with richer formatting
- unify completion rendering for workflow-backed skills

### `step_config.py`

- add upload-oriented steps once Telegram file flows are introduced
- expand menu depth when deferred skills are reactivated
- keep step prompts aligned with future skill doc revisions

### `tests/`

- add end-to-end tests for each active skill path
- add callback tests for `save_*` / `discard_*` approval flows
- add Redis-backed session-store coverage

## 3. Integration Sequence

`video-ai` should be the canonical end-to-end integration path.

1. `api/telegram_webhook.py` receives `/media`
2. webhook shows the main menu and the user taps `Create Video`
3. webhook routes `menu_video` then `skill_video-ai`
4. `services/skill_dispatcher.py` creates `VideoAISkill.initial_session()`
5. `services/skill_session_store.py` saves the session under `telegram_session:{chat_id}`
6. `services/telegram_renderer.py` sees `step_key=pick_persona` and renders the persona picker
7. user selects a persona, then provides topic
8. dispatcher updates `session.collected`
9. dispatcher calls `VideoAISkill.execute(...)`
10. skill checks `GET /api/personas/{persona_id}/readiness`
11. skill starts `POST /api/workflows/start-video` with default `tone=natural` and `platform=tiktok`
12. skill sets `session.control.workflow_id` and `approval_required=True`
13. renderer sends a "workflow started" message and offers approval/cancel follow-up

The same control flow works for `carousel`, `weekly-planner`, `image-scene`, `quota-inspector`, and persona helper flows.

## 4. Wiring Checklist Per Skill

### `image-scene`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `image-poster`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `quota-inspector`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `persona-inspector`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `persona-creator`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `video-ai`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `weekly-planner`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `carousel`
[x] session store wired
[x] router callback registered
[x] renderer handles current steps
[ ] end-to-end test scenario passes

### `long-post`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

## 5. Deferred Skills

- `long-post`
  - blocked by the missing dedicated backend endpoint `POST /api/media/long-post`
- `video-tutorial`
  - intentionally deferred because the current phase reuses `start-video` as the only video lane
- `image-poster`
  - still needs poster-specific prompt/template policy in the Telegram layer

## 6. Known Test Failures

Current full pytest status at the latest cleanup checkpoint:

- `87 passed, 4 failed`

The remaining failures are outside the Telegram skill/session wiring itself:

- `tests/test_chatgpt_connector_app.py::test_connector_app_oauth_and_tool_call_flow`
  - current result: `503`
  - expected by test: `200`
  - reason: connector OAuth bootstrap is intentionally disabled until a real external identity flow is configured
- `tests/test_chatgpt_connector_app.py::test_connector_task_registry_is_scoped_to_the_current_session`
  - current result: missing `state`
  - reason: same disabled OAuth bootstrap path as above
- `tests/test_chatgpt_connector_auth.py::test_connector_auth_service_creates_and_resolves_session`
  - current result: `PermissionError`
  - reason: connector OAuth bootstrap is intentionally disabled until a real external identity flow is configured
- `tests/test_services.py::test_postiz_publish_builds_payload`
  - current result: `provider_post_id == "platform-post-1"`
  - expected by test: `"post-1"`
  - reason: Postiz payload normalization/contract mismatch still needs reconciliation

Deployment note:

- current media pipeline and Telegram/OpenClaw skill lane are usable for internal/staging validation
- production push should still treat the connector OAuth failures and the Postiz payload mismatch as open items
