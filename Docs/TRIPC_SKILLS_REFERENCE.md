# TripC Skills Reference

## Purpose

This document defines the recommended skill taxonomy for the current TripC repository.

It is based on the code that exists now in:

- `Project/python_services/services`
- `Project/python_services/activities`
- `Project/python_services/workflows`
- `Project/python_services/scripts`

It should be treated as a repo-grounded reference, not as a forward-looking plan.

Important note:

- `Docs/TRIPC_VIDEO_PIPELINE_V2_REVIEW.md` is still useful as a design document, but parts of it are older than the current implementation state.
- For implementation status, prefer this file plus `Docs/CURRENT_REPO_STATUS.md`.

## Core Principle

This repo should distinguish between:

- `bot entry modes`
  - the public commands or menu options exposed to users in Telegram
- `internal skills`
  - the reusable pipeline capabilities implemented in services, activities, and workflows

Users should interact with simple entry modes such as:

- `/video`
- `/carousel`
- `/long_post`
- `/weekly_plan`
- `/persona_setup`
- `/quota`
- `/publish`

The bot should then map each entry mode to the relevant internal skills.

This is better than exposing raw prompt syntax because it:

- reduces user error
- ensures required parameters are collected before pipeline execution
- allows per-type prompt templates and provider defaults
- makes quota-aware gating possible before expensive jobs begin
- makes it easier to add new content types without breaking older flows

## Status Labels

- `Partial`
  - some logic exists, but the skill is not yet a clean end-to-end lane
- `Implemented`
  - the main logic exists in code and is wired into service/activity/workflow surfaces
- `Validated`
  - there is isolated smoke-test coverage or explicit repo documentation that the lane has been exercised

## Recommended Skill Set

### Core Video Pipeline

| Skill | What it does | Status |
|---|---|---|
| `video-orchestrator` | coordinates the end-to-end video lane | `Partial` |
| `script-gen` | generates short-form script JSON for video | `Implemented`, `Validated` |
| `scene-builder` | builds reusable scene metadata for visuals and captions | `Partial` |
| `image` | generates scene images and avatar stills | `Implemented`, `Validated` |
| `google-tts` | generates narration audio | `Implemented` |
| `heygen-video` | generates talking-head video and polls job status | `Implemented` |
| `ffmpeg-assembly` | assembles final vertical video locally | `Implemented` |

### Content Strategy

| Skill | What it does | Status |
|---|---|---|
| `weekly-plan` | generates weekly content strategy | `Implemented` |
| `carousel-plan` | generates slide-by-slide carousel strategy JSON | `Implemented`, `Validated` |
| `long-post-plan` | generates long-form post strategy JSON | `Implemented`, `Validated` |

### Infra

| Skill | What it does | Status |
|---|---|---|
| `r2-storage` | stores image/audio/video artifacts in Cloudflare R2 | `Implemented` |
| `quota-monitor` | records and exposes provider usage/quota state | `Implemented` |

### Operator Interface

| Skill | What it does | Status |
|---|---|---|
| `telegram-approval` | human approval loop for script and preview/publish | `Implemented` |
| `persona-setup` | one-time persona bootstrap for avatar readiness | `Partial` |
| `postiz-publish` | publish or schedule approved content | `Implemented` |

## Recommended Bot Entry Modes

These are the user-facing modes the Telegram bot should expose.

### Preferred default UX

Use `menu-driven` interaction by default:

1. user selects an entry mode
2. bot asks for missing parameters step by step
3. bot validates persona, quota, and required provider readiness
4. bot triggers the correct skill chain

### Optional power-user UX

Support shortcut syntax for repeat users:

- `/video_ai`
- `/video_ai again`
- `/video_ai minh_vn "Bun cha ca Da Nang"`
- `/carousel`
- `/long_post`

The shortcut layer should be optional, not the primary UX.

### Entry Mode Catalog

