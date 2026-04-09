# Video Agent Implementation Summary

## Scope

This document summarizes the Telegram bot and video pipeline work completed in this session.

Goal achieved:

- move the Telegram bot from a menu-first media trigger into a planning-first video agent
- add URL review, plan confirmation, execution-mode branching, manual mobile upload support, authenticated workspace handoff, planner-aware recording scripts, and audio fallback behavior

## High-Level Outcome

The bot now supports a planning-first flow:

1. `/start` launches a dedicated `video-planner` skill
2. user provides objective
3. user provides target URL
4. system performs AI-assisted website review
5. bot asks for language
6. bot asks for persona
7. bot asks for execution mode
8. bot generates a `Video Review Plan`
9. execution waits for explicit confirmation

Supported execution modes:

- `autonomous_screen_recording`
- `authenticated_pc_recording`
- `manual_mobile_recording`

The output pipeline continues to preserve the current vertical video format (`1080x1920`, `tiktok`/`9:16` path).

## Architecture And Contracts Added

Added to `Project/python_services/services/contracts.py`:

- `WebPageReviewContract`
- `WebPageReviewFindingContract`
- `CredentialHandoffContract`
- `RecordingScriptContract`
- `RecordingScriptStepContract`
- `VideoAudioPolicyContract`
- `VideoReviewPlanContract`

Extended existing workflow payloads:

- `VideoWorkflowStartPayloadContract.review_plan`
- `VideoWorkflowStartPayloadContract.execution_mode`
- `VideoWorkflowStartPayloadContract.audio_policy`
- `SplitScreenVideoInput.audio_url` is now optional
- `SplitScreenVideoInput.audio_policy` added
- `SceneContract.browser_action` added
- `SceneContract.visual_success_criteria` added

Architecture documentation added:

- `.opencode/TELEGRAM_VIDEO_PLANNER_ARCHITECTURE.md`

## Telegram Planner Flow

New skill and registration:

- `Project/python_services/skills/video_planner.py`
- `Project/python_services/skills/__init__.py`
- `Project/python_services/agents/openclaw_telegram_skill_configs.py`
- `Project/python_services/services/step_config.py`

Updated `/start` behavior:

- `Project/python_services/api/telegram_webhook.py`

Behavior:

- `/start <token>` still preserves Telegram-to-workspace linking
- plain `/start` now starts `video-planner`
- `/media` remains the legacy media entrypoint

Planner steps implemented:

- `collect_objective`
- `collect_target_url`
- URL review
- `choose_language`
- `pick_persona`
- `choose_execution_mode`
- `confirm_plan`
- `upload_manual_video` for manual mobile mode

## Website Review

Added:

- `Project/python_services/services/website_review_service.py`

Behavior:

- normalizes target URL
- fetches website content via Jina Reader first
- falls back to `BrowserAutomationService.get_page_content()`
- asks OpenClaw for structured page review JSON
- degrades to heuristic fallback if AI analysis fails

Website review output includes:

- page title
- product summary
- visible features
- visible flows
- recording candidates
- access level
- login-required signal
- risks
- assumptions

## Telegram Rendering Improvements

Updated:

- `Project/python_services/services/telegram_renderer.py`

New Telegram render surfaces:

- `Website Review Ready`
- richer `Video Review Plan`
- planner-specific completion messaging

The plan card now includes:

- objective
- URL
- language
- persona
- execution mode
- access level
- rationale from page review
- assumptions
- risks
- credential handoff state

## Execution Handoff

Added:

- `Project/python_services/services/video_planner_handoff_service.py`

Behavior after plan confirmation:

- `autonomous_screen_recording`
  - starts `/api/workflows/start-video`
- `authenticated_pc_recording`
  - creates secure workspace handoff
- `manual_mobile_recording`
  - waits for Telegram video upload, then bridges into the existing recorded-demo path

Explicit confirmation remains required before any execution path begins.

## Autonomous Screen Recording Path

Extended:

- `Project/python_services/services/script_service.py`
- `Project/python_services/activities/approval_activities.py`
- `Project/python_services/activities/__init__.py`
- `Project/python_services/worker.py`
- `Project/python_services/workflows/short_video_workflow.py`

New capability:

- `generate_script_from_review_plan(...)`

Behavior:

- a confirmed review plan is converted into
  - a narration script
  - a structured recording script
  - scene-level browser capture instructions
- the autonomous workflow path now prefers planner-driven scene generation for
  - `autonomous_screen_recording`
  - `authenticated_pc_recording`

Scene metadata now carries:

- `browser_action`
- `visual_success_criteria`
- `top_half_target`
- `top_half_capture_hint`
- `source_ref`

## Browser Capture Quality Improvements

Updated:

- `Project/python_services/services/browser_automation.py`
- `Project/python_services/activities/media_activities.py`

Improvements:

- planner-generated review-plan scenes now default to `orchestrated` capture mode unless explicitly static
- browser capture now receives `browser_action` and `visual_success_criteria`
- guided interaction is attempted before scrolling when the action implies interaction such as:
  - click
  - open
  - select
  - tap
  - press

This improves on-screen coherence without changing the existing capture frame or final video size.

## Manual Mobile Recording Path

Updated:

- `Project/python_services/skills/video_planner.py`
- `Project/python_services/services/skill_dispatcher.py`
- `Project/python_services/api/telegram_webhook.py`

Behavior:

- if plan is confirmed with `manual_mobile_recording`, planner moves to `upload_manual_video`
- Telegram video uploads are now accepted for this planner step
- uploaded mobile footage is bridged into the existing `video-ai` recorded-demo pipeline
- concept and beat generation are auto-advanced from the confirmed plan
- `platform = "tiktok"` is preserved so output stays on the current vertical canvas

