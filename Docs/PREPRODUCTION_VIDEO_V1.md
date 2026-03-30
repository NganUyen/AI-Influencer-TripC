# Video Pre-Production V1

Last verified: 2026-03-30 (UTC)

This document locks the recommended v1 pre-production design for the Telegram-driven AI influencer video lane.

## Current Implementation Status

The v1 pre-production lane is now implemented in the current codebase.

Implemented:

- `video-ai` no longer starts the old production workflow directly from Telegram
- deterministic Telegram collection flow for:
  - `persona_id`
  - `idea_brief`
  - `feature_focus`
  - `video_goal`
  - `audience`
  - `cta`
  - `reference_url`
  - `access_level`
- persona snapshot resolution before concept generation
- `ConceptBrief` generation through `CreativeDirectorService`
- `BeatSheet` generation through `CreativeDirectorService`
- two hard approval gates:
  - `confirm_concept`
  - `confirm_beats`
- in-session `ApprovedProductionPackage` artifact
- retryable failure handling for concept/beat generation
- safe stale-artifact cleanup before contract re-validation
- human-readable Telegram summaries for:
  - concept approval
  - beat approval
  - package-ready completion

Implemented quality guards:

- `ConceptBrief` must stay aligned with collected:
  - `feature_focus`
  - `video_goal`
  - `audience`
  - `cta`
  - `reference_url`
  - `access_level`
  - `platform`
- `tone_resolved` must follow persona `tone_default`, else fallback to `natural`
- `source_summary` must remain conservative
- `BeatSheet` must:
  - start with `hook`
  - end with `cta`
  - keep contiguous beat indices
  - avoid authenticated top-half capture when `access_level = public_page_only`
  - stay grounded on the approved `feature_focus`

Current test coverage:

- contract and quality validation for `ConceptBrief` and `BeatSheet`
- deterministic `video-ai` step ordering
- approval flow from concept to beat plan to package-ready state
- retryable failure behavior
- stale session artifact recovery
- Telegram renderer summaries for concept, beats, retry, and package-ready state

Current readiness:

- implemented and actively used as the production handoff shape for the Telegram `video-ai` lane
- approved packages now start production through `/api/workflows/start-video`
- not a claim that every provider-backed deployed path has already been smoke-tested in every environment

## Goal

Build a lightweight pre-production layer that prevents content drift before the existing short-video production workflow spends quota on:

- script generation
- TTS
- fal.ai image generation
- HeyGen talking-head generation
- final video assembly

The v1 target is not a full script editor or a full top-half runtime planner yet.

## V1 Scope Decision

V1 supports exactly one creative input mode:

- `idea_brief`

V1 does not support these modes yet:

- `script_input`
- `image_reference`
- `pdf_brief`

Reasoning:

- the current project needs a pre-production lock layer, not a multi-mode editing surface
- keeping a single mode avoids branching logic that does not match the current production pipeline
- the existing production lane still expects a narrow, structured handoff

## Why `idea_brief` Only

The main product risk today is mismatch between:

- what the persona says in the bottom half
- what the future top half should show

`idea_brief` is the cleanest way to solve that first because it forces the system to:

1. clarify what feature the video is about
2. clarify the business goal
3. clarify the intended audience
4. attach the source app/site context early
5. lock a shared structure before production starts

Supporting `script_input` in v1 would add another branch:

- preserve vs rewrite user script
- partial script validation
- script-to-brief conversion
- script-to-beat reconciliation

That is useful later, but it is not the highest-priority fit for the current repo.

## Source Requirement

Even though v1 is pre-production-first, the future top-half direction is screen capture from a real web/app source.

Because of that, `idea_brief` in v1 must collect:

- `reference_url`
- `access_level`

This keeps the data model aligned with the future top-half implementation without forcing top-half runtime work now.

`reference_url` is not the source of truth for the whole video.

The real source of truth is:

- approved `ConceptBrief`
- approved `BeatSheet`

The URL only grounds the concept and gives the system a target source to plan around.

## Persona Assumptions

The persona layer already stores fields needed for voice identity and production readiness, including:

- `language`
- `tts_voice`
- `tone_default`
- `heygen_avatar_id`

For v1 pre-production:

- `language` is resolved from the selected persona
- `tone_default` is used as the default tone
- no new persona-specific override logic is required in v1

This keeps the flow aligned with the existing persona registry and short-video workflow.

## V1 Data Contracts

### ConceptBrief

`ConceptBrief` is the video-level contract.

It answers:

- what the video is about
- who it is for
- what goal it serves
- what product/app/site it refers to
- what source access level exists

Recommended v1 shape:

```json
{
  "persona_id": "minh_vn",
  "creative_input_mode": "idea_brief",
  "feature_focus": "AI itinerary planner",
  "video_goal": "feature_demo",
  "audience": "travelers aged 22-35 who plan trips manually",
  "angle": "problem_solution",
  "platform": "tiktok",
  "cta": "Try TripC free",
  "reference_url": "https://tripc.ai",
  "access_level": "public_page_only",
  "source_summary": "TripC is presented as a travel planning product with itinerary and discovery features."
}
```