| Entry mode | User intent | Recommended UX | Internal skills |
|---|---|---|---|
| `/video` | create video content | menu: `AI Influencer Video`, `Web Tutorial Video` | `video-orchestrator`, `script-gen`, `scene-builder`, `image`, `google-tts`, `heygen-video`, `ffmpeg-assembly`, `telegram-approval`, `r2-storage`, `postiz-publish` |
| `/video_ai` | create AI influencer video directly | shortcut or submenu | `video-orchestrator`, `script-gen`, `scene-builder`, `image`, `google-tts`, `heygen-video`, `ffmpeg-assembly`, `telegram-approval`, `r2-storage`, `postiz-publish` |
| `/video_tutorial` | create tutorial-style video | shortcut or submenu | `scene-builder`, `image`, `google-tts`, `heygen-video`, `ffmpeg-assembly`, `telegram-approval`, `r2-storage`, `postiz-publish` |
| `/carousel` | create image carousel | menu or shortcut | `carousel-plan`, `image`, `telegram-approval`, `r2-storage`, `postiz-publish` |
| `/long_post` | create long-form post | menu or shortcut | `long-post-plan`, `image`, `telegram-approval`, `r2-storage`, `postiz-publish` |
| `/weekly_plan` | create weekly content strategy | menu or shortcut | `weekly-plan`, `telegram-approval`, `postiz-publish` |
| `/persona_setup` | prepare or inspect personas for video reuse | menu: `Create New`, `Choose Existing` | `persona-setup`, `image`, `heygen-video`, `r2-storage` |
| `/quota` | inspect provider readiness and usage | menu or shortcut | `quota-monitor` |
| `/publish` | publish or schedule approved content | menu or shortcut | `postiz-publish` |

### Why `/carousel` should not live under `/video`

`carousel` is a content-planning and image-generation lane, not a video assembly lane.

It may share some providers with video, but it should remain its own entry mode because:

- user intent is different
- provider requirements are different
- output contract is different
- the flow does not require HeyGen or ffmpeg assembly

### Menu-Driven Parameter Collection

For a high-quality Telegram UX, the bot should collect structured inputs before triggering internal skills.

Example for `/video`:

1. choose type
2. choose persona
3. optionally choose `Create New Persona`
4. enter topic
5. inject default tone/platform for the current lane
6. validate quota and persona readiness
7. trigger pipeline

Example for `/carousel`:

1. choose persona
2. enter topic
3. choose platform
4. choose tone or style
5. choose slide count if needed
6. trigger strategy generation

Example for `/persona_setup`:

1. choose `Create New Persona` or `Choose Existing Persona`
2. if creating new:
   - enter persona ID
   - choose language
   - choose voice
   - enter appearance prompt or upload real image
   - review generated avatar preview
   - confirm avatar registration
3. if choosing existing:
   - load personas from DB
   - show readiness and usage state
   - allow `Use`, `Details`, or `Rebuild Avatar`

### Template-Driven Prompting

The bot should not rely on free-form prompts from users as the primary control surface.

Instead:

- user supplies structured intent
- bot selects the correct template by entry mode
- bot injects persona, platform, tone, and provider defaults

This improves:

- consistency
- style control
- provider compatibility
- guardrails for image and video generation

### Quota-Aware Gating

Before starting an expensive lane, the bot should use `quota-monitor` to decide whether the mode is available.

Examples:

- if HeyGen quota is unavailable, hide or disable AI influencer video modes
- if only image providers are available, keep carousel and long-post modes enabled
- if persona setup is incomplete, block video modes until `persona-setup` succeeds

This avoids starting workflows that will fail in the middle of the pipeline.

### Shared Persona Registry

`/persona_setup` and `/video -> AI Influencer` should use the same persona registry source.

That means:

- one shared DB query for persona lookup
- one shared status model
- one shared formatting layer for persona cards
- one shared readiness policy for gating video flows

Recommended persona statuses:

- `pending`
- `generating`
- `ready`
- `failed`
- `rebuilding`

## Skill Details

## Core Video Pipeline

### `video-orchestrator`

**Role**

Coordinates the full video lane:

1. receive topic/persona input
2. generate script
3. wait for Telegram approval
4. generate audio, images, and talking-head
5. assemble final video
6. send preview
7. publish after operator decision

**Current flow in repo**

The repo already has the required pieces, but not yet a dedicated first-class video workflow that owns this entire sequence as one clean Temporal workflow.

**Status**

- `Partial`

**What is already implemented**

- script approval activity lane
- media generation activities
- video assembly activity
- preview/publish approval activities

**What is still missing**

- a dedicated `@workflow.defn` for the video lane that stitches these steps together end-to-end

