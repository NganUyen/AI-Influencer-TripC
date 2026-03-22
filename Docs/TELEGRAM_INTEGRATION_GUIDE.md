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

Canonical backend APIs already usable by the current skill layer:

- `POST /api/media/generate/image`
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

## 2. What Needs To Be Built

### `session_store.py`

- Redis key: `telegram_session:{chat_id}`
- TTL: `600` seconds
- Methods: `get_session`, `set_session`, `clear_session`
- Shape: `SkillSession` from `skills/base.py`

### `telegram_router.py`

- `/media` command -> main menu
- callback routing table:
  - `menu_image` -> image submenu
  - `menu_video` -> video submenu
  - `menu_manage` -> manage submenu
  - `skill_{name}` -> `skill_dispatcher`

### `skill_dispatcher.py`

- load session from Redis
- update `session.collected` from user input
- call `skill.execute()`
- save updated session
- return `SkillResult`

### `telegram_renderer.py`

- render `SkillResult` to Telegram messages
- rules per step type:
  - `collect_*` -> question + keyboard
  - `preview_*` -> media + action buttons
  - `poll_status` -> progress message + re-poll
  - `waiting_*` -> "waiting for approval" message
  - `done` -> final output + completion
  - `failed` -> error + retry button

### `step_config.py`

- per-skill `step -> input_type` mapping
- inline keyboard options per step
- free-text prompts per step
- central prompt text owned here, not inside skill execution logic

## 3. Integration Sequence

`video-ai` should be the canonical end-to-end integration path.

1. `telegram_router.py` receives `/media`
2. router shows the main menu and the user taps `Create Video`
3. router shows the video submenu and the user taps `AI Influencer`
4. `skill_dispatcher.py` creates `VideoAISkill.initial_session()`
5. session is saved under `telegram_session:{chat_id}`
6. `telegram_renderer.py` sees `step_key=pick_persona` and renders the persona picker
7. user selects a persona, then provides topic, tone, and platform
8. dispatcher updates `session.collected`
9. dispatcher calls `VideoAISkill.execute(...)`
10. skill checks `GET /api/personas/{persona_id}/readiness`
11. skill starts `POST /api/workflows/start-video`
12. skill sets `session.control.workflow_id` and `approval_required=True`
13. renderer sends a "workflow started" message and offers status/approval follow-up

The same control flow works for `weekly-planner`, `image-scene`, `quota-inspector`, and persona helper flows.

## 4. Wiring Checklist Per Skill

### `image-scene`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `image-poster`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `quota-inspector`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `persona-inspector`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `persona-creator`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `video-ai`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `weekly-planner`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `carousel`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

### `long-post`
[ ] session store tested
[ ] router callback registered
[ ] renderer handles all steps
[ ] end-to-end test scenario passes

## 5. Deferred Skills

- `carousel`
  - currently stubbed in the skill package for this implementation pass
  - unblocked when the Telegram layer is ready to treat `/api/media/carousel` as active instead of stubbed
- `long-post`
  - blocked by the missing dedicated backend endpoint `POST /api/media/long-post`
- `video-tutorial`
  - intentionally deferred because the current phase reuses `start-video` as the only video lane
- `image-poster`
  - still needs poster-specific prompt/template policy in the Telegram layer
