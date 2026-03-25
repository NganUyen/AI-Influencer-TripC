# TripC Media / Video Pipeline Master Summary

## 1. Purpose

This document is the single summary of the TripC backend media/video pipeline.

It exists to help the team:

- understand the current backend logic
- know which parts are already implemented
- know which parts are still missing
- freeze one canonical pipeline before building Telegram/OpenClaw skills

This document is intentionally backend-first.

It does not describe UI polish or product copy. It describes:

- execution flow
- contracts
- orchestration
- storage
- approval logic
- integration boundaries for future skills

## 2. What This System Is

The TripC media/video pipeline is the backend system that turns:

- a topic
- a persona
- a platform target

into:

- a script
- scene prompts
- generated media assets
- a final assembled short-form vertical video
- a human approval decision

The intended operator surface is Telegram.

The intended automation/orchestration surface is:

- backend APIs
- Temporal workflows
- later: Telegram skills / OpenClaw skills

## 3. System Boundary

The pipeline currently spans these backend areas:

- FastAPI API layer
- Temporal workflow/activity layer
- provider service layer
- storage layer
- Telegram approval layer

Main code areas:

- `Project/python_services/main.py`
- `Project/python_services/api/media.py`
- `Project/python_services/api/workflows.py`
- `Project/python_services/workflows/weekly_marketing_workflow.py`
- `Project/python_services/activities/strategy_activities.py`
- `Project/python_services/activities/media_activities.py`
- `Project/python_services/activities/video_activities.py`
- `Project/python_services/activities/approval_activities.py`
- `Project/python_services/services/script_service.py`
- `Project/python_services/services/contracts.py`
- `Project/python_services/services/storage_service.py`
- `Project/python_services/services/telegram_service.py`

## 4. Core Goal

The canonical target pipeline is:

1. receive topic + persona + platform intent
2. generate a validated script and scene structure
3. ask for Telegram approval before expensive media generation
4. generate:
   - audio
   - scene images
   - talking-head video
5. assemble the final video through one canonical lane
6. upload final artifact to R2
7. send preview to Telegram
8. let operator decide save or discard

This is the pipeline that skills should eventually call.

## 5. Current Architecture

The current backend is split into four main layers.

### 5.1 Strategy Layer

Main file:

- `Project/python_services/activities/strategy_activities.py`

Responsibilities:

- generate weekly content strategy
- generate media prompts from strategy
- generate daily content
- generate carousel strategy
- generate long-post strategy

What this layer does:

- decides what content should exist
- generates planning output
- generates prompts and copy

What it does not do:

- assemble final videos
- upload final videos
- manage Telegram state

### 5.2 Media Asset Layer

Main file:

- `Project/python_services/activities/media_activities.py`

Responsibilities:

- image generation
- provider-side video generation
- audio generation
- talking-head video creation
- scene image generation
- generic storage upload for media assets

What this layer does:

- creates remote assets
- normalizes media payloads
- uploads some generated assets to R2

What it should not do:

- own final split-screen composition logic

### 5.3 Video Assembly Layer

Main file:

- `Project/python_services/activities/video_activities.py`

Responsibilities:

- accept image/audio/talking-head assets
- download them locally
- build slideshow
- add captions
- assemble final vertical video
- fallback to slideshow + audio when avatar is missing
- upload final MP4 to R2

This is the single canonical final assembly lane.

### 5.4 Approval / Operator Layer

Main files:

- `Project/python_services/activities/approval_activities.py`
- `Project/python_services/services/telegram_service.py`

Responsibilities:

- send approval requests to Telegram
- poll approval state
- send preview
- collect operator decision

## 6. Provider Map

The backend currently uses multiple provider services.

### 6.1 OpenClaw

Used in:

- `generate_weekly_strategy()`

Role:

- strategy and planning

OpenClaw is not currently the final video assembly engine.

### 6.2 AIService

Used in:

- prompt generation
- copy generation
- script generation through `ScriptService`
- carousel/long-post generation

Role:

- language generation
- structured JSON generation

### 6.3 fal.ai

Used through:

- `FalAIService`

Role:

- image generation
- provider-side video generation
- scene image generation

### 6.4 Google TTS

Used through:

- `GoogleTTSService`

Role:

- narration audio generation

### 6.5 HeyGen