**Code refs**

- [`../Project/python_services/activities/approval_activities.py`](../Project/python_services/activities/approval_activities.py)
- [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)
- [`../Project/python_services/activities/video_activities.py`](../Project/python_services/activities/video_activities.py)
- [`../Project/python_services/workflows/weekly_marketing_workflow.py`](../Project/python_services/workflows/weekly_marketing_workflow.py)

### `script-gen`

**Role**

Generates structured video script output for downstream media generation.

**Flow**

1. receive `app_name`, `topic`, `persona_config`
2. call `AIService`
3. validate output into `ScriptContract`
4. return:
   - `script`
   - `duration_estimate`
   - `scenes[]`

**Status**

- `Implemented`
- `Validated`

**What is already implemented**

- `ScriptService`
- strict Pydantic contract
- approval activity integration
- smoke test path

**Code refs**

- [`../Project/python_services/services/script_service.py`](../Project/python_services/services/script_service.py)
- [`../Project/python_services/services/contracts.py`](../Project/python_services/services/contracts.py)
- [`../Project/python_services/activities/approval_activities.py`](../Project/python_services/activities/approval_activities.py)
- [`../Project/python_services/scripts/smoke_script.py`](../Project/python_services/scripts/smoke_script.py)

### `scene-builder`

**Role**

Builds reusable scene metadata for image generation, caption overlays, and tutorial-style visual flows.

**Flow**

1. derive scene prompts and captions from topic or app context
2. attach timing, role, caption, and persona context
3. pass scenes into image generation or assembly steps

**Status**

- `Partial`

**Why it is partial**

Scene logic exists, but it is split across two lanes:

- `ScriptService` generates `scenes[]` inside `ScriptContract`
- `content_scenes_service.py` generates tutorial/content scenes separately

There is not yet one unified scene builder abstraction.

**Code refs**

- [`../Project/python_services/services/contracts.py`](../Project/python_services/services/contracts.py)
- [`../Project/python_services/services/script_service.py`](../Project/python_services/services/script_service.py)
- [`../Project/python_services/services/content_scenes_service.py`](../Project/python_services/services/content_scenes_service.py)
- [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)

### `image`

**Role**

Generates images for:

- slideshow scenes
- tutorial scenes
- persona avatar stills
- optional upscale paths

**Flow**

1. receive prompt and model choice
2. call the active image provider
3. normalize output
4. pass image URL into downstream pipeline

**Status**

- `Implemented`
- `Validated`

**What is already implemented**

- provider-backed image generation through `FalAIService`
- image generation
- video generation wrapper
- upscale wrapper
- scene image activity
- repo documents the current `fal.ai` implementation as the strongest validated provider slice

**Current provider reality**

The skill name is intentionally provider-neutral.

Current implementation in this repo is backed by `fal.ai`, but the skill should remain `image` so the pipeline contract stays stable even if the provider changes later.

**Code refs**

- [`../Project/python_services/services/fal_service.py`](../Project/python_services/services/fal_service.py)
- [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)
- [`./CURRENT_REPO_STATUS.md`](./CURRENT_REPO_STATUS.md)
- [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md)

### `google-tts`

**Role**

Generates narration audio from script text.

**Flow**

1. receive script and voice config
2. call Google TTS
3. return audio bytes
4. upload to storage or hand off to downstream lane

**Status**

- `Implemented`

**What is already implemented**

- `GoogleTTSService`
- media activity wrapper
- smoke test script

**Current validation note**

The code path exists, but real validation still depends on working Google API enablement and credentials.

**Code refs**

- [`../Project/python_services/services/google_tts_service.py`](../Project/python_services/services/google_tts_service.py)
- [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)
- [`../Project/python_services/scripts/smoke_tts.py`](../Project/python_services/scripts/smoke_tts.py)

### `heygen-video`

**Role**

Generates talking-head output from avatar plus audio.

**Flow**

1. receive `avatar_id` and `audio_url`
2. create HeyGen video job
3. poll job status until terminal state
4. return talking-head video URL

This skill also covers avatar creation support used by `persona-setup`.

**Status**

- `Implemented`

**What is already implemented**

- create avatar
- create talking-head video
- poll video status
- live remaining quota fetch
- media activity wrapper
- smoke script

**Code refs**