## Authenticated PC Recording Handoff

Added or updated:

- `Project/python_services/services/video_capture_handoff_service.py`
- `Project/python_services/services/video_planner_handoff_service.py`
- `Project/python_services/api/customer.py`
- `Project/app/capture-handoff/page.tsx`
- `Project/app/auth/page.tsx`

Behavior:

- authenticated capture plans generate short-lived signed handoff tokens
- handoff URL opens inside the workspace, not Telegram
- the workspace page requires customer authentication
- return context through `/auth` is now preserved via `next`
- handoff inspect endpoint validates ownership and token validity
- handoff complete endpoint now exists and can resume workflow execution

Important constraint:

- raw credentials are still intentionally not collected in Telegram
- the completion flow is minimal and secure, but not yet a full credential vault implementation

## Audio And BGM Fallback

Added:

- `Project/python_services/assets/audio_library/library.json`
- `Project/python_services/assets/audio_library/product_explainer_soft.mp3`
- `Project/python_services/assets/audio_library/calm_review_bed.mp3`
- `Project/python_services/assets/audio_library/upbeat_demo_loop.mp3`
- `Project/python_services/services/background_music_service.py`

Updated:

- `Project/python_services/activities/video_activities.py`
- `Project/python_services/workflows/short_video_workflow.py`
- `Project/python_services/activities/media_activities.py`

Behavior:

- if narration audio is missing and BGM fallback is enabled, local BGM is used
- if narration audio exists but is effectively silent, silent-audio fallback now happens before final mux
- final assembly can complete with a neutral bottom-half fallback when no talking head exists
- output remains `1080x1920`
- metadata now records:
  - `used_bgm_fallback`
  - `bgm_profile`
  - `used_talking_head`

Also fixed:

- `generate_audio()` no longer uses `user_id` before assignment
- workflow no longer crashes when `audio_result` is intentionally `None`
- `voiceover_required` now influences whether TTS is started

## Verified Fixes After Review

After a separate verification pass, these issues were fixed:

- manual planner uploads were unreachable from the Telegram webhook
- planner persona picker could include non-ready personas
- blocked authenticated handoff no longer forces full replanning
- manual upload prompt no longer derails on stray text
- TTS `user_id` runtime bug fixed
- workflow now safely supports `audio_url=None`
- silent-audio fallback moved to pre-mux stage
- authenticated handoff now has completion/resume path
- auth redirect now preserves secure handoff return path
- workflow now preserves planner scene execution metadata

## Files Touched

Major backend files:

- `Project/python_services/services/contracts.py`
- `Project/python_services/services/website_review_service.py`
- `Project/python_services/services/video_planner_handoff_service.py`
- `Project/python_services/services/video_capture_handoff_service.py`
- `Project/python_services/services/background_music_service.py`
- `Project/python_services/services/script_service.py`
- `Project/python_services/services/skill_dispatcher.py`
- `Project/python_services/services/telegram_renderer.py`
- `Project/python_services/services/step_config.py`
- `Project/python_services/services/browser_automation.py`
- `Project/python_services/skills/video_planner.py`
- `Project/python_services/api/telegram_webhook.py`
- `Project/python_services/api/customer.py`
- `Project/python_services/api/workflows.py`
- `Project/python_services/activities/approval_activities.py`
- `Project/python_services/activities/media_activities.py`
- `Project/python_services/activities/video_activities.py`
- `Project/python_services/workflows/short_video_workflow.py`
- `Project/python_services/worker.py`

Frontend files:

- `Project/app/capture-handoff/page.tsx`
- `Project/app/auth/page.tsx`

Docs and agent config:

- `AGENTS.md`
- `.opencode/AGENTS.md`
- `.opencode/TELEGRAM_VIDEO_PLANNER_ARCHITECTURE.md`

## Tests Added Or Updated

Added or updated tests include:

- `Project/python_services/tests/test_website_review_service.py`
- `Project/python_services/tests/test_telegram_renderer.py`
- `Project/python_services/tests/test_video_planner_handoff.py`
- `Project/python_services/tests/test_video_capture_handoff_service.py`
- `Project/python_services/tests/test_script_service_review_plan.py`
- `Project/python_services/tests/test_background_music_service.py`
- `Project/python_services/tests/test_video_activities_bgm_fallback.py`
- `Project/python_services/tests/test_media_activities_audio.py`
- `Project/python_services/tests/test_skill_dispatcher.py`
- `Project/python_services/tests/test_customer_api.py`
- `Project/python_services/tests/test_telegram_webhook_local.py`
- `Project/python_services/tests/test_workflows_api.py`

## Verification Status

Verified in this environment:

- targeted repaired-path tests passed
- broader backend regression tests passed
- backend syntax/import checks passed

Not fully verified here:

- frontend typecheck could not be run because `npm` is unavailable in this environment
- frontend Jest was not executed here

## Remaining Gaps

Still incomplete or intentionally minimal:

- authenticated PC capture still does not implement a full secure credential vault or session-material persistence flow
- `bgm_duck_under_voiceover` is still not a true mix/duck implementation
- guided browser interaction is still lightweight text-target clicking, not a full multi-step browser action planner for complex authenticated flows

## Recommended Next Work

1. Build a true secure session/credential submission flow for authenticated PC capture.
2. Implement real voiceover+BGM mixing and ducking.
3. Add broader integration tests across Telegram planner -> workflow -> final assembly.
4. Add frontend test coverage for `/capture-handoff` and auth return flow.