Used through:

- `HeyGenService`

Role:

- talking-head video generation

### 6.6 Cloudflare R2

Used through:

- `StorageService`

Role:

- store generated audio
- store uploaded provider assets
- store final assembled video

### 6.7 Telegram

Used through:

- `TelegramService`

Role:

- approval and operator interaction

## 7. Current Backend Entry Points

## 7.1 API Prefixes

Registered in:

- `Project/python_services/main.py`

Relevant prefixes:

- `/api/media`
- `/api/workflows`

## 7.2 Media API

Defined in:

- `Project/python_services/api/media.py`

Current endpoints:

- `POST /api/media/generate/image`
- `POST /api/media/generate/video`
- `POST /api/media/generate/audio`
- `GET /api/media/voices`
- `GET /api/media/storage/list`
- `POST /api/media/carousel`
  - input: `topic`, `platform`, optional `persona_id`, `tone`, `style`, `num_slides`
  - generates slide strategy, slide images, text-overlay artifacts, and manifest upload
  - returns a carousel artifact with rendered slide image URLs

These endpoints are useful for direct provider access and smoke validation.

The first five are direct provider/smoke endpoints. `POST /api/media/carousel` is a higher-level orchestration endpoint for the carousel lane.

## 7.3 Workflow API

Defined in:

- `Project/python_services/api/workflows.py`

Current endpoints:

- `POST /api/workflows/start-weekly`
- `POST /api/workflows/approve/{workflow_id}`
- `GET /api/workflows/status/{workflow_id}`
- `GET /api/workflows/list`
- `POST /api/workflows/cancel/{workflow_id}`
- `POST /api/workflows/start-video`
  - input: `persona_id`, `topic`, `tone`, `platform`, `telegram_chat_id`
  - validates persona readiness before starting
  - starts `ShortVideoWorkflow`
  - returns: `workflow_id`, `run_id`, `status`

## 7.4 Persona API

Persona lifecycle is part of the expected backend system, so the backend entrypoint section should define the minimum persona API surface as well.

Current reality:

- `persona_id` is treated as a first-class input in the short-video pipeline
- the persona API is implemented and stable

Implemented persona endpoints:

- `GET /api/personas`
- `POST /api/personas`
- `GET /api/personas/{persona_id}`
- `PATCH /api/personas/{persona_id}`
- `GET /api/personas/{persona_id}/readiness`

How these endpoints connect to the pipeline:

- setup flow uses persona create + avatar/register endpoints
- reuse flow uses persona list/readiness endpoints
- `POST /api/workflows/start-video` should accept `persona_id` coming from this persona API surface

## 8. Current Working Workflow

## 8.1 `WeeklyMarketingWorkflow`

Defined in:

- `Project/python_services/workflows/weekly_marketing_workflow.py`

Current run sequence:

1. generate weekly strategy
2. send Telegram approval for strategy
3. wait for approval signal
4. generate media prompts
5. generate media assets in parallel
6. upload assets to storage
7. schedule posts
8. spawn downstream publishing workflows

What it already covers:

- marketing strategy flow
- approval gate
- prompt-driven asset generation
- scheduling and distribution

What it does not cover:

- script-first short-video generation
- scene-based assembly
- talking-head + split-screen orchestration
- final Telegram preview decision for video

## 8.2 `ShortVideoWorkflow`

Defined in:

- `Project/python_services/workflows/short_video_workflow.py`

Registered in `worker.py`.

Execution order:

1. resolve persona (load `tts_voice`, `heygen_avatar_id` from DB)
2. `generate_and_send_script_for_approval()`
3. `wait_for_script_approval()`
4. Stage A — parallel: `generate_audio()` + `generate_scene_images()`
5. Stage B — sequential: `create_talking_head_video()` (uses audio URL from Stage A)
6. `build_split_screen_video()`
7. `send_preview_to_telegram()`
8. `wait_for_publish_decision()`
9. return `FinalVideoContract`

Status progression:

`queued` → `waiting_script_approval` → `generating_assets` → `assembling` → `waiting_final_decision` → `completed` / `discarded` / `failed`

All exit paths return a strict `FinalVideoContract` shape with `workflow_id`, `persona_id`, `topic`, `video_url`, `storage_key`, and `metadata.reason`.