- [`../Project/python_services/services/heygen_service.py`](../Project/python_services/services/heygen_service.py)
- [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)
- [`../Project/python_services/scripts/smoke_heygen.py`](../Project/python_services/scripts/smoke_heygen.py)

### `ffmpeg-assembly`

**Role**

Assembles the final vertical video from generated assets.

**Flow**

1. download remote assets locally
2. build slideshow or top-half visual track
3. stack with HeyGen bottom-half video
4. mux narration audio
5. upload final MP4 to R2

**Status**

- `Implemented`

**What is already implemented**

- deterministic local assembly helpers
- ffmpeg command execution
- split-screen build activity
- smoke assembly script

**Current validation note**

Real execution still depends on having valid media URLs and local ffmpeg available.

**Code refs**

- [`../Project/python_services/activities/video_activities.py`](../Project/python_services/activities/video_activities.py)
- [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)
- [`../Project/python_services/scripts/smoke_assembly.py`](../Project/python_services/scripts/smoke_assembly.py)

## Content Strategy

### `weekly-plan`

**Role**

Generates a weekly content plan for the broader marketing workflow.

**Flow**

1. receive `user_id` and `brand_config`
2. generate weekly strategy
3. send for approval
4. continue into media and publishing lanes

**Status**

- `Implemented`

**What is already implemented**

- weekly strategy activity
- weekly marketing workflow integration
- approval compatibility path

**Code refs**

- [`../Project/python_services/activities/strategy_activities.py`](../Project/python_services/activities/strategy_activities.py)
- [`../Project/python_services/workflows/weekly_marketing_workflow.py`](../Project/python_services/workflows/weekly_marketing_workflow.py)

### `carousel-plan`

**Role**

Generates structured JSON for image carousel content.

**Flow**

1. receive `app_name`, `topic`, `persona_config`, `platform`
2. generate `slides[]`
3. return:
   - `image_prompt`
   - `caption`
   - `cta_overlay`
   - `platform_caption`
   - `hashtags`

**Status**

- `Implemented`
- `Validated`

**What is already implemented**

- dedicated strategy activity
- smoke test coverage through `smoke_strategies.py`

**Code refs**

- [`../Project/python_services/activities/strategy_activities.py`](../Project/python_services/activities/strategy_activities.py)
- [`../Project/python_services/scripts/smoke_strategies.py`](../Project/python_services/scripts/smoke_strategies.py)

### `long-post-plan`

**Role**

Generates structured JSON for long-form content.

**Flow**

1. receive `app_name`, `topic`, `persona_config`, `platform`
2. generate:
   - `hero_image_prompt`
   - `title`
   - `body`
   - `meta_description`
   - `hashtags`
   - `cta`

**Status**

- `Implemented`
- `Validated`

**What is already implemented**

- dedicated strategy activity
- smoke test coverage through `smoke_strategies.py`

**Code refs**

- [`../Project/python_services/activities/strategy_activities.py`](../Project/python_services/activities/strategy_activities.py)
- [`../Project/python_services/scripts/smoke_strategies.py`](../Project/python_services/scripts/smoke_strategies.py)

## Infra

### `r2-storage`

**Role**

Handles media artifact storage in Cloudflare R2.

**Flow**

1. receive image/audio/video bytes or file-like content
2. upload to R2
3. return public URL or storage key
4. support delete/list operations

**Status**

- `Implemented`

**What is already implemented**

- `StorageService`
- upload
- delete
- list files
- smoke script

**Code refs**

- [`../Project/python_services/services/storage_service.py`](../Project/python_services/services/storage_service.py)
- [`../Project/python_services/scripts/smoke_storage.py`](../Project/python_services/scripts/smoke_storage.py)

### `quota-monitor`

**Role**

Tracks provider usage and quota state for operators and dashboard surfaces.

**Flow**

1. provider call happens at wrapper boundary
2. runtime usage is recorded
3. quota snapshots are stored
4. summary and detail are exposed through `/api/quota/*`
5. dashboard reads quota state

**Status**

- `Implemented`

**What is already implemented**

- provider catalog
- runtime usage recording
- summary/detail aggregation
- live HeyGen remaining quota refresh
- API endpoints
- documented dashboard integration

**Code refs**

