# TripC Video Pipeline v2

## Summary

This document is the implementation plan for the TripC AI short-video pipeline based on the current repository state.

It is intentionally written as a forward-looking integration plan, not as a status report.

Important baseline assumptions:

- provider API keys and environment variables already exist in `.env`
- backend API scaffolding already exists in the repo
- workflow and activity structure already exists in the repo
- the only media logic that has actually been implemented and tested in isolation is the `fal.ai` image path

Everything else in this document should be treated as the next integration target, not as already completed work.

## Current Codebase Starting Point

The current repository already provides the following foundation:

- FastAPI backend structure under `Project/python_services/api`
- Temporal workflow/activity structure under `Project/python_services/workflows` and `Project/python_services/activities`
- shared settings/config loading under `Project/python_services/config/settings.py`
- media API routes in `Project/python_services/api/media.py`
- storage integration scaffold in `Project/python_services/services/storage_service.py`
- Telegram service scaffold in `Project/python_services/services/telegram_service.py`
- persona-related database tables already present in Supabase schema

The only provider path that is currently implemented at the logic level is:

- `fal.ai` image generation in `Project/python_services/services/fal_service.py`

That path already has:

- isolated service logic
- API route wiring
- activity wiring
- smoke test script
- pytest coverage for service/API/activity contract

This means the repository is ready for incremental provider integration, but not yet ready for a full end-to-end short-video pipeline.

## Target End-to-End Pipeline

The intended production pipeline is:

1. User submits a topic and persona through Telegram or a backend entrypoint.
2. Backend loads persona configuration from database.
3. GPT-4 generates:
   - short-form script
   - duration estimate
   - scene list
   - visual prompts
4. Telegram sends the generated script back for approval.
5. After approval, media generation starts:
   - TTS narration
   - scene images
   - talking-head video
6. ffmpeg assembles final split-screen 9:16 video.
7. Final video uploads to Cloudflare R2.
8. Telegram sends preview link.
9. Publish action is triggered manually by the user.

The system should remain human-in-the-loop at the approval and publish stages.

## Pipeline Phases To Implement

### Phase 1: Script Generation And Approval

Goal:

- turn `persona_id + topic` into approved structured content for downstream media generation

Implementation shape:

- add a script-generation service on top of the existing `AIService`
- define a strict JSON output contract:
  - `script`
  - `duration_estimate`
  - `scenes[]`
- each scene should contain:
  - `id`
  - `timestamp_start`
  - `timestamp_end`
  - `caption`
  - `prompt`
- approval should go through the existing Telegram integration pattern
- approval state should map cleanly into Temporal signal/query flow

Codebase fit:

- should plug into the existing workflow structure rather than creating a parallel orchestration path
- should reuse current approval workflow concepts already present in backend code

### Phase 2: Media Generation Layer

Goal:

- generate all remote assets required for the final video

Media responsibilities:

- narration audio
- 5 scene images
- one talking-head video

Provider split:

- `AIService`:
  - script and prompt generation
- `Google TTS`:
  - narration audio generation
- `fal.ai`:
  - scene images
  - optional higher-quality avatar images for persona setup
- `HeyGen`:
  - talking-head video generation

Important implementation rule:

- every provider must follow the same pattern already used by `fal.ai`
  - service layer
  - normalized output contract
  - API entrypoint or smoke test path
  - activity adapter

Current repo reality:

- only `fal.ai` image generation follows that pattern today
- TTS and HeyGen should be added next using the same service-first approach

### Phase 3: Video Assembly

Goal:

- combine generated assets into one publish-ready vertical video

Assembly target:

- `1080x1920`
- split screen
- top half: slideshow + caption overlays+ animation video about promoting the product ( TRIPC ) 
- bottom half: HeyGen talking head
- AAC audio + H.264 video

Implementation shape:

- create a dedicated assembly activity, for example `video_activities.py`
- download remote assets locally into a temp working directory
- build slideshow from image sequence
- overlay timed captions from scene metadata
- stack top and bottom tracks
- mux narration audio
- upload final MP4 to R2

This phase should remain deterministic and local:

- ffmpeg should be the assembly engine
- provider services should only generate assets, not final video composition

### Phase 4: Preview And Publish

Goal:

- keep final publishing explicit and operator-controlled

Implementation shape:

- send preview URL back through Telegram
- expose actions like:
  - approve preview
  - publish TikTok
  - publish Shorts