## 8.3 Child Workflows

Also in `weekly_marketing_workflow.py`:

- `PostPublishingWorkflow`
- `EngagementSyndicateWorkflow`

These are publishing/distribution workflows, not short-video construction workflows.

## 9. Script Layer

## 9.1 `ScriptService`

Defined in:

- `Project/python_services/services/script_service.py`

Purpose:

- generate a structured and validated short-video script

Output contract:

- `ScriptContract`

Shape:

```json
{
  "script": "narration text",
  "duration_estimate": 45.0,
  "scenes": [
    {
      "id": 1,
      "timestamp_start": 0.0,
      "timestamp_end": 6.0,
      "caption": "overlay text",
      "prompt": "visual prompt"
    }
  ]
}
```

Behavior:

- calls AI model
- strips code fences if needed
- parses JSON
- validates with Pydantic
- raises:
  - `ScriptGenerationError`
  - `ScriptContractError`

This is currently one of the cleanest and most stable parts of the newer pipeline.

## 10. Media Asset Layer Details

## 10.1 Shared Helpers

In `media_activities.py`:

- `_prompt_metadata()`
- `_prompt_voice()`

Purpose:

- normalize mixed legacy/new prompt payloads

Current target structure:

```json
{
  "type": "...",
  "prompt": "...",
  "metadata": {
    "day": 1,
    "platform": "tiktok"
  },
  "config": {
    "voice": "vi-VN-Wavenet-D",
    "duration": 5,
    "fps": 24
  }
}
```

Compatibility fallback still exists:

- top-level `day`
- top-level `platform`
- top-level `voice_id`

The long-term target should use nested fields only.

## 10.2 `generate_image()`

Purpose:

- generate image asset using fal.ai

Input:

- `ImageInput`

Output:

```json
{
  "type": "image",
  "service": "fal_ai",
  "url": "...",
  "status": "completed",
  "data": {...},
  "metadata": {...}
}
```

Important runtime behavior:

- validates normalized input
- closes `FalAIService`
- maps 4xx provider failures to non-retryable `ApplicationError`

## 10.3 `generate_video()`

Purpose:

- generate provider-side video using fal.ai video models

Input:

- `VideoInput`

Output:

```json
{
  "type": "video",
  "service": "fal_ai",
  "url": "...",
  "status": "completed",
  "data": {...},
  "metadata": {...}
}
```

Important note:

- this is not the final TripC assembled video
- this is only a provider-generated video asset

## 10.4 `generate_audio()`

Purpose:

- generate narration audio using Google TTS
- upload MP3 to R2 immediately

Input:

- `AudioInput`

Output:

```json
{
  "type": "audio",
  "service": "google_tts",
  "url": "...",
  "voice": "...",
  "metadata": {...},
  "status": "completed"
}
```

Important runtime behavior:

- the result URL is already an R2 URL
- this differs from image/video assets that may still be provider-hosted before upload

## 10.5 `upload_to_storage()`

Purpose:

- normalize external asset upload into R2

Behavior:

1. download `media_asset["url"]`
2. derive filename from metadata
3. upload through `StorageService.upload()`
4. return original asset plus `storage_url`

This is used heavily by the current weekly workflow.

## 10.6 `create_talking_head_video()`

Purpose:

- create a talking-head video through HeyGen
- upload the result to R2

Input:

- `avatar_id`
- `audio_url`
- `background`
- `day`
- `topic`

Output:

```json
{
  "type": "talking_head_video",
  "url": "...",
  "storage_url": "...",
  "heygen_video_id": "...",
  "status": "completed",
  "day": 1,
  "topic": "...",
  "metadata": {...}
}
```

Role:

- lower-half avatar input for final assembly

## 10.7 `generate_scene_images()`

Purpose:

- generate scene images in parallel from scene definitions

Expected scene input:

- `image_prompt`
- optional `config.model`

Output:

- original scenes enriched with:
  - `image_url`
  - `status`

Role:

- source of `image_urls` for the final video assembly lane

## 10.8 Compatibility Wrappers Still Present

Still present in `media_activities.py`:

- `create_slideshow()`
- `create_split_screen_video()`

Current behavior:

- both delegate to `build_split_screen_video()`

Important note:

- they are not canonical
- they only exist as compatibility shims
- if no real runtime caller depends on them, they should be removed later