- [`../Project/python_services/services/quota_monitor_service.py`](../Project/python_services/services/quota_monitor_service.py)
- [`../Project/python_services/api/quota.py`](../Project/python_services/api/quota.py)
- [`./CURRENT_REPO_STATUS.md`](./CURRENT_REPO_STATUS.md)

## Operator Interface

### `telegram-approval`

**Role**

Owns the human-in-the-loop Telegram interaction layer.

**Flow**

1. send script approval request
2. poll approval status
3. send final preview
4. poll publish decision

**Status**

- `Implemented`

**What is already implemented**

- Telegram service
- approval request state
- approval polling
- preview send
- publish decision wait path

**Code refs**

- [`../Project/python_services/services/telegram_service.py`](../Project/python_services/services/telegram_service.py)
- [`../Project/python_services/activities/approval_activities.py`](../Project/python_services/activities/approval_activities.py)

### `persona-setup`

**Role**

Prepares a persona once so the expensive video lane can reuse a ready avatar.

**Flow**

1. choose branch:
   - `Create New Persona`
   - `Choose Existing Persona`
2. if creating new:
   - collect persona ID
   - collect language and voice
   - collect appearance prompt or real photo
   - generate avatar preview through the active image provider
   - allow `Use`, `Regenerate`, or `Cancel`
   - upload avatar to R2
   - create HeyGen avatar
   - persist persona metadata and readiness
3. if choosing existing:
   - load personas from DB
   - show current status and summary
   - if `ready`, allow `Create Video Now`, `Details`, or `Rebuild Avatar`
   - if `generating` or `failed`, show the appropriate next action
4. before video generation:
   - confirm persona readiness
   - reuse stored `heygen_avatar_id`

**Status**

- `Partial`

**Why it is partial**

The scripts exist, but they still use `DEMO_PERSONAS` in memory rather than a real production persistence path.

**What is already implemented**

- setup script
- readiness check script
- image -> R2 -> HeyGen setup flow

**What is still missing**

- real DB-backed persona load/update flow
- persona picker service for Telegram menus
- shared registry layer used by both `/persona_setup` and `/video`
- full production-safe persistence and idempotency path

**Code refs**

- [`../Project/python_services/scripts/setup_persona.py`](../Project/python_services/scripts/setup_persona.py)
- [`../Project/python_services/scripts/check_persona.py`](../Project/python_services/scripts/check_persona.py)
- [`../Project/python_services/services/heygen_service.py`](../Project/python_services/services/heygen_service.py)
- [`../Project/python_services/services/fal_service.py`](../Project/python_services/services/fal_service.py)
- [`../Project/python_services/services/storage_service.py`](../Project/python_services/services/storage_service.py)

**Recommended UX**

`/persona_setup`

- bot shows:
  - `Create New Persona`
  - `Choose Existing Persona`

For `Create New Persona`, the bot should:

1. ask for persona ID
2. ask for language
3. ask for voice
4. ask for appearance prompt or photo
5. generate avatar preview
6. allow:
   - `Use`
   - `Regenerate`
   - `Cancel`
7. register in HeyGen
8. save DB state

For `Choose Existing Persona`, the bot should:

1. query personas from DB
2. show status-aware cards
3. allow:
   - `Create Video Now`
   - `View Details`
   - `Rebuild Avatar`

### Inline Persona Picker In `/video`

`/video -> AI Influencer` should not require users to leave the video flow just to pick a persona.

Recommended flow:

1. user chooses `AI Influencer Video`
2. bot shows ready personas from DB
3. bot also shows `Create New Persona`
4. if user chooses a ready persona, continue directly to topic and tone collection
5. if user chooses `Create New Persona`, branch into the create-persona flow and return to `/video`

This keeps the main content flow fast while still allowing operator setup in-context.

### Shared Query Policy

The persona picker inside `/video` and the existing-persona branch inside `/persona_setup` should use the same query logic.

Suggested behavior:

- `/video -> AI Influencer`
  - show only personas with `status=ready`
  - also show `Create New Persona`
- `/persona_setup`
  - show all personas
  - expose actions based on state:
    - `ready`
    - `generating`
    - `failed`
    - `pending`
    - `rebuilding`

This avoids duplicate logic and keeps persona handling consistent across bot flows.

### `postiz-publish`

**Role**

Publishes or schedules approved content through Postiz and keeps publishing state normalized.