- reuse Postiz integration where possible for scheduling/publishing
- do not auto-publish immediately after render without user approval

## Persona System Plan

The repo already contains a `personas` table, but it is not yet aligned with the proposed video pipeline needs.

Plan:

- extend the existing persona schema instead of replacing it
- add fields needed for:
  - language
  - TTS voice config
  - appearance prompt
  - avatar asset URL
  - `heygen_avatar_id`
  - readiness/setup state
  - optional market/locale targeting

Important constraint:

- persona setup should be a one-time preparation step
- video generation should reuse prepared assets and IDs
- the pipeline must not recreate avatars on every video request

Recommended separation:

- persona setup path:
  - generate avatar image
  - create/store HeyGen avatar
  - persist persona-ready metadata
- video execution path:
  - only load persona config and reuse stored assets

### Persona Setup Flow

The plan needs a concrete persona bootstrap path, not just a conceptual one-time setup statement.

Recommended file:

- `Project/python_services/scripts/setup_persona.py`

Recommended persona setup flow:

1. Load persona record by `persona_id`.
2. Validate that the persona has:
   - display identity fields
   - voice settings
   - appearance prompt
3. Mark persona status as `generating`.
4. Generate one high-quality avatar still image through `fal.ai`.
5. Upload or register that image with HeyGen.
6. Persist returned `heygen_avatar_id`.
7. Save:
   - `avatar_image_url`
   - `heygen_avatar_id`
   - `avatar_status = ready`
   - `last_setup_at`
8. Return a compact summary for operator confirmation.

Expected persona setup output:

- `persona_id`
- `avatar_image_url`
- `heygen_avatar_id`
- `avatar_status`

Important operational rules:

- persona setup must be idempotent
- rerunning setup should not silently create duplicate avatars unless explicitly requested
- failed setup should leave the persona in a recoverable state such as:
  - `pending`
  - `failed`
  - `generating`
- setup logs should make it obvious whether the failure occurred in:
  - image generation
  - HeyGen avatar creation
  - DB persistence

Recommended follow-up helper:

- `Project/python_services/scripts/check_persona.py`

Purpose:

- inspect whether a persona is actually ready for video execution before entering the expensive pipeline

## Model Strategy

The image model should not be treated as a single global default for all use cases.

Recommended use-case split:

- slideshow scene generation:
  - fast model
  - lower latency
- persona avatar generation:
  - higher quality still image model
- premium poster / ad generation:
  - higher reasoning/text-rendering model

For the current codebase:

- keep the implemented `fal.ai` image path generic enough to accept model overrides
- choose actual model defaults per call site, not only once globally

That keeps the service reusable for:

- scene image generation
- persona avatar generation
- marketing poster generation

## Contracts That Must Be Locked

To keep the pipeline stable, the following internal contracts should be formalized and reused consistently:

### Script contract

- `script`
- `duration_estimate`
- `scenes[]`

### Scene contract

- `id`
- `timestamp_start`
- `timestamp_end`
- `caption`
- `prompt`

### Audio contract

- `type`
- `url`
- `voice`
- optional duration metadata

### Image contract

- `type`
- `url`
- `width`
- `height`
- `model`
- `prompt`

### Talking-head video contract

- `type`
- `url`
- `avatar_id`
- optional duration/status metadata

### Final output contract

- `video_url`
- `preview_url`
- `storage_key`
- optional duration and publishing metadata

The current image path already establishes this pattern. The rest of the media pipeline should follow it exactly.

## Error Handling And Retry Strategy

The plan also needs an explicit failure strategy for expensive multi-provider execution.

The main rule should be:

- never rerun the whole pipeline blindly if only one expensive provider failed

### Failure handling principle

Each phase should persist its successful artifacts so the workflow can resume from the first failed dependency instead of restarting from zero cost.

Examples of persisted intermediate artifacts:

- approved script JSON
- scene prompts
- generated image URLs
- generated audio URL
- `heygen_video_url`
- final assembled video URL

### Provider-specific retry posture

`fal.ai` image generation

- retry transient HTTP/network failures
- do not retry clearly invalid prompt or authentication failures
- store successful image URLs immediately when each scene finishes

`Google TTS` or future TTS provider

- retry transient upstream/network issues
- do not retry invalid voice config or authentication failures
- persist audio URL once generated

`HeyGen`

- treat as long-running and expensive
- poll with bounded timeout
- retry only for transient transport or provider-status issues
- do not regenerate audio or images if HeyGen fails after those assets already succeeded
- rerun only the talking-head lane