## 11. Video Assembly Layer Details

## 11.1 Canonical Lane

Defined in:

- `Project/python_services/activities/video_activities.py`

Canonical activity:

- `build_split_screen_video()`

This is the single final video assembly path.

## 11.2 Input Contract

Input type:

- `SplitScreenVideoInput`

Shape:

```json
{
  "image_urls": ["..."],
  "audio_url": "...",
  "talking_head_url": "...",
  "scene_captions": ["..."],
  "persona_id": "persona-123",
  "topic": "topic-name",
  "duration_per_image": 4.0
}
```

Required:

- `image_urls`
- `audio_url`

Optional:

- `talking_head_url`
- `scene_captions`

## 11.3 Assembly Steps

### Step 1. Validate input

- Pydantic validation through `SplitScreenVideoInput`
- fail fast if image or audio is missing

### Step 2. Download assets

Required:

- images
- audio

Optional:

- talking head

Helpers:

- `_download_required()`
- `_download_optional()`

### Step 3. Build slideshow

Produces:

- `concat.txt`
- slideshow MP4

Rendering:

- top-half style preparation at `1080x960`
- libx264
- yuv420p

### Step 4. Add captions

If captions exist:

- timed caption overlays are applied by image slot

### Step 5. Final assembly

If talking head is available:

- split-screen mode
- top = slideshow
- bottom = talking head
- narration audio muxed in

If talking head is missing or optional download fails:

- slideshow + audio fallback mode

This fallback is intentional and required.

The pipeline must not fail only because the avatar asset is unavailable.

### Step 6. Validate final file

- file must exist
- file must be above a minimum size threshold

### Step 7. Upload to R2

- uses `StorageService.upload_bytes()`

Storage key pattern:

- `videos/{persona_id}/{safe_topic}_final.mp4`

## 11.4 Final Output Contract

Returned as `FinalVideoContract`.

Shape:

```json
{
  "type": "video",
  "url": "...",
  "video_url": "...",
  "preview_url": "...",
  "storage_key": "...",
  "metadata": {
    "image_urls": ["..."],
    "audio_url": "...",
    "talking_head_url": "...",
    "scene_captions": ["..."],
    "persona_id": "...",
    "topic": "...",
    "duration_per_image": 4.0,
    "assembly_mode": "split_screen",
    "used_talking_head": true
  },
  "status": "completed",
  "resolution": "1080x1920",
  "persona_id": "...",
  "topic": "..."
}
```

This is the artifact shape that future skills should depend on.

## 12. Storage Layer

Defined in:

- `Project/python_services/services/storage_service.py`

Available methods:

- `upload(file_data, filename, content_type, metadata=None)`
- `upload_bytes(data, filename, content_type, metadata=None)`
- `delete(filename)`
- `get_presigned_url(filename, expiration=3600)`
- `list_files(prefix="")`

Current usage:

- `generate_audio()` uploads MP3 directly
- `create_talking_head_video()` uploads bytes directly
- `build_split_screen_video()` uploads final video bytes directly
- `upload_to_storage()` uploads through the stream-based method

Storage design rule:

- use `upload()` for file-like streams
- use `upload_bytes()` for raw byte payloads

## 13. Contracts Used By The Pipeline

Defined in:

- `Project/python_services/services/contracts.py`

Important contracts:

- `SceneContract`
- `ScriptContract`
- `PromptMetadata`
- `MediaConfig`
- `ImageInput`
- `VideoInput`
- `AudioInput`
- `SplitScreenVideoInput`
- `VideoArtifact`
- `FinalVideoContract`

These are the shared schema layer for the backend pipeline.

## 14. Error Model

Defined in:

- `Project/python_services/services/errors.py`

Important error categories:

- `ScriptGenerationError`
- `ScriptContractError`
- `AssemblyError`
- `AssemblyMissingAssetError`
- `StorageUploadError`
- `PersonaConfigurationError`
- `PersonaNotReadyError`

Intent:

- keep retry behavior predictable
- separate retryable provider/network issues from structural non-retryable issues

At the activity level, many provider failures are also wrapped into `ApplicationError` for Temporal retry control.

## 15. Persona Lifecycle

This section describes the persona behavior that the backend pipeline is expected to support.