**Flow**

1. receive approved content and media URLs
2. upload media where needed
3. publish or schedule through Postiz
4. persist returned publish state
5. expose state to workflow/dashboard surfaces

**Status**

- `Implemented`

**What is already implemented**

- Postiz service wrapper
- publish
- get post status
- delete post
- analytics fetch
- repo status documentation around persisted publishing state

**Code refs**

- [`../Project/python_services/services/postiz_service.py`](../Project/python_services/services/postiz_service.py)
- [`./CURRENT_REPO_STATUS.md`](./CURRENT_REPO_STATUS.md)

## Telegram UX Recommendation

### Recommended direction

Use `menu-driven first`, with `shortcut syntax` as an optional fast path.

Recommended behavior:

- first-time or casual users enter `/video`
- bot presents menu options and collects missing parameters
- experienced users can use shortcuts like `/video_ai` or `/video_ai again`

### Why this is the better fit for the repo

- the repo already has reusable internal skills
- the repo already has approval and quota primitives
- the repo does not yet have a strong public command router or conversation state layer
- a menu-driven entry layer can sit cleanly on top of the current architecture

### Current implementation reality

The repo already supports:

- approval request sending
- approval polling
- publish decision polling
- quota summary APIs

The repo does not yet fully support:

- Telegram command routing by content type
- conversation state management for multi-step menus
- last-used config or `again` behavior
- per-entry-mode prompt template registry
- DB-backed persona picker reused across `/persona_setup` and `/video`

That means the design direction is sound, but the menu system itself is still an implementation target.

### Suggested Conversation State

The Telegram session store should keep structured state instead of only raw text history.

Example session shape:

```python
{
  "entry_mode": "video_ai",
  "step_key": "enter_topic",
  "collected": {
    "video_type": "ai_influencer",
    "persona_id": "minh_vn",
    "topic": None,
    "tone": None
  }
}
```

For `/persona_setup`, example:

```python
{
  "entry_mode": "persona_setup",
  "step_key": "choose_branch",
  "collected": {
    "branch": "create_new",
    "persona_id": "minh_vn",
    "language": "vi-VN",
    "voice": "vi-VN-Wavenet-D",
    "appearance_prompt": None,
    "photo_upload": None
  }
}
```

Using `step_key` is better than numeric step counters because the flow is easier to evolve without breaking old sessions.

## Final Assessment

### Skills that are cleanest to use right now

- `script-gen`
- `image`
- `google-tts`
- `heygen-video`
- `ffmpeg-assembly`
- `weekly-plan`
- `carousel-plan`
- `long-post-plan`
- `r2-storage`
- `quota-monitor`
- `telegram-approval`
- `postiz-publish`

### Skills that are correct but still need consolidation

- `video-orchestrator`
- `scene-builder`
- `persona-setup`

### Best near-term product shape

If this repo continues in the current direction, the cleanest public operator surface is:

- `/video`
- `/carousel`
- `/long_post`
- `/weekly_plan`
- `/persona_setup`
- `/quota`
- `/publish`

Internally, those commands should dispatch to the skill set defined in this document.

## Suggested Reading Order

1. [`./CURRENT_REPO_STATUS.md`](./CURRENT_REPO_STATUS.md)
2. [`./TRIPC_VIDEO_PIPELINE_V2_REVIEW.md`](./TRIPC_VIDEO_PIPELINE_V2_REVIEW.md)
3. [`../Project/python_services/activities/approval_activities.py`](../Project/python_services/activities/approval_activities.py)
4. [`../Project/python_services/activities/media_activities.py`](../Project/python_services/activities/media_activities.py)
5. [`../Project/python_services/activities/video_activities.py`](../Project/python_services/activities/video_activities.py)
6. [`../Project/python_services/services/script_service.py`](../Project/python_services/services/script_service.py)
7. [`../Project/python_services/services/fal_service.py`](../Project/python_services/services/fal_service.py)
8. [`../Project/python_services/services/google_tts_service.py`](../Project/python_services/services/google_tts_service.py)
9. [`../Project/python_services/services/heygen_service.py`](../Project/python_services/services/heygen_service.py)
10. [`../Project/python_services/services/quota_monitor_service.py`](../Project/python_services/services/quota_monitor_service.py)