`ffmpeg` assembly

- retry only after validating that all required local files are present
- treat missing asset inputs as non-retryable until upstream artifacts exist

### Temporal retry guidance

Recommended retry categories:

- retryable:
  - timeout
  - connection reset
  - temporary 5xx
  - provider polling timeout that is known to be transient
- non-retryable:
  - invalid API key
  - invalid model id
  - invalid persona configuration
  - missing required prompt/script data
  - policy/content rejection
  - malformed provider response that indicates a contract mismatch

Recommended workflow behavior if HeyGen fails late:

1. keep approved script
2. keep generated image URLs
3. keep generated audio URL
4. mark talking-head step as failed
5. allow operator or workflow retry to rerun only HeyGen and downstream assembly

That avoids paying for TTS and `fal.ai` again when those parts already succeeded.

### Recommended error types

The repo should gradually standardize provider errors into explicit classes, for example:

- `FalAIServiceError`
- `FalAIAuthError`
- `FalAIRetryableError`
- `TTSServiceError`
- `TTSAuthError`
- `HeyGenServiceError`
- `HeyGenTimeoutError`
- `HeyGenAuthError`
- `AssemblyError`
- `PersonaConfigurationError`

This matters because Temporal retry policy becomes much cleaner when non-retryable cases are named explicitly.

## Build Order For This Repo

The safest implementation order for this codebase is:

1. Finalize `fal.ai` image integration as the reference provider pattern.
2. Add `GoogleTTSService` with isolated smoke-test and normalized output.
3. Add `HeyGenService` with polling and isolated smoke-test.
4. Add ffmpeg-based assembly activity.
5. Expand persona schema through migration.
6. Add script-generation contract on top of `AIService`.
7. Integrate Telegram `/video` flow and approval loop.
8. Add preview/publish actions.

This order keeps each provider independently testable before it is embedded into Temporal orchestration.

## Provider Smoke-Test Checklist

Before a provider is integrated into Temporal workflow execution, it should have its own isolated smoke-test path.

### fal.ai image checklist

- service can call real provider successfully
- normalized response includes a usable `url`
- route contract is stable
- smoke test returns real JSON output
- at least one real output has been manually opened and inspected

### TTS checklist

- service can generate a real audio URL
- returned audio file is playable
- duration is reasonable for the script
- voice configuration is actually applied
- normalized output contract is stable

Recommended file:

- `Project/python_services/scripts/smoke_tts.py`

### HeyGen checklist

- avatar ID is valid
- provider accepts audio URL input
- polling reaches terminal state correctly
- successful run returns a playable video URL
- failure states are surfaced clearly
- timeout behavior is explicit and bounded

Recommended file:

- `Project/python_services/scripts/smoke_heygen.py`

### Storage checklist

- upload works for image
- upload works for audio
- upload works for video
- returned public URL is reachable
- delete and list behavior match expected bucket paths

Recommended file:

- `Project/python_services/scripts/smoke_storage.py`

### ffmpeg assembly checklist

- downloads all required media locally
- slideshow builds correctly
- captions appear at expected timestamps
- split-screen output is `1080x1920`
- final MP4 plays correctly
- final artifact uploads to R2 successfully

Recommended file:

- `Project/python_services/scripts/smoke_assembly.py`

Only after these isolated smoke tests pass should the provider be promoted from scaffolded integration into workflow-level execution.

## Documentation Rule For Future Work

This plan should avoid binary labels like `Done` unless a path has been both implemented and validated.

For this repo, use these terms only:

- `Scaffolded`
  - files/routes/settings structure exist
- `Integrated`
  - logic exists and is wired into the repo
- `Validated`
  - provider call or runtime behavior has been exercised successfully

Current reality at the time of writing:

- `fal.ai` image generation: integrated and validated in isolation
- everything else in the video pipeline: planned or scaffolded

## Final Recommendation

The proposed TripC short-video pipeline is valid and fits the architecture of this repository, but it should be implemented as an incremental provider-integration roadmap, not as a single “already-built” system.

The correct interpretation of the current codebase is:

- backend structure exists
- workflow structure exists
- environment scaffolding exists
- media API entrypoints exist
- image integration is the first completed reference slice

The next engineering objective is to replicate that same quality bar for:

- TTS
- HeyGen
- ffmpeg assembly
- persona setup
- Telegram-driven execution

Only after those slices are individually validated should the full video pipeline be considered operational.