This is important because the short-video flow should not recreate avatar setup on every render.

The correct backend model is:

- setup persona once
- persist persona state
- reuse ready personas across many videos

## 15.1 Persona Principle

A persona is not just a label.

A persona should carry reusable video-generation state such as:

- stable `persona_id`
- display name
- language
- TTS voice
- avatar image
- HeyGen avatar binding
- readiness state

The pipeline should treat persona setup as a preparation phase, not as part of every video request.

## 15.2 Persona Setup Phase

This is the one-time setup flow for creating a reusable AI influencer persona.

Example user flow:

`/media -> Manage -> Personas -> Create`

Suggested setup sequence:

1. user enters `persona_id`
2. user chooses language and voice
3. user uploads avatar image or generates one from prompt
4. user previews avatar
5. user accepts, regenerates, or cancels
6. backend registers avatar with HeyGen
7. backend stores final persona state
8. persona becomes `ready`

Desired setup flow in detail:

### Step 1. Enter `persona_id`

Example:

- `minh_vn`

This should be the stable backend identifier used later by workflows and skills.

### Step 2. Choose language and voice

Examples:

- language: `Vietnamese`
- TTS voice: `vi-VN-Wavenet-D`

These values should be stored and reused later.

### Step 3. Create avatar image

Two allowed sources:

- upload real image
- generate AI image from prompt

This belongs to the image branch of the pipeline.

That image branch may include:

- image upload
- optional image normalization
- optional fal.ai avatar generation/refinement
- final avatar preview

### Step 4. Preview avatar

Expected operator actions:

- use
- regenerate
- cancel

Suggested buttons:

- `Use`
- `Generate Again`
- `Cancel`

### Step 5. Register avatar in HeyGen

The backend then creates or binds the persona to a HeyGen avatar and receives:

- `heygen_avatar_id`

This must be persisted because it is the key that makes persona reuse possible.

### Step 6. Persist persona record

After successful avatar registration, backend stores persona data and marks it ready for reuse.

Expected resulting state:

- `status = ready`

## 15.3 Persona Reuse Phase

This is the normal runtime behavior for every future video request.

Example user flow:

`/media -> Create Video -> AI Influencer`

Expected bot behavior:

- load personas from DB where `status = ready`
- present persona choices
- allow reuse without rebuilding avatar setup

Example selection UI:

- `Minh`
- `Linh`
- `Jake`
- `Create New`

When the user selects a ready persona such as `minh_vn`, the pipeline should reuse:

- `minh_vn.heygen_avatar_id`
- `minh_vn.tts_voice`
- `minh_vn.avatar_image_url`

It should not:

- recreate the HeyGen avatar
- ask for voice again
- regenerate avatar image again

## 15.4 Persona Data That Should Be Stored

The backend persona record should contain, at minimum:

- `persona_id`
- `display_name`
- `language`
- `tts_voice`
- `avatar_image_url`
- `avatar_source_type`
- `avatar_prompt` if AI-generated
- `heygen_avatar_id`
- `status`
- `created_at`
- `updated_at`

Recommended optional fields:

- `description`
- `tone_default`
- `market_default`
- `platform_defaults`
- `thumbnail_url`

## 15.5 Persona Status Model

The persona model should have explicit readiness states.

Recommended minimal states:

- `draft`
- `image_ready`
- `heygen_registered`
- `ready`
- `failed`

Meaning:

- `draft`: base record exists but setup incomplete
- `image_ready`: avatar image exists but HeyGen binding not done
- `heygen_registered`: HeyGen avatar exists but final confirmation not complete
- `ready`: persona is safe to use in short-video workflow
- `failed`: setup failed and needs operator review

For the first backend implementation, it is acceptable to simplify to:

- `draft`
- `ready`
- `failed`

But `ready` must mean:

- valid TTS voice exists
- avatar image exists
- `heygen_avatar_id` exists

## 15.6 Persona Readiness Contract

Before starting a short-video workflow, backend should validate:

- persona exists
- persona status is `ready`
- persona has a valid `heygen_avatar_id`
- persona has a valid TTS voice

If any of these fail, backend should stop before generation and return a non-retryable persona readiness error.

This maps naturally to:

- `PersonaConfigurationError`
- `PersonaNotReadyError`

## 15.7 How Persona Connects To Short-Video Workflow