### BeatSheet

`BeatSheet` is the structure-level contract.

It answers:

- what each beat is doing
- what the bottom half must communicate
- what the future top half should use as its source target
- how long the beat lasts

It is not a full storyboard.

It should stay at the level of:

- narrative intent
- source type
- capture target
- capture hint
- overlay summary
- duration

Recommended v1 shape:

```json
{
  "concept_id": "cd_001",
  "beats": [
    {
      "idx": 3,
      "purpose": "feature_demo",
      "bottom_half_message": "TripC tự gom lịch trình chỉ trong vài giây.",
      "top_half_source_type": "public_page_capture",
      "top_half_target": "itinerary_planner_section",
      "top_half_capture_hint": "show planner UI or nearest public product section related to itinerary generation",
      "overlay_text": "AI builds your trip",
      "duration_sec": 5
    }
  ]
}
```

### ApprovedProductionPackage

Production should not ask the user for context again.

It should receive a single handoff package:

```json
{
  "concept_brief": {},
  "beat_sheet": {},
  "persona_snapshot": {}
}
```

This package is the only pre-production output that production should consume.

## Two Hard Approval Gates

V1 keeps two hard approval gates:

1. `ConceptBrief`
2. `BeatSheet`

Why both matter:

- approving only the concept is not enough because the user still does not see the narrative pacing
- approving only the beat structure without a clear concept causes feature drift
- two short gates are cheaper than generating mismatched media

V1 approval actions should stay simple:

- `Approve`
- `Edit`
- `Regenerate`

No beat-by-beat editor is required in v1.

## Beat Taxonomy

To keep outputs predictable, v1 should use a small fixed beat taxonomy:

- `hook`
- `problem`
- `solution_intro`
- `feature_demo`
- `product_positioning`
- `proof`
- `benefit`
- `expectation_setting`
- `cta`

The beat count should stay constrained:

- default: 5 beats
- optional: 6 beats for more complex demos

## Telegram V1 Flow

Recommended Telegram conversation flow:

1. user chooses `AI Influencer Video`
2. bot asks for persona
3. bot asks the core idea
4. bot asks for feature focus
5. bot asks for audience
6. bot asks for goal
7. bot asks for CTA
8. bot asks for `reference_url`
9. bot asks for `access_level`
10. system generates `ConceptBrief`
11. user approves or revises
12. system generates `BeatSheet`
13. user approves or revises
14. system builds `ApprovedProductionPackage`
15. production may start later from that package

V1 should use:

- free text for the idea
- inline keyboard for constrained options such as goal, angle, platform, and access level
- short human-readable summaries for approval

The bot should not show raw JSON to the user.

## Production Integration Rule

This is the key handoff rule:

- `BeatSheet` decides structure
- `ScriptService` decides wording

That means:

- production script generation must consume `ConceptBrief + BeatSheet`
- it must not invent a new structure from raw topic text
- it must keep narration aligned with approved `bottom_half_message` values

This rule is now implemented in the current codebase:

- `VideoAISkill` submits `approved_package` to `/api/workflows/start-video`
- `ShortVideoWorkflow` detects that package and bypasses script approval
- `generate_script_from_approved_package_activity` and `ScriptService.generate_script_from_package()` turn the approved beats into production `SceneContract` data

## Relation To Current Codebase

This v1 design stays compatible with the current project shape:

- Telegram skill/session flow already exists
- persona readiness and voice fields already exist
- OpenClaw is already available for structured planning
- the short-video production lane already consumes an approved pre-production package
- top-half metadata now carries source type, capture target, capture hint, and optional source reference into production

This v1 design intentionally does not require:

- PDF parsing
- image reference ingestion
- script editing workflows

## Non-Goals For V1

V1 does not attempt to implement:

- full storyboard generation
- user-provided script editing
- beat-by-beat visual editing
- multi-modal uploads
- durable DB-backed storage for pre-production packages

Those can be added only after the `idea_brief -> ConceptBrief -> BeatSheet -> ApprovedProductionPackage` path is stable.

## Final Decision

The recommended v1 pre-production design for this repo is:

- one input mode only: `idea_brief`
- `reference_url` and `access_level` are required in that mode
- `ConceptBrief` is the video-level contract
- `BeatSheet` is the structure-level contract
- `ApprovedProductionPackage` is the only production handoff
- no `script_input` branch in v1

This is the smallest design that still matches the intended split-screen product direction and avoids introducing side logic that does not fit the current production pipeline.

## What Is Still Not Done

Still pending:

- richer durable package persistence beyond Telegram session / Redis
- operator tooling for package resume or package inspection outside the Telegram session
- more input modes such as `script_input`, image reference, and PDF brief
- deeper authenticated top-half capture planning beyond the current metadata + fallback model
- stronger deployed E2E coverage across Telegram, Temporal, storage, and providers

The current state should therefore be understood as:

- pre-production lock layer: done
- production handoff into the video workflow: done
- basic top-half runtime path: done for current `public_page_capture` / fallback model
- broader authoring and operator tooling: still pending