The future `ShortVideoWorkflow` should consume `persona_id`, then resolve the persona record once at workflow start.

It should derive:

- language for script generation
- TTS voice for `generate_audio()`
- `heygen_avatar_id` for `create_talking_head_video()`
- optional defaults such as tone/market/platform hints

This means the workflow should not require the user to keep re-entering persona setup fields after the persona is ready.

## 15.8 OpenClaw / Telegram Skill Implication For Personas

Skills should treat personas as reusable backend resources.

What the skill should do:

- list ready personas
- let user choose one
- optionally offer `Create New`

What the skill should not do:

- rebuild avatar registration every time
- own persona persistence rules
- duplicate HeyGen registration logic

Backend should expose enough persona APIs/contracts so skills can:

- list personas
- create personas
- check persona readiness
- use persona by `persona_id` in `start-video`

## 15.9 Persona Summary

The correct persona model for this project is:

- create once
- store permanently
- reuse many times in short-video generation

This persona branch is a required part of the backend media/video system because the AI influencer video flow depends on stable reusable avatar state.

## 16. Telegram Approval Layer

## 16.1 Existing Capabilities

Current Telegram approval capabilities:

- send strategy approval request
- poll approval result
- send script approval request
- wait for script approval
- send preview request
- poll final decision

Current service behavior in `telegram_service.py`:

- sends inline-button Telegram messages
- stores approval state in memory
- handles callback types:
  - `approve_`
  - `reject_`
  - `edit_`
  - `save_`
  - `discard_`

## 16.2 Current Limitation

Preview callback types emitted by `send_preview_to_telegram()` that are not yet handled:

- `publish_tiktok_*`
- `publish_shorts_*`
- `schedule_*`

Preview decision callbacks `save_` and `discard_` are now wired. `publish_tiktok_` and `publish_shorts_` remain out of scope until the distribution layer is implemented.

## 16.3 State Limitation

Approval state is now backed by Redis with TTL 1800 seconds. Falls back to in-memory dict if Redis is unavailable.

## 17. Current Telegram/User Flows

## 17.1 Existing Weekly Flow

This exists today:

1. start weekly workflow
2. generate strategy
3. send strategy preview to Telegram
4. operator approves or rejects
5. generate assets
6. schedule content
7. downstream publishing workflows run

## 17.2 Intended Short-Video Flow

Target flow:

1. user chooses topic, persona, platform
2. generate script + scenes
3. send script to Telegram
4. operator approves or rejects
5. generate:
   - audio
   - scene images
   - talking head
6. assemble final video
7. upload final artifact
8. send preview to Telegram
9. operator chooses save or discard

This is only partially wired in the current codebase.

## 17.3 Skill-Oriented Telegram Flow

For skills, Telegram should eventually behave like a structured input router:

1. collect required fields
2. validate them
3. start backend workflow
4. show status updates
5. ask for approval at checkpoints
6. show final result and action buttons

This requires a real Telegram session layer, not only callback storage.

## 18. What Is Implemented Today

These backend parts are already credible and usable as building blocks:

- script generation and validation
- image generation
- provider-side video generation
- audio generation
- talking-head creation
- scene image generation
- canonical final assembly lane
- R2 upload logic
- weekly strategy workflow
- approval activity pattern
- `ShortVideoWorkflow` (end-to-end orchestration)
- persona API (CRUD + readiness check)
- Redis-backed Telegram approval state
- `POST /api/workflows/start-video`
- `POST /api/media/carousel`

## 19. What Is Not Fully Implemented Yet

These parts still block the short-video pipeline from being a fully skill-ready system:

- compatibility wrappers still exist (`create_slideshow`, `create_split_screen_video`)
- no skill-facing workflow status contract yet
- distribution/publish layer not implemented (TikTok, YouTube Shorts)

## 20. Minimum Pre-Skills Gaps

These are the three concrete gaps that had to be fixed before the short-video pipeline could be treated as callable by skills.

### Gap 1. `ShortVideoWorkflow`

Status: **implemented**

Workflow is defined in `workflows/short_video_workflow.py` and registered in `worker.py`.

### Gap 2. Telegram Approval State Is In-Memory

Status: **implemented**

Approval state is now backed by Redis with TTL 1800 seconds. Falls back to in-memory dict if Redis is unavailable.

### Gap 3. Start Endpoint For Video Workflow

Status: **implemented**

`POST /api/workflows/start-video` is defined in `api/workflows.py`, validates persona readiness, and starts `ShortVideoWorkflow`.

All three pre-skills gaps are now closed. The short-video pipeline is callable by skills.

## 21. Canonical Target Pipeline To Freeze

This is the recommended official backend pipeline.

1. resolve persona and input fields
2. generate script through `ScriptService`
3. send script approval to Telegram
4. wait for approval
5. generate audio
6. generate scene images
7. generate talking head
8. assemble final video via `build_split_screen_video()`
9. upload final artifact
10. send preview to Telegram
11. wait for save/discard
12. return final artifact state

Canonical contracts for this pipeline:

- `ScriptContract`
- `AudioInput`
- `ImageInput`
- `SplitScreenVideoInput`
- `FinalVideoContract`

Canonical final artifact shape:

```json
{
  "type": "video",
  "url": "...",
  "storage_key": "...",
  "metadata": {...},
  "status": "completed"
}
```

## 22. OpenClaw Skill Integration Notes

This section matters specifically for future OpenClaw / Telegram skills.

## 22.1 What OpenClaw Should Be Responsible For

OpenClaw skills should be responsible for:

- collecting structured user intent
- routing the request to the correct backend workflow entrypoint
- showing progress and results
- optionally helping choose persona/topic/platform defaults

OpenClaw should not own:

- ffmpeg assembly logic
- provider-specific asset generation logic
- storage upload logic
- Telegram approval persistence

Those belong to the backend pipeline.

## 22.2 What The Backend Should Expose To Skills

At minimum, the backend should expose:

- `POST /api/workflows/start-video`
- workflow status query endpoint
- final artifact contract
- persona lookup/readiness contract

Skills should call backend orchestration, not recreate pipeline logic themselves.

## 22.3 Expected Skill Input Contract

The skill-facing request should eventually be formalized around fields like:

- `persona_id`
- `topic`
- `platform`
- `tone`
- optional duration/style hints

Skills should pass clean, validated inputs into backend workflow start.

## 22.4 Expected Skill Status Contract

Skills will likely need stable statuses such as:

- `queued`
- `waiting_script_approval`
- `generating_assets`
- `assembling`
- `waiting_final_decision`
- `completed`
- `discarded`
- `failed`

This status contract is not fully formalized in code yet, but should be added before the skills layer becomes final.

## 23. Readiness Summary

## 23.1 Stable Enough Now

These parts are stable enough to keep as the foundation:

- `ScriptService`
- `generate_image()`
- `generate_video()`
- `generate_audio()`
- `create_talking_head_video()`
- `generate_scene_images()`
- `build_split_screen_video()`
- `StorageService`
- contract models in `contracts.py`

## 23.2 Must Be Finished Before Skills

These items were required before skills could be built. All three are now closed:

- ~~create `ShortVideoWorkflow`~~ — implemented
- ~~add Redis-backed Telegram approval state~~ — implemented
- ~~add `POST /api/workflows/start-video`~~ — implemented

Remaining before full skill integration:

- define skill-facing request/status contracts
- define persona readiness flow clearly (done for API, needs skill-facing formalization)

## 24. Final Conclusion

The backend now has a complete short-video pipeline foundation.

What is now true:

- one canonical assembly lane: `build_split_screen_video()`
- one dedicated short-video workflow: `ShortVideoWorkflow`
- one stable video start endpoint: `POST /api/workflows/start-video`
- persona lifecycle with DB-backed registry
- Redis-backed durable approval state
- script and preview approval via Telegram

What is still not implemented:

- distribution/publish layer (TikTok, YouTube Shorts)
- long-post assembly endpoint
- OpenClaw/Telegram skill routing layer
- conversation state management for multi-step menus

Current prioritization note:

- keep `ShortVideoWorkflow` / `POST /api/workflows/start-video` as the primary video lane for OpenClaw integration
- defer a separate tutorial lane until there is a concrete need beyond the existing short-video flow
- defer long-post integration until a dedicated backend endpoint exists

The pipeline is now stable enough for Telegram/OpenClaw skill integration. Build skills on top of this foundation without modifying pipeline internals.
